import html
import json
import logging
import os
import re
import time
import urllib.parse
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from threading import Lock
from types import SimpleNamespace

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import models
from ..services.aliyun_service import AliyunService
from ..services.tencent_service import TencentService
from .database import SessionLocal
from .security import decrypt_secret

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    SEND_THROTTLE_SECONDS = float(os.getenv("SEND_THROTTLE_SECONDS", "0"))
except ValueError:
    SEND_THROTTLE_SECONDS = 0.0
try:
    CAMPAIGN_PARALLELISM = max(
        1, int(os.getenv("CAMPAIGN_PARALLELISM", "4"))
    )
except ValueError:
    CAMPAIGN_PARALLELISM = 4

scheduler = BackgroundScheduler()
_send_campaign_batch_lock = Lock()
_campaign_job_locks = {}
_campaign_job_locks_guard = Lock()

TRACKABLE_HREF_PATTERN = re.compile(
    r'href\s*=\s*(["\']?)(?P<url>(?:https?://|mailto:|tel:|sms:)[^"\'>\s]+)\1',
    re.IGNORECASE,
)
ANCHOR_BLOCK_PATTERN = re.compile(r"(?is)<a\b[^>]*>.*?</a>")
HTML_TAG_PATTERN = re.compile(r"(?is)<[^>]+>")
PLAIN_TEXT_LINK_PATTERN = re.compile(
    r"(?P<url>(?:https?://|www\.)[A-Z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+)|(?P<email>[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})",
    re.IGNORECASE,
)
TRAILING_LINK_PUNCTUATION = ".,;:!?)]}>，。；：！？）】》"
SUCCESS_STATUSES = ("sent", "opened", "clicked", "unsubscribed")


def get_db_session():
    return SessionLocal()


def _decrypt_account_secrets(account):
    if not account:
        return account
    return SimpleNamespace(
        id=getattr(account, "id", None),
        provider=getattr(account, "provider", None),
        name=getattr(account, "name", None),
        access_key_id=getattr(account, "access_key_id", None),
        access_key_secret=decrypt_secret(getattr(account, "access_key_secret", None)),
        region_id=getattr(account, "region_id", None),
        tencent_secret_id=getattr(account, "tencent_secret_id", None),
        tencent_secret_key=decrypt_secret(
            getattr(account, "tencent_secret_key", None)
        ),
        tencent_region=getattr(account, "tencent_region", None),
        from_alias=getattr(account, "from_alias", None),
        enabled=getattr(account, "enabled", True),
    )


def _legacy_account_from_setting(setting, provider: str):
    if not setting:
        return None
    if provider == "aliyun" and setting.access_key_id and setting.access_key_secret:
        return SimpleNamespace(
            id=None,
            provider="aliyun",
            name="legacy-aliyun",
            access_key_id=setting.access_key_id,
            access_key_secret=decrypt_secret(setting.access_key_secret),
            region_id=setting.region_id or "cn-hangzhou",
            from_alias=setting.from_alias,
            enabled=True,
        )
    if (
        provider == "tencent"
        and setting.tencent_secret_id
        and setting.tencent_secret_key
    ):
        return SimpleNamespace(
            id=None,
            provider="tencent",
            name="legacy-tencent",
            tencent_secret_id=setting.tencent_secret_id,
            tencent_secret_key=decrypt_secret(setting.tencent_secret_key),
            tencent_region=setting.tencent_region or "ap-hongkong",
            from_alias=setting.from_alias,
            enabled=True,
        )
    return None


def _resolve_campaign_account(db: Session, campaign, setting):
    provider = (campaign.provider or "").lower().strip()
    if provider not in {"aliyun", "tencent"}:
        return None, f"Unsupported provider: {campaign.provider}"

    if campaign.account_id:
        account = (
            db.query(models.CloudAccount)
            .filter(models.CloudAccount.id == campaign.account_id)
            .first()
        )
        if not account:
            return None, f"Cloud account not found: id={campaign.account_id}"
        if account.provider != provider:
            return None, "Campaign provider/account mismatch"
        if not account.enabled:
            return None, f"Cloud account disabled: id={campaign.account_id}"
        return _decrypt_account_secrets(account), None

    accounts = (
        db.query(models.CloudAccount)
        .filter(
            models.CloudAccount.provider == provider,
            models.CloudAccount.enabled.isnot(False),
        )
        .order_by(models.CloudAccount.id.asc())
        .all()
    )
    if len(accounts) == 1:
        return _decrypt_account_secrets(accounts[0]), None
    if len(accounts) > 1:
        return None, "Multiple cloud accounts found; campaign.account_id is required"

    legacy = _legacy_account_from_setting(setting, provider)
    if legacy:
        return legacy, None
    return None, "Cloud account not configured"


