from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from sqlalchemy import func
from .database import SessionLocal
from ..models import models
from ..services.aliyun_service import AliyunService
from ..services.tencent_service import TencentService
import logging
import json
import time
from datetime import datetime
import random
import re
import uuid
import urllib.parse
import html
from threading import Lock

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
_send_campaign_batch_lock = Lock()
TRACKABLE_HREF_PATTERN = re.compile(
    r'href\s*=\s*(["\']?)(?P<url>(?:https?://|mailto:|tel:|sms:)[^"\'>\s]+)\1',
    re.IGNORECASE,
)
ANCHOR_BLOCK_PATTERN = re.compile(r"(?is)<a\b[^>]*>.*?</a>")
HTML_TAG_PATTERN = re.compile(r"(?is)<[^>]+>")
PLAIN_TEXT_LINK_PATTERN = re.compile(
    r"(?P<url>(?:https?://|www\.)[^\s<>\"]+)|(?P<email>[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})",
    re.IGNORECASE,
)
TRAILING_LINK_PUNCTUATION = ".,;:!?)]}>，。；：！？）】》"


def get_db_session():
    return SessionLocal()


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
    """
    Convert plain text URLs/emails in HTML text nodes into anchor tags.
    Existing <a>...</a> blocks are preserved to avoid nested anchors.
    """
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


