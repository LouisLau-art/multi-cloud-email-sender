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
    db = get_db_session()
    try:
        # 0. 检查计划任务
        scheduled_campaigns = db.query(models.Campaign).filter(models.Campaign.status == "scheduled").all()
        for sc in scheduled_campaigns:
            if sc.scheduled_start_time and datetime.utcnow() >= sc.scheduled_start_time:
                sc.status = "sending"
                db.commit()

        # 1. 查找运行中的任务
        active_campaigns = db.query(models.Campaign).filter(models.Campaign.status == "sending").all()
        
        for campaign in active_campaigns:
            setting = db.query(models.Setting).first()
            if not setting: continue
                
            template = db.query(models.EmailTemplate).filter(models.EmailTemplate.id == campaign.template_id).first()
            
            # 间隔检查
            last_batch = (db.query(models.CampaignBatch)
                .filter(models.CampaignBatch.campaign_id == campaign.id)
                .order_by(models.CampaignBatch.sent_at.desc())
                .first())
            
            if last_batch:
                time_since_last = (datetime.utcnow() - last_batch.sent_at).total_seconds() / 60
                if time_since_last < campaign.interval_minutes: continue 

            # 获取联系人
            contacts = (db.query(models.Contact)
                .filter(models.Contact.list_id == campaign.list_id)
                .offset(campaign.sent_count)
                .limit(campaign.batch_size)
                .all())
                
            if not contacts:
                campaign.status = "completed"
                db.commit()
                continue
            
            logger.info(f"Campaign {campaign.name} ({campaign.provider}): Sending batch of {len(contacts)}...")
            
            ali_client = None
            if campaign.provider == 'aliyun':
                ali_client = AliyunService.create_client(setting.access_key_id, setting.access_key_secret, setting.region_id)

            for i, contact in enumerate(contacts):
                db.refresh(campaign)
                if campaign.status != 'sending': break

                # 准备变量
                vars_map = json.loads(contact.extra_vars) if contact.extra_vars else {}
                if contact.name:
                    vars_map['Name'] = contact.name
                    vars_map['name'] = contact.name
                    vars_map['username'] = contact.name
                vars_map['Email'] = contact.email or ""
                
                # 标题替换 (关键：同时支持 {key} 和 {{key}})
                subject = template.subject
                for key, val in vars_map.items():
                    subject = subject.replace(f"{{{key}}}", str(val))
                    subject = subject.replace(f"{{{{{key}}}}}", str(val))
                
                real_from_alias = (campaign.from_alias or template.from_alias or setting.from_alias or campaign.account_name.split('@')[0])
                clean_to_address = contact.email.split()[0].strip()
                
                try:
                    if campaign.provider == 'tencent':
                        if template.provider == 'tencent' and template.provider_id:
                            # 腾讯云模板模式
                            TencentService.send_mail(
                                setting.tencent_secret_id, setting.tencent_secret_key, setting.tencent_region,
                                campaign.account_name, clean_to_address, subject, "", 
                                from_alias=real_from_alias, template_id=template.provider_id,
                                template_params=json.dumps(vars_map)
                            )
                        else:
                            # 腾讯云 HTML 模式
                            body = template.body
                            for key, val in vars_map.items():
                                body = body.replace(f"{{{key}}}", str(val))
                                body = body.replace(f"{{{{{key}}}}}", str(val))
                            TencentService.send_mail(
                                setting.tencent_secret_id, setting.tencent_secret_key, setting.tencent_region,
                                campaign.account_name, clean_to_address, subject, body, from_alias=real_from_alias
                            )
                    elif campaign.provider == 'aliyun':
                        body = template.body
                        for key, val in vars_map.items():
                            body = body.replace(f"{{{key}}}", str(val))
                            body = body.replace(f"{{{{{key}}}}}", str(val))
                        AliyunService.single_send_mail(
                            ali_client, campaign.account_name, True, 1, clean_to_address, subject, body, real_from_alias
                        )
                    
                    logger.info(f"[{i+1}/{len(contacts)}] Sent to {clean_to_address}")
                    time.sleep(random.uniform(0.2, 1.0))
                except Exception as e:
                    logger.error(f"❌ FAILED: {clean_to_address} - {e}")

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