def _split_trailing_punctuation(value: str):
    stripped = value.rstrip(TRAILING_LINK_PUNCTUATION)
    suffix = value[len(stripped) :]
    return stripped, suffix


def _linkify_text_content(text: str):
    if not text:
        return text

    def repl(match):
        raw_url = match.group("url")
        if raw_url:
            url_text, suffix = _split_trailing_punctuation(raw_url)
            if not url_text:
                return raw_url
            href = (
                url_text
                if url_text.lower().startswith(("http://", "https://"))
                else f"https://{url_text}"
            )
            return f'<a href="{href}">{url_text}</a>{suffix}'

        raw_email = match.group("email")
        email_text, suffix = _split_trailing_punctuation(raw_email)
        if not email_text:
            return raw_email
        return f'<a href="mailto:{email_text}">{email_text}</a>{suffix}'

    return PLAIN_TEXT_LINK_PATTERN.sub(repl, text)


def _linkify_html_fragment(fragment: str):
    if not fragment:
        return fragment

    out = []
    last = 0
    for tag_match in HTML_TAG_PATTERN.finditer(fragment):
        out.append(_linkify_text_content(fragment[last : tag_match.start()]))
        out.append(tag_match.group(0))
        last = tag_match.end()
    out.append(_linkify_text_content(fragment[last:]))
    return "".join(out)


def linkify_plain_text_targets(body: str):
    if not body:
        return body

    out = []
    last = 0
    for anchor_match in ANCHOR_BLOCK_PATTERN.finditer(body):
        out.append(_linkify_html_fragment(body[last : anchor_match.start()]))
        out.append(anchor_match.group(0))
        last = anchor_match.end()
    out.append(_linkify_html_fragment(body[last:]))
    return "".join(out)


def _build_vars_map(recipient: models.CampaignRecipient):
    try:
        vars_map = (
            json.loads(recipient.extra_vars_snapshot) if recipient.extra_vars_snapshot else {}
        )
        if not isinstance(vars_map, dict):
            vars_map = {}
    except Exception:
        vars_map = {}

    first_name = (recipient.first_name_snapshot or "").strip()
    middle_name = (recipient.middle_name_snapshot or "").strip()
    last_name = (recipient.last_name_snapshot or "").strip()

    if first_name:
        vars_map["FirstName"] = first_name
        vars_map["first_name"] = first_name
        vars_map["firstName"] = first_name
    if middle_name:
        vars_map["MiddleName"] = middle_name
        vars_map["middle_name"] = middle_name
        vars_map["middleName"] = middle_name
    if last_name:
        vars_map["LastName"] = last_name
        vars_map["last_name"] = last_name
        vars_map["lastName"] = last_name

    full_name = (recipient.name_snapshot or "").strip()
    if not full_name:
        full_name = " ".join(
            part for part in [first_name, middle_name, last_name] if part
        ).strip()
    if full_name:
        vars_map["Name"] = full_name
        vars_map["name"] = full_name
        vars_map["username"] = full_name
    vars_map["Email"] = recipient.email or ""
    return vars_map


def _render_subject(template_subject: str, vars_map: dict):
    subject = template_subject or ""
    for key, val in vars_map.items():
        subject = subject.replace(f"{{{key}}}", str(val))
        subject = subject.replace(f"{{{{{key}}}}}", str(val))
    # Strip unresolved variable-like braces while preserving most CSS/JS braces.
    subject = re.sub(r"\{([^{}]+)\}", r"\1", subject)
    return subject


def _render_body(template_body: str, vars_map: dict):
    body = template_body or ""
    for key, val in vars_map.items():
        body = body.replace(f"{{{key}}}", str(val))
        body = body.replace(f"{{{{{key}}}}}", str(val))
    body = re.sub(r"\{([\w\s]+)\}", r"\1", body)
    return linkify_plain_text_targets(body)


