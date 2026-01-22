from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from ..core.database import get_db
from ..models import models
from ..services.campaign_service import ContactService, CampaignService
from ..services.aliyun_service import AliyunService
from pydantic import BaseModel
from ..core.scheduler import scheduler, send_campaign_batch

router = APIRouter()

# --- Pydantic Models ---
import json
import traceback

class SettingUpdate(BaseModel):
    access_key_id: Optional[str] = None
    access_key_secret: Optional[str] = None
    region_id: str = "cn-hangzhou"
    tencent_secret_id: Optional[str] = None
    tencent_secret_key: Optional[str] = None
    tencent_region: str = "ap-hongkong"
    from_alias: Optional[str] = None

class TemplateCreate(BaseModel):
    title: str
    subject: str
    body: str
    from_alias: str

class TemplateUpdate(BaseModel):
    title: str
    subject: str
    body: str
    from_alias: str

class CampaignCreate(BaseModel):
    name: str
    template_id: int
    list_id: int
    account_name: str
    provider: str = "aliyun"
    batch_size: int = 2000
    interval_minutes: int = 15
    scheduled_start_time: Optional[datetime] = None
    from_alias: Optional[str] = None

# --- Routes ---

@router.post("/settings")
def update_settings(setting: SettingUpdate, db: Session = Depends(get_db)):
    existing = db.query(models.Setting).first()
    if not existing:
        existing = models.Setting()
        db.add(existing)
    
    existing.access_key_id = setting.access_key_id
    existing.access_key_secret = setting.access_key_secret
    existing.region_id = setting.region_id
    existing.tencent_secret_id = setting.tencent_secret_id
    existing.tencent_secret_key = setting.tencent_secret_key
    existing.tencent_region = setting.tencent_region
    existing.from_alias = setting.from_alias
    
    db.commit()
    return {"message": "Settings updated"}

@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    return db.query(models.Setting).first()

@router.post("/contacts/upload")
async def upload_contacts(file: UploadFile = File(...), list_name: str = Form(...), db: Session = Depends(get_db)):
    content = await file.read()
    try:
        contact_list = ContactService.process_csv(db, content, list_name)
        return {"id": contact_list.id, "count": contact_list.total_count}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/contacts")
def get_contact_lists(db: Session = Depends(get_db)):
    return db.query(models.ContactList).all()

@router.delete("/contacts/{id}")
def delete_contact_list(id: int, db: Session = Depends(get_db)):
    contact_list = db.query(models.ContactList).filter(models.ContactList.id == id).first()
    if not contact_list:
        raise HTTPException(status_code=404, detail="Contact list not found")
    db.delete(contact_list)
    db.commit()
    return {"status": "deleted"}

@router.post("/templates")
def create_template(template: TemplateCreate, db: Session = Depends(get_db)):
    db_template = models.EmailTemplate(**template.dict())
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

@router.put("/templates/{id}")
def update_template(id: int, template: TemplateUpdate, db: Session = Depends(get_db)):
    db_template = db.query(models.EmailTemplate).filter(models.EmailTemplate.id == id).first()
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    db_template.title = template.title
    db_template.subject = template.subject
    db_template.body = template.body
    db_template.from_alias = template.from_alias
    db.commit()
    return db_template

@router.get("/templates")
def get_templates(db: Session = Depends(get_db)):
    return db.query(models.EmailTemplate).all()

@router.post("/templates/sync")
def sync_templates(db: Session = Depends(get_db)):
    setting = db.query(models.Setting).first()
    if not setting:
        raise HTTPException(status_code=400, detail="请先在设置中配置 AccessKey")
    
    # --- DEBUG: Print Settings to Console ---
    print(f"DEBUG SETTINGS: AliID={setting.access_key_id}, TenID={setting.tencent_secret_id}, TenRegion={setting.tencent_region}")
    
    messages = []
    
    # --- 1. Aliyun Sync ---
    if setting.access_key_id and setting.access_key_secret:
        try:
            client = AliyunService.create_client(setting.access_key_id, setting.access_key_secret, setting.region_id)
            res = AliyunService.query_templates(client)
            if res.body.data and res.body.data.template:
                count = 0
                for t in res.body.data.template:
                    existing = db.query(models.EmailTemplate).filter(models.EmailTemplate.title == t.template_name).first()
                    detail_res = AliyunService.desc_template(client, int(t.template_id))
                    detail = detail_res.body
                    
                    if not existing:
                        new_t = models.EmailTemplate(
                            title=detail.template_name,
                            subject=detail.template_subject,
                            body=detail.template_text,
                            from_alias=setting.from_alias
                        )
                        db.add(new_t)
                        count += 1
                    else:
                        existing.subject = detail.template_subject
                        existing.body = detail.template_text
                messages.append(f"阿里云同步 {count} 个")
        except Exception as e:
            print(f"Aliyun Sync Error: {e}")
            messages.append("阿里云同步失败")

    # --- 2. Tencent Sync ---
    if setting.tencent_secret_id and setting.tencent_secret_key:
        try:
            from ..services.tencent_service import TencentService
            client = TencentService.create_client(setting.tencent_secret_id, setting.tencent_secret_key, setting.tencent_region)
            res = TencentService.query_templates(client)
            
            # Fix: Parse Tencent response as JSON dict
            data = json.loads(res.to_json_string())
            
            if "Templates" in data and data["Templates"]:
                count = 0
                for t in data["Templates"]:
                    # t is a dict: {'TemplateID': ..., 'TemplateName': ...}
                    template_id = t.get('TemplateID')
                    template_name = t.get('TemplateName')
                    
                    detail_res = TencentService.get_template(client, template_id)
                    detail_data = json.loads(detail_res.to_json_string())
                    detail_content = detail_data.get('TemplateContent', {})
                    
                    existing = db.query(models.EmailTemplate).filter(models.EmailTemplate.title == template_name).first()
                    
                    # Fallback for Subject (Standard SES templates might not store it)
                    subject = "来自腾讯云的模板"
                    if 'TemplateSubject' in detail_content:
                         subject = detail_content['TemplateSubject']
                    
                    body = detail_content.get('Html', 'No Content')
                    
                    if not existing:
                        new_t = models.EmailTemplate(
                            title=template_name,
                            subject=subject,
                            body=body,
                            from_alias=setting.from_alias
                        )
                        db.add(new_t)
                        count += 1
                    else:
                        existing.body = body
                messages.append(f"腾讯云同步 {count} 个")
        except Exception as e:
            print(f"Tencent Sync Error Detail: {traceback.format_exc()}")
            messages.append(f"腾讯云同步失败: {str(e)}")

    db.commit()
    if not messages:
        # Check if any provider was configured but no templates found
        if (setting.access_key_id and setting.access_key_secret) or \
           (setting.tencent_secret_id and setting.tencent_secret_key):
             return {"message": "同步完成。未发现新模板（请确认云端模板已审核通过）"}
        return {"message": "未配置任何云服务商，无法同步"}
    return {"message": " | ".join(messages)}