def send_campaign_batch():
    if not _send_campaign_batch_lock.acquire(blocking=False):
        logger.info(
            "send_campaign_batch is already running; skip overlapping trigger."
        )
        return

    db = None
    try:
        db = get_db_session()
        # 0. 濡偓閺屻儴顓搁崚鎺嶆崲閸?
        scheduled_campaigns = (
            db.query(models.Campaign)
            .filter(models.Campaign.status == "scheduled")
            .all()
        )
        for sc in scheduled_campaigns:
            if sc.scheduled_start_time and datetime.utcnow() >= sc.scheduled_start_time:
                sc.status = "sending"
                db.commit()

        # 1. 閺屻儲澹樻潻鎰攽娑擃厾娈戞禒璇插
        active_campaigns = (
            db.query(models.Campaign).filter(models.Campaign.status == "sending").all()
        )

        for campaign in active_campaigns:
            setting = db.query(models.Setting).first()
            if not setting:
                continue

            template = (
                db.query(models.EmailTemplate)
                .filter(models.EmailTemplate.id == campaign.template_id)
                .first()
            )
            if not template:
                err_msg = f"Template not found: id={campaign.template_id}"
                logger.error(f"Campaign {campaign.id} failed: {err_msg}")
                campaign.status = "error"
                db.add(
                    models.CampaignBatch(
                        campaign_id=campaign.id,
                        status="error",
                        recipient_count=0,
                        error_message=err_msg,
                        sent_at=datetime.utcnow(),
                    )
                )
                db.commit()
                continue

            # 闂傛挳娈уΛ鈧弻?
            last_batch = (
                db.query(models.CampaignBatch)
                .filter(models.CampaignBatch.campaign_id == campaign.id)
                .order_by(models.CampaignBatch.sent_at.desc())
                .first()
            )

            if last_batch:
                time_since_last = (
                    datetime.utcnow() - last_batch.sent_at
                ).total_seconds() / 60
                if time_since_last < campaign.interval_minutes:
                    continue

            # 閼惧嘲褰囬懕鏃傞兇娴?
            contacts = (
                db.query(models.Contact)
                .filter(models.Contact.list_id == campaign.list_id)
                .offset(campaign.sent_count)
                .limit(campaign.batch_size)
                .all()
            )

            if not contacts:
                campaign.status = "completed"
                db.commit()
                continue

            logger.info(
                f"Campaign {campaign.name} ({campaign.provider}): Sending batch of {len(contacts)}..."
            )

            ali_client = None
            if campaign.provider == "aliyun":
                ali_client = AliyunService.create_client(
                    setting.access_key_id, setting.access_key_secret, setting.region_id
                )

            for i, contact in enumerate(contacts):
                db.refresh(campaign)
                if campaign.status != "sending":
                    break

                clean_to_address = contact.email.split()[0].strip()
                tracking_id = str(uuid.uuid4())
                tracked_links = set()

                # 鐠佹澘缍嶉崣鎴︹偓浣规）韫?
                recipient = models.CampaignRecipient(
                    campaign_id=campaign.id,
                    contact_id=contact.id,
                    email=clean_to_address,
                    tracking_id=tracking_id,
                    status="sending",
                )
                db.add(recipient)
                db.commit()  # 閸忓牊褰佹禍銈勪簰閼惧嘲绶?ID (閾忕晫鍔ф潻娆撳櫡 UUID 婢剁喓鏁ゆ禍?

                # 閸戝棗顦崣姗€鍣?
                vars_map = json.loads(contact.extra_vars) if contact.extra_vars else {}
                if contact.name:
                    vars_map["Name"] = contact.name
                    vars_map["name"] = contact.name
                    vars_map["username"] = contact.name
                vars_map["Email"] = contact.email or ""

                # 閺嶅洭顣介弴鎸庡床 (閸忔娊鏁敍姘倱閺冭埖鏁幐?{key} 閸?{{key}})
                subject = template.subject
                for key, val in vars_map.items():
                    subject = subject.replace(f"{{{key}}}", str(val))
                    subject = subject.replace(f"{{{{{key}}}}}", str(val))

                # 濞撳懐鎮婇張顏勫爱闁板秶娈戦崡鐘辩秴缁楋讣绱扮亸?{娴犵粯鍓伴崘鍛啇} 娑擃厾娈戦懞杈ㄥ閸欓些闂勩倧绱濇穱婵堟殌閸愬懘鍎撮弬鍥ㄦ拱
                subject = re.sub(r"\{([^{}]+)\}", r"\1", subject)

                real_from_alias = (
                    campaign.from_alias
                    or template.from_alias
                    or setting.from_alias
                    or campaign.account_name.split("@")[0]
                )

                # 鏉╁€熼嚋閸嶅繒绀?URL (娴犲酣鍘ょ純顔款嚢閸?
                track_base_url = setting.track_domain or "http://192.168.2.8:8000"
                # 缁夊娅庨張顐㈢啲閺傛粍娼?
                if track_base_url.endswith("/"):
                    track_base_url = track_base_url[:-1]

                pixel_url = f"{track_base_url}/api/track/open/{tracking_id}"
                pixel_html = f'<img src="{pixel_url}" width="1" height="1" style="display:none" />'

                # 闁剧偓甯存潻鍊熼嚋閺囨寧宕查崙鑺ユ殶
                def replace_link(match):
                    quote = match.group(1) or '"'
                    original_url = html.unescape(match.group("url").strip())
                    # 闁灝鍘ら弴鎸庡床瀹歌尙绮￠弰顖濇嫹闊亪鎽奸幒銉ф畱URL
                    if "/api/track" in original_url:
                        return match.group(0)
                    encoded_url = urllib.parse.quote(original_url, safe="")
                    tracking_url = f"{track_base_url}/api/track/click/{tracking_id}?target={encoded_url}"
                    tracked_links.add(original_url)
                    return f"href={quote}{tracking_url}{quote}"

                try:
                    if campaign.provider == "tencent":
                        if template.provider == "tencent" and template.provider_id:
                            # 閼垫崘顔嗘禍鎴災侀弶鎸幠佸?                            # 鐏忔繆鐦▔銊ュ弳 pixel 閸掓澘褰夐柌蹇庤厬閿涘苯顩ч弸婊勀侀弶鎸庢暜閹?{{tracking_pixel}}
                            # 娴ｅ棗銇囨径姘殶閺冭泛鈧瑦膩閺夊じ绗夐弨顖涘瘮閿涘本澧嶆禒銉δ侀弶鎸幠佸蹇曟畱鏉╁€熼嚋濮ｆ棁绶濋崶浼存閿涘矂娅庨棃鐐茨侀弶鍧楀櫡妫板嫮鏆€娴滃棔缍呯純?                            # 鏉╂瑩鍣烽弳鍌涙鐠哄疇绻冨Ο鈩冩緲濡€崇础閻ㄥ嫬鍎氱槐鐘虫暈閸忋儻绱濋幋鏍偓鍛矌娴犲懍绶风挧?send_mail 閹存劕濮?
                            tencent_response = TencentService.send_mail(
                                setting.tencent_secret_id,
                                setting.tencent_secret_key,
                                setting.tencent_region,
                                campaign.account_name,
                                clean_to_address,
                                subject,
                                "",
                                from_alias=real_from_alias,
                                template_id=template.provider_id,
                                template_params=json.dumps(vars_map),
                                reply_to_address=campaign.reply_to_address,
                            )
                            # Save MessageId for Pull Tracking
                            if tencent_response and hasattr(
                                tencent_response, "MessageId"
                            ):
                                recipient.message_id = tencent_response.MessageId
                                recipient.provider = "tencent"
                        else:
                            # 閼垫崘顔嗘禍?HTML 濡€崇础
                            body = template.body
                            for key, val in vars_map.items():
                                body = body.replace(f"{{{key}}}", str(val))
                                body = body.replace(f"{{{{{key}}}}}", str(val))

                            # 濞撳懐鎮婇張顏勫爱闁板秶娈戦崣姗€鍣?(閸欘亝绔婚悶鍡欐箙鐠ч攱娼甸崓蹇撳綁闁插繒娈戦敍宀勪缉閸忓秶鐗崸?CSS/JS)
                            body = re.sub(r"\{([\w\s]+)\}", r"\1", body)
                            body = linkify_plain_text_targets(body)

                            # 1. 濞夈劌鍙嗛崓蹇曠
                            if campaign.track_opens:
                                if "</body>" in body:
                                    body = body.replace(
                                        "</body>", f"{pixel_html}</body>"
                                    )
                                    logger.info(
                                        f"Injecting pixel for {clean_to_address}: Success (</body> found)"
                                    )
                                else:
                                    body += pixel_html
                                    logger.info(
                                        f"Injecting pixel for {clean_to_address}: Appended to end"
                                    )

                            # 2. 閺囨寧宕查悙鐟板毊闁剧偓甯?
                            if campaign.track_clicks:
                                body, replaced_links = TRACKABLE_HREF_PATTERN.subn(
                                    replace_link,
                                    body,
                                )
                                if replaced_links:
                                    logger.info(
                                        f"Link tracking injected for {clean_to_address}"
                                    )

                            tencent_response = TencentService.send_mail(
                                setting.tencent_secret_id,
                                setting.tencent_secret_key,
                                setting.tencent_region,
                                campaign.account_name,
                                clean_to_address,
                                subject,
                                body,
                                from_alias=real_from_alias,
                                reply_to_address=campaign.reply_to_address,
                            )
                            # Save MessageId for Pull Tracking
                            if tencent_response and hasattr(
                                tencent_response, "MessageId"
                            ):
                                recipient.message_id = tencent_response.MessageId
                                recipient.provider = "tencent"
                    elif campaign.provider == "aliyun":
                        body = template.body
                        for key, val in vars_map.items():
                            body = body.replace(f"{{{key}}}", str(val))
                            body = body.replace(f"{{{{{key}}}}}", str(val))

                        # 濞撳懐鎮婇張顏勫爱闁板秶娈戦崣姗€鍣?(閸欘亝绔婚悶鍡欐箙鐠ч攱娼甸崓蹇撳綁闁插繒娈戦敍宀勪缉閸忓秶鐗崸?CSS/JS)
                        body = re.sub(r"\{([\w\s]+)\}", r"\1", body)
                        body = linkify_plain_text_targets(body)

                        # 1. 濞夈劌鍙嗛崓蹇曠
                        if campaign.track_opens:
                            if "</body>" in body:
                                body = body.replace("</body>", f"{pixel_html}</body>")
                                logger.info(
                                    f"Injecting pixel for {clean_to_address} (Aliyun)"
                                )
                            else:
                                body += pixel_html

                        # 2. 閺囨寧宕查悙鐟板毊闁剧偓甯?
                        if campaign.track_clicks:
                            body, replaced_links = TRACKABLE_HREF_PATTERN.subn(
                                replace_link, body
                            )
                            if replaced_links:
                                logger.info(
                                    f"Link tracking injected for {clean_to_address} (Aliyun)"
                                )

                        # 闂冨潡鍣锋禍? 婵″倹鐏?campaign.reply_to_address 閺堝鈧》绱濋崚娆掝吇娑撳搫绱戦崥顖氭礀娣団€虫勾閸р偓閸旂喕鍏?(True)
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

                    logger.info(f"[{i + 1}/{len(contacts)}] Sent to {clean_to_address}")
                    # 閺囧瓨鏌婇悩鑸碘偓浣疯礋 sent
                    recipient.status = "sent"
                    recipient.sent_at = datetime.utcnow()

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
                                    tracking_id=tracking_id, target_url=target_url
                                )
                            )

                    db.commit()

                    time.sleep(random.uniform(0.2, 1.0))
                except Exception as e:
                    logger.error(f"閴?FAILED: {clean_to_address} - {e}")
                    recipient.status = "failed"
                    recipient.error_message = str(e)
                    db.commit()

            # 閺囧瓨鏌婃潻娑樺
            campaign.sent_count += len(contacts)
            if campaign.sent_count >= campaign.total_recipients:
                campaign.status = "completed"

            db.add(
                models.CampaignBatch(
                    campaign_id=campaign.id,
                    status="sent",
                    recipient_count=len(contacts),
                    sent_at=datetime.utcnow(),
                )
            )
            db.commit()
    finally:
        if db is not None:
            db.close()
        _send_campaign_batch_lock.release()