def _apply_tracking(body: str, tracking_id: str, track_base_url: str, track_opens: bool, track_clicks: bool):
    tracked_links = set()
    working_body = body
    pixel_url = f"{track_base_url}/api/track/open/{tracking_id}"
    pixel_html = f'<img src="{pixel_url}" width="1" height="1" style="display:none" />'

    if track_opens:
        if "</body>" in working_body:
            working_body = working_body.replace("</body>", f"{pixel_html}</body>")
        else:
            working_body += pixel_html

    if track_clicks:
        def replace_link(match):
            quote = match.group(1) or '"'
            original_url = html.unescape(match.group("url").strip())
            if "/api/track/" in original_url:
                return match.group(0)
            encoded_url = urllib.parse.quote(original_url, safe="")
            tracking_url = (
                f"{track_base_url}/api/track/click/{tracking_id}?target={encoded_url}"
            )
            tracked_links.add(original_url)
            return f"href={quote}{tracking_url}{quote}"

        working_body, _ = TRACKABLE_HREF_PATTERN.subn(replace_link, working_body)

    return working_body, tracked_links


def _campaign_sent_count(db: Session, campaign_id: int) -> int:
    return (
        db.query(models.CampaignRecipient)
        .filter(
            models.CampaignRecipient.campaign_id == campaign_id,
            models.CampaignRecipient.status.in_(SUCCESS_STATUSES),
        )
        .count()
    )


def _finalize_campaign_status(db: Session, campaign):
    campaign.sent_count = _campaign_sent_count(db, campaign.id)
    pending_left = (
        db.query(models.CampaignRecipient)
        .filter(
            models.CampaignRecipient.campaign_id == campaign.id,
            models.CampaignRecipient.status.in_(("pending", "sending")),
        )
        .count()
    )
    if pending_left > 0:
        return

    failed_left = (
        db.query(models.CampaignRecipient)
        .filter(
            models.CampaignRecipient.campaign_id == campaign.id,
            models.CampaignRecipient.status == "failed",
        )
        .count()
    )
    total_recipients = campaign.total_recipients or 0
    if failed_left > 0 and campaign.sent_count < total_recipients:
        logger.warning(
            "Campaign %s finished with failures: sent=%s failed=%s total=%s",
            campaign.id,
            campaign.sent_count,
            failed_left,
            total_recipients,
        )
    # When there are no pending/sending recipients, the campaign has reached
    # a terminal state and should not auto-pause.
    campaign.status = "completed"


def _campaign_lock(campaign_id: int) -> Lock:
    with _campaign_job_locks_guard:
        if campaign_id not in _campaign_job_locks:
            _campaign_job_locks[campaign_id] = Lock()
        return _campaign_job_locks[campaign_id]


