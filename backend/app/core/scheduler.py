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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def get_db_session():
    return SessionLocal()


def send_campaign_batch():
    db = get_db_session()
    try:
        # 0. 检查计划任务
        scheduled_campaigns = (
            db.query(models.Campaign)
            .filter(models.Campaign.status == "scheduled")
            .all()
        )
        for sc in scheduled_campaigns:
            if sc.scheduled_start_time and datetime.utcnow() >= sc.scheduled_start_time:
                sc.status = "sending"
                db.commit()

        # 1. 查找运行中的任务
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

            # 间隔检查
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

            # 获取联系人
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

                # 记录发送日志
                recipient = models.CampaignRecipient(
                    campaign_id=campaign.id,
                    contact_id=contact.id,
                    email=clean_to_address,
                    tracking_id=tracking_id,
                    status="sending",
                )
                db.add(recipient)
                db.commit()  # 先提交以获得 ID (虽然这里 UUID 够用了)

                # 准备变量
                vars_map = json.loads(contact.extra_vars) if contact.extra_vars else {}
                if contact.name:
                    vars_map["Name"] = contact.name
                    vars_map["name"] = contact.name
                    vars_map["username"] = contact.name
                vars_map["Email"] = contact.email or ""

                # 标题替换 (关键：同时支持 {key} 和 {{key}})
                subject = template.subject
                for key, val in vars_map.items():
                    subject = subject.replace(f"{{{key}}}", str(val))
                    subject = subject.replace(f"{{{{{key}}}}}", str(val))

                # 清理未匹配的占位符：将 {任意内容} 中的花括号移除，保留内部文本
                subject = re.sub(r"\{([^{}]+)\}", r"\1", subject)

                real_from_alias = (
                    campaign.from_alias
                    or template.from_alias
                    or setting.from_alias
                    or campaign.account_name.split("@")[0]
                )

                # 追踪像素 URL (从配置读取)
                track_base_url = setting.track_domain or "http://192.168.2.8:8000"
                # 移除末尾斜杠
                if track_base_url.endswith("/"):
                    track_base_url = track_base_url[:-1]

                pixel_url = f"{track_base_url}/api/track/open/{tracking_id}"
                pixel_html = f'<img src="{pixel_url}" width="1" height="1" style="display:none" />'

                # 链接追踪替换函数
                def replace_link(match):
                    quote = match.group(1)
                    original_url = match.group(2)
                    # 避免替换已经是追踪链接的URL
                    if "/api/track" in original_url:
                        return match.group(0)
                    encoded_url = urllib.parse.quote(original_url, safe="")
                    tracking_url = f"{track_base_url}/api/track/click/{tracking_id}?target={encoded_url}"
                    tracked_links.add(original_url)
                    return f"href={quote}{tracking_url}{quote}"

                try:
                    if campaign.provider == "tencent":
                        if template.provider == "tencent" and template.provider_id:
                            # 腾讯云模板模式
                            # 尝试注入 pixel 到变量中，如果模板支持 {{tracking_pixel}}
                            # 但大多数时候模板不支持，所以模板模式的追踪比较困难，除非模板里预留了位置
                            # 这里暂时跳过模板模式的像素注入，或者仅仅依赖 send_mail 成功

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
                            # 腾讯云 HTML 模式
                            body = template.body
                            for key, val in vars_map.items():
                                body = body.replace(f"{{{key}}}", str(val))
                                body = body.replace(f"{{{{{key}}}}}", str(val))

                            # 清理未匹配的变量 (只清理看起来像变量的，避免破坏 CSS/JS)
                            body = re.sub(r"\{([\w\s]+)\}", r"\1", body)

                            # 1. 注入像素
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

                            # 2. 替换点击链接
                            if campaign.track_clicks:
                                original_body_len = len(body)
                                body = re.sub(
                                    r'href\s*=\s*(["\'])(http[^"\']+)\1',
                                    replace_link,
                                    body,
                                )
                                if len(body) != original_body_len:
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

                        # 清理未匹配的变量 (只清理看起来像变量的，避免破坏 CSS/JS)
                        body = re.sub(r"\{([\w\s]+)\}", r"\1", body)

                        # 1. 注入像素
                        if campaign.track_opens:
                            if "</body>" in body:
                                body = body.replace("</body>", f"{pixel_html}</body>")
                                logger.info(
                                    f"Injecting pixel for {clean_to_address} (Aliyun)"
                                )
                            else:
                                body += pixel_html

                        # 2. 替换点击链接
                        if campaign.track_clicks:
                            original_body_len = len(body)
                            body = re.sub(
                                r'href\s*=\s*(["\'])(http[^"\']+)\1', replace_link, body
                            )
                            if len(body) != original_body_len:
                                logger.info(
                                    f"Link tracking injected for {clean_to_address} (Aliyun)"
                                )

                        # 阿里云: 如果 campaign.reply_to_address 有值，则认为开启回信地址功能 (True)
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
                    # 更新状态为 sent
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
                    logger.error(f"❌ FAILED: {clean_to_address} - {e}")
                    recipient.status = "failed"
                    recipient.error_message = str(e)
                    db.commit()

            # 更新进度
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
        db.close()


def pull_email_tracking_status():
    """
    后台任务：从腾讯云拉取邮件追踪状态 (打开/点击)
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
            return  # 没有配置腾讯云，跳过

        # 查询最近 7 天内待同步的腾讯云收件人
        from datetime import timedelta

        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        unresolved_filters = (
            models.CampaignRecipient.provider == "tencent",
            models.CampaignRecipient.message_id.isnot(None),
            models.CampaignRecipient.sent_at >= seven_days_ago,
            # 仍需要追踪更新的记录：sent/opened（clicked 视为终态）
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

        # 仅拉取存在未完成追踪记录的日期，减少无效 API 查询
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

                        # 打开：只记录首个打开时间
                        if user_opened and not recipient.opened_at:
                            recipient.opened_at = now
                            updated = True
                            if recipient.status == "sent":
                                recipient.status = "opened"

                        # 点击：点击优先级高于打开
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
                            # clicked 视为终态，避免后续重复检查
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
        scheduler.add_job(send_campaign_batch, "interval", minutes=1)
        # 添加 Pull Tracking 任务，每 5 分钟运行一次
        scheduler.add_job(pull_email_tracking_status, "interval", minutes=5)
        scheduler.start()