def pull_email_tracking_status():
    """
    后台任务：从腾讯云拉取邮件追踪状态(打开/点击)
    每 5 分钟运行一次，查询最近 7 天内有 message_id 的收件人记录
    """
    db = get_db_session()
    try:
        setting = db.query(models.Setting).first()
        if (
            not setting
            or not setting.tencent_secret_id
            or not setting.tencent_secret_key
        ):
            return  # 濞屸剝婀侀柊宥囩枂閼垫崘顔嗘禍鎴礉鐠哄疇绻?
        # 閺屻儴顕楅張鈧潻?7 婢垛晛鍞村鍛倱濮濄儳娈戦懙鎹愵唵娴滄垶鏁规禒鏈垫眽
        from datetime import timedelta

        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        unresolved_filters = (
            models.CampaignRecipient.provider == "tencent",
            models.CampaignRecipient.message_id.isnot(None),
            models.CampaignRecipient.sent_at >= seven_days_ago,
            # 娴犲秹娓剁憰浣芥嫹闊亝娲块弬鎵畱鐠佹澘缍嶉敍姝磂nt/opened閿涘潏licked 鐟欏棔璐熺紒鍫熲偓渚婄礆
            models.CampaignRecipient.status.in_(["sent", "opened"]),
        )

        pending_count = (
            db.query(models.CampaignRecipient)
            .filter(*unresolved_filters)
            .count()
        )
        if pending_count == 0:
            return

        logger.info(f"[Pull Tracking] Pending Tencent recipients: {pending_count}")

        # 娴犲懏濯洪崣鏍х摠閸︺劍婀€瑰本鍨氭潻鍊熼嚋鐠佹澘缍嶉惃鍕）閺堢噦绱濋崙蹇撶毌閺冪姵鏅?API 閺屻儴顕?
        pending_dates = (
            db.query(func.date(models.CampaignRecipient.sent_at))
            .filter(*unresolved_filters)
            .distinct()
            .all()
        )

        total_updated = 0
        per_page_limit = 100
        max_pages_per_date = 50

        for (date_str,) in pending_dates:
            if not date_str:
                continue
            try:
                date_recipients = (
                    db.query(models.CampaignRecipient)
                    .filter(*unresolved_filters, func.date(models.CampaignRecipient.sent_at) == date_str)
                    .all()
                )
                if not date_recipients:
                    continue

                # MessageId -> recipient
                date_recipient_map = {
                    r.message_id: r for r in date_recipients if r.message_id
                }
                if not date_recipient_map:
                    continue

                logger.info(
                    f"[Pull Tracking] Syncing date={date_str}, unresolved={len(date_recipient_map)}"
                )

                offset = 0
                pages = 0
                date_updated = 0

                while pages < max_pages_per_date:
                    response = TencentService.get_send_email_status(
                        setting.tencent_secret_id,
                        setting.tencent_secret_key,
                        setting.tencent_region or "ap-hongkong",
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

                        # 閹垫挸绱戦敍姘涧鐠佹澘缍嶆＃鏍﹂嚋閹垫挸绱戦弮鍫曟？
                        if user_opened and not recipient.opened_at:
                            recipient.opened_at = now
                            updated = True
                            if recipient.status == "sent":
                                recipient.status = "opened"

                        # 閻愮懓鍤敍姘卞仯閸戣绱崗鍫㈤獓妤傛ü绨幍鎾崇磻
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
                            # clicked 鐟欏棔璐熺紒鍫熲偓渚婄礉闁灝鍘ら崥搴ｇ敾闁插秴顦插Λ鈧弻?
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
                    logger.info(
                        f"[Pull Tracking] date={date_str} updated={date_updated}"
                    )
                    total_updated += date_updated

            except Exception as e:
                logger.error(
                    f"[Pull Tracking] Error fetching status for {date_str}: {e}"
                )
                continue

        if total_updated:
            logger.info(f"[Pull Tracking] Total updated recipients: {total_updated}")

    except Exception as e:
        logger.error(f"[Pull Tracking] Error: {e}")
    finally:
        db.close()


def start_scheduler():
    if not scheduler.running:
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