def _process_campaign_batch(campaign_id: int):
    campaign_lock = _campaign_lock(campaign_id)
    if not campaign_lock.acquire(blocking=False):
        logger.info("Campaign %s is already processing; skip overlapping run.", campaign_id)
        return

    db = None
    try:
        db = get_db_session()
        campaign = (
            db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
        )
        if not campaign or campaign.status != "sending":
            return

        setting = db.query(models.Setting).first() or SimpleNamespace(
            track_domain="http://127.0.0.1:8000",
            from_alias=None,
            access_key_id=None,
            access_key_secret=None,
            tencent_secret_id=None,
            tencent_secret_key=None,
            region_id="cn-hangzhou",
            tencent_region="ap-hongkong",
        )

        template = (
            db.query(models.EmailTemplate)
            .filter(models.EmailTemplate.id == campaign.template_id)
            .first()
        )
        if not template:
            campaign.status = "error"
            db.add(
                models.CampaignBatch(
                    campaign_id=campaign.id,
                    status="error",
                    recipient_count=0,
                    error_message=f"Template not found: id={campaign.template_id}",
                    sent_at=datetime.utcnow(),
                )
            )
            db.commit()
            return

        account, account_err = _resolve_campaign_account(db, campaign, setting)
        if account_err:
            campaign.status = "error"
            db.add(
                models.CampaignBatch(
                    campaign_id=campaign.id,
                    status="error",
                    recipient_count=0,
                    error_message=account_err,
                    sent_at=datetime.utcnow(),
                )
            )
            db.commit()
            return

        if template.provider in {"aliyun", "tencent"}:
            if template.provider != campaign.provider:
                campaign.status = "error"
                db.add(
                    models.CampaignBatch(
                        campaign_id=campaign.id,
                        status="error",
                        recipient_count=0,
                        error_message="Template/provider/account mismatch",
                        sent_at=datetime.utcnow(),
                    )
                )
                db.commit()
                return
            if template.account_id and account.id and template.account_id != account.id:
                campaign.status = "error"
                db.add(
                    models.CampaignBatch(
                        campaign_id=campaign.id,
                        status="error",
                        recipient_count=0,
                        error_message="Template/provider/account mismatch",
                        sent_at=datetime.utcnow(),
                    )
                )
                db.commit()
                return

        last_batch = (
            db.query(models.CampaignBatch)
            .filter(models.CampaignBatch.campaign_id == campaign.id)
            .order_by(models.CampaignBatch.sent_at.desc())
            .first()
        )
        if last_batch and last_batch.sent_at:
            gap_minutes = (datetime.utcnow() - last_batch.sent_at).total_seconds() / 60
            if gap_minutes < campaign.interval_minutes:
                return

        recipients = (
            db.query(models.CampaignRecipient)
            .filter(
                models.CampaignRecipient.campaign_id == campaign.id,
                models.CampaignRecipient.status == "pending",
            )
            .order_by(
                models.CampaignRecipient.send_order.asc(),
                models.CampaignRecipient.id.asc(),
            )
            .limit(campaign.batch_size)
            .all()
        )

        if not recipients:
            _finalize_campaign_status(db, campaign)
            db.commit()
            return

        logger.info(
            "Campaign %s (%s): sending batch size=%s",
            campaign.name,
            campaign.provider,
            len(recipients),
        )

        ali_client = None
        if campaign.provider == "aliyun":
            ali_client = AliyunService.create_client(
                account.access_key_id,
                account.access_key_secret,
                account.region_id,
            )

        track_base_url = (
            (setting.track_domain or "http://127.0.0.1:8000").rstrip("/")
        )
        batch_sent = 0
        batch_failed = 0

        for recipient in recipients:
            db.refresh(campaign)
            if campaign.status != "sending":
                break

            clean_to_address = (recipient.email or "").split()[0].strip()
            if not clean_to_address:
                recipient.status = "failed"
                recipient.error_message = "Recipient email is empty"
                db.commit()
                batch_failed += 1
                continue

            if not recipient.tracking_id:
                recipient.tracking_id = str(uuid.uuid4())
            tracking_id = recipient.tracking_id
            recipient.status = "sending"
            db.commit()

            vars_map = _build_vars_map(recipient)
            subject = _render_subject(template.subject, vars_map)
            real_from_alias = (
                campaign.from_alias
                or template.from_alias
                or account.from_alias
                or setting.from_alias
                or campaign.account_name.split("@")[0]
            )

            try:
                if campaign.provider == "tencent":
                    if template.provider == "tencent" and template.provider_id:
                        tencent_response = TencentService.send_mail(
                            account.tencent_secret_id,
                            account.tencent_secret_key,
                            account.tencent_region,
                            campaign.account_name,
                            clean_to_address,
                            subject,
                            "",
                            from_alias=real_from_alias,
                            template_id=template.provider_id,
                            template_params=json.dumps(vars_map, ensure_ascii=False),
                            reply_to_address=campaign.reply_to_address,
                        )
                        if tencent_response and hasattr(tencent_response, "MessageId"):
                            recipient.message_id = tencent_response.MessageId
                            recipient.provider = "tencent"
                    else:
                        body = _render_body(template.body, vars_map)
                        body, tracked_links = _apply_tracking(
                            body,
                            tracking_id,
                            track_base_url,
                            campaign.track_opens,
                            campaign.track_clicks,
                        )
                        tencent_response = TencentService.send_mail(
                            account.tencent_secret_id,
                            account.tencent_secret_key,
                            account.tencent_region,
                            campaign.account_name,
                            clean_to_address,
                            subject,
                            body,
                            from_alias=real_from_alias,
                            reply_to_address=campaign.reply_to_address,
                        )
                        if tencent_response and hasattr(tencent_response, "MessageId"):
                            recipient.message_id = tencent_response.MessageId
                            recipient.provider = "tencent"
                        if campaign.track_clicks and tracked_links:
                            existing_urls = {
                                row[0]
                                for row in db.query(models.CampaignRecipientLink.target_url)
                                .filter(
                                    models.CampaignRecipientLink.tracking_id
                                    == tracking_id
                                )
                                .all()
                            }
                            for target_url in tracked_links - existing_urls:
                                db.add(
                                    models.CampaignRecipientLink(
                                        tracking_id=tracking_id,
                                        target_url=target_url,
                                    )
                                )
                else:
                    body = _render_body(template.body, vars_map)
                    body, tracked_links = _apply_tracking(
                        body,
                        tracking_id,
                        track_base_url,
                        campaign.track_opens,
                        campaign.track_clicks,
                    )
                    use_reply_to = True if campaign.reply_to_address else False
                    AliyunService.single_send_mail(
                        ali_client,
                        campaign.account_name,
                        use_reply_to,
                        1,
                        clean_to_address,
                        subject,
                        body,
                        real_from_alias,
                    )
                    if campaign.track_clicks and tracked_links:
                        existing_urls = {
                            row[0]
                            for row in db.query(models.CampaignRecipientLink.target_url)
                            .filter(
                                models.CampaignRecipientLink.tracking_id == tracking_id
                            )
                            .all()
                        }
                        for target_url in tracked_links - existing_urls:
                            db.add(
                                models.CampaignRecipientLink(
                                    tracking_id=tracking_id,
                                    target_url=target_url,
                                )
                            )

                recipient.status = "sent"
                recipient.error_message = None
                recipient.sent_at = datetime.utcnow()
                db.commit()
                batch_sent += 1
                if SEND_THROTTLE_SECONDS > 0:
                    time.sleep(SEND_THROTTLE_SECONDS)
            except Exception as e:
                logger.error(
                    "Send failed campaign=%s recipient=%s err=%s",
                    campaign.id,
                    clean_to_address,
                    e,
                )
                recipient.status = "failed"
                recipient.error_message = str(e)
                db.commit()
                batch_failed += 1

        if campaign.status == "sending":
            _finalize_campaign_status(db, campaign)

        batch_status = "sent"
        batch_error = None
        if batch_failed and not batch_sent:
            batch_status = "error"
            batch_error = "Batch failed"
        elif batch_failed:
            batch_status = "partial"
            batch_error = f"Batch partial success: sent={batch_sent}, failed={batch_failed}"

        db.add(
            models.CampaignBatch(
                campaign_id=campaign.id,
                status=batch_status,
                recipient_count=batch_sent + batch_failed,
                error_message=batch_error,
                sent_at=datetime.utcnow(),
            )
        )
        db.commit()
    except Exception:
        logger.exception("Campaign batch processing failed campaign_id=%s", campaign_id)
    finally:
        if db is not None:
            db.close()
        campaign_lock.release()