@router.get("/senders/sync")
def sync_senders(db: Session = Depends(get_db)):
    setting = db.query(models.Setting).first()
    if not setting:
        raise HTTPException(status_code=400, detail="请先在设置中配置 AccessKey")
    
    senders = []
    
    # --- Aliyun ---
    if setting.access_key_id and setting.access_key_secret:
        try:
            client = AliyunService.create_client(setting.access_key_id, setting.access_key_secret, setting.region_id)
            res = AliyunService.query_mail_address(client)
            if res.body.data and res.body.data.mail_address:
                for addr in res.body.data.mail_address:
                    status_map = {'0': '正常', '1': '冻结', '2': '待验证'}
                    status_str = status_map.get(str(addr.account_status), str(addr.account_status))
                    senders.append({
                        "email": addr.account_name, 
                        "provider": "aliyun", 
                        "status": status_str,
                        "label": f"[阿里云] {addr.account_name} ({status_str})"
                    })
        except Exception as e:
            print(f"Aliyun Senders Error: {e}")

    # --- Tencent ---
    if setting.tencent_secret_id and setting.tencent_secret_key:
        try:
            from ..services.tencent_service import TencentService
            client = TencentService.create_client(setting.tencent_secret_id, setting.tencent_secret_key, setting.tencent_region)
            res = TencentService.query_senders(client)
            
            # Fix: Parse Tencent response as JSON dict
            data = json.loads(res.to_json_string())
            
            if "EmailIdentities" in data and data["EmailIdentities"]:
                for identity in data["EmailIdentities"]:
                    # identity is a dict: {'IdentityName': '...', 'IdentityType': ...}
                    email = identity.get('IdentityName')
                    senders.append({
                        "email": email,
                        "provider": "tencent",
                        "status": "已验证", 
                        "label": f"[腾讯云] {email}"
                    })
        except Exception as e:
            print(f"Tencent Senders Error Detail: {traceback.format_exc()}")
    
    return senders

@router.post("/campaigns")
def create_campaign(campaign: CampaignCreate, db: Session = Depends(get_db)):
    print(f"Creating campaign with data: {campaign}")
    return CampaignService.create_campaign(
        db, 
        campaign.name, 
        campaign.template_id, 
        campaign.list_id, 
        campaign.account_name,
        campaign.batch_size,
        campaign.interval_minutes,
        campaign.scheduled_start_time,
        campaign.from_alias
    )

@router.get("/campaigns")
def get_campaigns(db: Session = Depends(get_db)):
    return db.query(models.Campaign).all()

@router.post("/campaigns/{id}/start")
def start_campaign(id: int, db: Session = Depends(get_db)):
    campaign = db.query(models.Campaign).filter(models.Campaign.id == id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if campaign.scheduled_start_time and campaign.scheduled_start_time > datetime.utcnow():
        campaign.status = "scheduled"
        db.commit()
        return {"status": "scheduled", "start_time": campaign.scheduled_start_time}
    else:
        campaign.status = "sending"
        db.commit()
        try:
            scheduler.add_job(send_campaign_batch, 'date')
        except Exception as e:
            print(f"Trigger error: {e}")
        return {"status": "started"}

@router.post("/campaigns/{id}/stop")
def stop_campaign(id: int, db: Session = Depends(get_db)):
    campaign = db.query(models.Campaign).filter(models.Campaign.id == id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.status = "paused"
    db.commit()
    return {"status": "paused"}

@router.delete("/campaigns/{id}")
def delete_campaign(id: int, db: Session = Depends(get_db)):
    campaign = db.query(models.Campaign).filter(models.Campaign.id == id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    db.delete(campaign)
    db.commit()
    return {"status": "deleted"}