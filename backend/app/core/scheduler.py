from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from .database import SessionLocal
from ..models import models
from ..services.aliyun_service import AliyunService
from ..services.tencent_service import TencentService
import logging
import json
import time
from datetime import datetime
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

def get_db_session():
    return SessionLocal()

def send_campaign_batch():
    """
    核心调度任务：
    1. 查找状态为 'sending' 的任务
    2. 获取下一批未发送的联系人
    3. 循环发送 (支持多云分流)
    """
    db = get_db_session()
    try:
        # 0. 检查是否有计划任务到期
        scheduled_campaigns = db.query(models.Campaign).filter(models.Campaign.status == "scheduled").all()
        for sc in scheduled_campaigns:
            if sc.scheduled_start_time and datetime.utcnow() >= sc.scheduled_start_time:
                sc.status = "sending"
                db.commit()
                logger.info(f"Scheduled campaign {sc.name} started automatically.")

        # 1. 查找正在运行的任务
        active_campaigns = db.query(models.Campaign).filter(models.Campaign.status == "sending").all()
        
        if not active_campaigns:
            return

        for campaign in active_campaigns:
            setting = db.query(models.Setting).first()
            if not setting:
                logger.error("No settings found!")
                continue
                
            template = db.query(models.EmailTemplate).filter(models.EmailTemplate.id == campaign.template_id).first()
            
            # Check time interval
            last_batch = db.query(models.CampaignBatch)\
                .filter(models.CampaignBatch.campaign_id == campaign.id)\
                .order_by(models.CampaignBatch.sent_at.desc())\
                .first()
            
            if last_batch:
                time_since_last = (datetime.utcnow() - last_batch.sent_at).total_seconds() / 60
                if time_since_last < campaign.interval_minutes:
                    continue 

            # 获取下一批联系人
            contacts = db.query(models.Contact)\
                .filter(models.Contact.list_id == campaign.list_id)\
                .offset(campaign.sent_count)\
                .limit(campaign.batch_size)\
                .all()
                
            if not contacts:
                campaign.status = "completed"
                db.commit()
                continue
            
            logger.info(f"Campaign {campaign.name} ({campaign.provider}): Sending batch of {len(contacts)}...")
            
            # 初始化阿里云 Client (如果是阿里云任务)
            ali_client = None
            if campaign.provider == 'aliyun':
                try:
                    ali_client = AliyunService.create_client(setting.access_key_id, setting.access_key_secret, setting.region_id)
                except Exception as e:
                    logger.error(f"Aliyun client error: {e}")
                    continue

            for i, contact in enumerate(contacts):
                # --- 关键修正：实时检查任务状态 ---
                # 每发 1 封就检查一次数据库状态，实现“秒级暂停”
                # 为了性能，也可以每 10 封检查一次 (if i % 10 == 0)
                db.expire(campaign) # 强制刷新 session 中的对象
                db.refresh(campaign)
                if campaign.status != 'sending':
                    logger.info(f"Campaign {campaign.name} stopped/paused by user. Breaking loop.")
                    break

                # 动态替换变量 (仅准备数据，暂不替换字符串)
                vars_map = json.loads(contact.extra_vars) if contact.extra_vars else {}
                if contact.name:
                    vars_map['Name'] = contact.name
                    vars_map['name'] = contact.name
                    vars_map['UserName'] = contact.name
                    vars_map['username'] = contact.name
                vars_map['Email'] = contact.email or ""
                
                # 确定发件人昵称
                real_from_alias = (
                    campaign.from_alias or 
                    template.from_alias or 
                    setting.from_alias or 
                    campaign.account_name.split('@')[0]
                )
                clean_to_address = contact.email.split()[0].strip()
                
                # 腾讯云逻辑
                if campaign.provider == 'tencent':
                    logger.info(f"DEBUG Tencent Check: TplProvider={template.provider}, TplID={template.provider_id}") # Debug Log
                    try:
                        # 模式A：腾讯云原生模板 (Template Mode)
                        if template.provider == 'tencent' and template.provider_id:
                            # 关键修复：不要做本地字符串替换！直接传变量给腾讯云
                            # 腾讯云模板使用 {{key}}，我们只需传 {"key": "value"}
                            
                            # 构造 Subject (如果模板没有默认标题，或者我们想覆盖)
                            # 注意：腾讯云 Template 接口的 Subject 参数优先级高于模板自带 Subject
                            # 这里我们不对 Subject 做本地替换，除非我们想强制覆盖模板标题
                            # 为了保险，我们还是用模板原标题，不做任何处理
                            final_subject = template.subject
                            
                            template_params_json = json.dumps(vars_map)
                            
                            TencentService.send_mail(
                                secret_id=setting.tencent_secret_id,
                                secret_key=setting.tencent_secret_key,
                                region=setting.tencent_region,
                                from_email=campaign.account_name,
                                to_email=clean_to_address,
                                subject=final_subject, 
                                html_body="", 
                                from_alias=real_from_alias,
                                template_id=template.provider_id,
                                template_params=template_params_json
                            )
                            logger.info(f"[{i+1}/{len(contacts)}] Sent (Tencent Template) to {clean_to_address}")
                            
                        # 模式B：自定义 HTML (Custom Mode)
                        else:
                            # 需要本地替换
                            subject = template.subject
                            body = template.body
                            for key, val in vars_map.items():
                                subject = subject.replace(f"{{{key}}}", str(val))
                                body = body.replace(f"{{{key}}}", str(val))
                                
                            TencentService.send_mail(
                                secret_id=setting.tencent_secret_id,
                                secret_key=setting.tencent_secret_key,
                                region=setting.tencent_region,
                                from_email=campaign.account_name,
                                to_email=clean_to_address,
                                subject=subject,
                                html_body=body,
                                from_alias=real_from_alias
                            )
                            logger.info(f"[{i+1}/{len(contacts)}] Sent (Tencent HTML) to {clean_to_address}")

                        campaign.sent_count += 1
                        time.sleep(random.uniform(0.2, 1.0))
                    except Exception as e:
                        logger.error(f"❌ FAILED (Tencent): {clean_to_address} - {e}")

                # 阿里云逻辑
                elif campaign.provider == 'aliyun':
                    try:
                        # 阿里云目前统一使用本地替换模式
                        subject = template.subject
                        body = template.body
                        for key, val in vars_map.items():
                            subject = subject.replace(f"{{{key}}}", str(val))
                            body = body.replace(f"{{{key}}}", str(val))
                            
                        AliyunService.single_send_mail(
                            client=ali_client,
                            account_name=campaign.account_name,
                            reply_to_address=True,
                            address_type=1,
                            to_address=clean_to_address,
                            subject=subject,
                            html_body=body,
                            from_alias=real_from_alias
                        )
                        campaign.sent_count += 1
                        logger.info(f"[{i+1}/{len(contacts)}] Sent (Aliyun) to {clean_to_address}")
                        time.sleep(random.uniform(0.2, 1.0))
                    except Exception as e:
                        logger.error(f"❌ FAILED (Aliyun): {clean_to_address} - {e}")
            
            # 更新进度
            campaign.sent_count += len(contacts)
            if campaign.sent_count >= campaign.total_recipients:
                campaign.status = "completed"
            
            db.add(models.CampaignBatch(campaign_id=campaign.id, status="sent", recipient_count=len(contacts), sent_at=datetime.utcnow()))
            db.commit()
    finally:
        db.close()

def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(send_campaign_batch, 'interval', minutes=1)
        scheduler.start()