def send_campaign_batch():
    if not _send_campaign_batch_lock.acquire(blocking=False):
        logger.info("send_campaign_batch is already running; skip overlapping trigger.")
        return

    db = None
    active_campaign_ids = []
    try:
        db = get_db_session()
        scheduled_campaigns = (
            db.query(models.Campaign)
            .filter(models.Campaign.status == "scheduled")
            .all()
        )
        for campaign in scheduled_campaigns:
            if campaign.scheduled_start_time and datetime.utcnow() >= campaign.scheduled_start_time:
                campaign.status = "sending"
        db.commit()

        active_campaign_ids = [
            row.id
            for row in db.query(models.Campaign.id)
            .filter(models.Campaign.status == "sending")
            .all()
        ]
    finally:
        if db is not None:
            db.close()

    try:
        if not active_campaign_ids:
            return

        worker_count = min(CAMPAIGN_PARALLELISM, len(active_campaign_ids))
        logger.info(
            "Dispatching %s campaigns with parallelism=%s",
            len(active_campaign_ids),
            worker_count,
        )
        with ThreadPoolExecutor(
            max_workers=worker_count, thread_name_prefix="campaign-batch"
        ) as executor:
            futures = [
                executor.submit(_process_campaign_batch, campaign_id)
                for campaign_id in active_campaign_ids
            ]
            for future in as_completed(futures):
                future.result()
    finally:
        _send_campaign_batch_lock.release()


def pull_email_tracking_status():
    db = get_db_session()
    try:
        tencent_accounts = (
            db.query(models.CloudAccount)
            .filter(
                models.CloudAccount.provider == "tencent",
                models.CloudAccount.enabled.isnot(False),
                models.CloudAccount.tencent_secret_id.isnot(None),
                models.CloudAccount.tencent_secret_key.isnot(None),
            )
            .order_by(models.CloudAccount.id.asc())
            .all()
        )
        tencent_accounts = [_decrypt_account_secrets(a) for a in tencent_accounts]

        if not tencent_accounts:
            setting = db.query(models.Setting).first()
            legacy = _legacy_account_from_setting(setting, "tencent")
            if not legacy:
                return
            tencent_accounts = [legacy]

        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        total_updated = 0
        for account in tencent_accounts:
            account_name = getattr(account, "name", "legacy-tencent")
            account_id = getattr(account, "id", None)
            secret_id = getattr(account, "tencent_secret_id", None)
            secret_key = getattr(account, "tencent_secret_key", None)
            region = getattr(account, "tencent_region", "ap-hongkong") or "ap-hongkong"

            if not secret_id or not secret_key:
                continue

            unresolved_filters = (
                models.CampaignRecipient.provider == "tencent",
                models.CampaignRecipient.message_id.isnot(None),
                models.CampaignRecipient.sent_at >= seven_days_ago,
                models.CampaignRecipient.status.in_(["sent", "opened"]),
                models.Campaign.provider == "tencent",
            )

            pending_query = db.query(models.CampaignRecipient).join(
                models.Campaign,
                models.Campaign.id == models.CampaignRecipient.campaign_id,
            )
            if account_id is not None:
                pending_query = pending_query.filter(models.Campaign.account_id == account_id)
            else:
                pending_query = pending_query.filter(models.Campaign.account_id.is_(None))
            pending_query = pending_query.filter(*unresolved_filters)

            if pending_query.count() == 0:
                continue

            pending_dates = (
                db.query(func.date(models.CampaignRecipient.sent_at))
                .join(
                    models.Campaign,
                    models.Campaign.id == models.CampaignRecipient.campaign_id,
                )
                .filter(*unresolved_filters)
            )
            if account_id is not None:
                pending_dates = pending_dates.filter(models.Campaign.account_id == account_id)
            else:
                pending_dates = pending_dates.filter(models.Campaign.account_id.is_(None))
            pending_dates = pending_dates.distinct().all()

            per_page_limit = 100
            max_pages_per_date = 50

            for (date_str,) in pending_dates:
                if not date_str:
                    continue
                try:
                    date_query = (
                        db.query(models.CampaignRecipient)
                        .join(
                            models.Campaign,
                            models.Campaign.id == models.CampaignRecipient.campaign_id,
                        )
                        .filter(
                            *unresolved_filters,
                            func.date(models.CampaignRecipient.sent_at) == date_str,
                        )
                    )
                    if account_id is not None:
                        date_query = date_query.filter(models.Campaign.account_id == account_id)
                    else:
                        date_query = date_query.filter(models.Campaign.account_id.is_(None))

                    date_recipients = date_query.all()
                    date_recipient_map = {
                        r.message_id: r for r in date_recipients if r.message_id
                    }
                    if not date_recipient_map:
                        continue

                    offset = 0
                    pages = 0
                    date_updated = 0

                    while pages < max_pages_per_date:
                        response = TencentService.get_send_email_status(
                            secret_id,
                            secret_key,
                            region,
                            date_str,
                            offset=offset,
                            limit=per_page_limit,
                        )
                        status_list = (
                            list(response.EmailStatusList)
                            if response and response.EmailStatusList
                            else []
                        )
                        if not status_list:
                            break

                        page_updated = 0
                        for cloud_status in status_list:
                            message_id = getattr(cloud_status, "MessageId", None)
                            if not message_id:
                                continue
                            recipient = date_recipient_map.get(message_id)
                            if not recipient:
                                continue

                            updated = False
                            now = datetime.utcnow()
                            user_opened = bool(getattr(cloud_status, "UserOpened", False))
                            user_clicked = bool(getattr(cloud_status, "UserClicked", False))

                            if user_opened and not recipient.opened_at:
                                recipient.opened_at = now
                                updated = True
                                if recipient.status == "sent":
                                    recipient.status = "opened"

                            if user_clicked:
                                if not recipient.clicked_at:
                                    recipient.clicked_at = now
                                    updated = True
                                if not recipient.opened_at:
                                    recipient.opened_at = now
                                    updated = True
                                if recipient.status != "clicked":
                                    recipient.status = "clicked"
                                    updated = True
                                date_recipient_map.pop(message_id, None)

                            if updated:
                                page_updated += 1

                        if page_updated:
                            db.commit()
                            date_updated += page_updated

                        if len(status_list) < per_page_limit:
                            break
                        offset += per_page_limit
                        pages += 1

                    if date_updated:
                        total_updated += date_updated
                except Exception as e:
                    logger.error(
                        "[Pull Tracking] Error account=%s date=%s err=%s",
                        account_name,
                        date_str,
                        e,
                    )
                    continue

        if total_updated:
            logger.info("[Pull Tracking] Total updated recipients: %s", total_updated)
    except Exception as e:
        logger.error("[Pull Tracking] Error: %s", e)
    finally:
        db.close()


def recover_interrupted_campaigns():
    """
    Recover recipients left in `sending` due to process crash/kill.
    They are re-queued to `pending` so campaigns can continue after restart.
    """
    db = get_db_session()
    try:
        stuck_recipients = (
            db.query(models.CampaignRecipient)
            .join(
                models.Campaign,
                models.Campaign.id == models.CampaignRecipient.campaign_id,
            )
            .filter(
                models.CampaignRecipient.status == "sending",
                models.Campaign.status.in_(
                    ("sending", "pending", "scheduled", "paused", "completed")
                ),
            )
            .all()
        )
        affected_campaign_ids = set()
        for recipient in stuck_recipients:
            recipient.status = "pending"
            if not recipient.error_message:
                recipient.error_message = "Recovered after process restart"
            affected_campaign_ids.add(recipient.campaign_id)

        for campaign_id in affected_campaign_ids:
            campaign = (
                db.query(models.Campaign)
                .filter(models.Campaign.id == campaign_id)
                .first()
            )
            if campaign:
                campaign.sent_count = _campaign_sent_count(db, campaign_id)
                if campaign.status == "completed":
                    # A completed campaign with recoverable recipients is inconsistent.
                    campaign.status = "paused"

        normalized_completed = 0
        completed_campaigns = (
            db.query(models.Campaign)
            .filter(models.Campaign.status == "completed")
            .all()
        )
        for campaign in completed_campaigns:
            campaign.sent_count = _campaign_sent_count(db, campaign.id)
            pending_or_sending = (
                db.query(models.CampaignRecipient)
                .filter(
                    models.CampaignRecipient.campaign_id == campaign.id,
                    models.CampaignRecipient.status.in_(("pending", "sending")),
                )
                .count()
            )
            if pending_or_sending > 0:
                campaign.status = "paused"
                normalized_completed += 1

        db.commit()
        if stuck_recipients or normalized_completed:
            logger.warning(
                "Recovered %s recipients from 'sending' to 'pending' across %s campaigns; normalized %s stale completed campaigns.",
                len(stuck_recipients),
                len(affected_campaign_ids),
                normalized_completed,
            )
    except Exception:
        db.rollback()
        logger.exception("Failed to recover interrupted campaigns.")
    finally:
        db.close()


def start_scheduler():
    if not scheduler.running:
        recover_interrupted_campaigns()
        scheduler.add_job(
            send_campaign_batch,
            "interval",
            minutes=1,
            id="send_campaign_batch_interval",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        scheduler.add_job(
            pull_email_tracking_status,
            "interval",
            minutes=5,
            id="pull_email_tracking_status_interval",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()
