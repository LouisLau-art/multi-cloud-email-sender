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
class SettingUpdate(BaseModel):
    access_key_id: str
    access_key_secret: str
    region_id: str = "cn-hangzhou"
    tencent_secret_id: Optional[str] = None
    tencent_secret_key: Optional[str] = None
    tencent_region: str = "ap-guangzhou"
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
    
    try:
        client = AliyunService.create_client(setting.access_key_id, setting.access_key_secret, setting.region_id)
        res = AliyunService.query_templates(client)
        al_templates = res.body.data.template
        
        if not al_templates:
            return {"message": "阿里云上没有发现模板"}

        sync_count = 0
        for t in al_templates:
            existing = db.query(models.EmailTemplate).filter(models.EmailTemplate.title == t.template_name).first()
            detail_res = AliyunService.desc_template(client, int(t.template_id))
            detail = detail_res.body
            
            if not existing:
                new_t = models.EmailTemplate(
                    title=detail.template_name,
                    subject=detail.template_subject,
                    body=detail.template_text,
                    from_alias=setting.from_alias # 默认使用全局别名
                )
                db.add(new_t)
                sync_count += 1
            else:
                existing.subject = detail.template_subject
                existing.body = detail.template_text
                sync_count += 1
        
        db.commit()
        return {"message": f"成功同步 {sync_count} 个模板"}
    except Exception as e:
        error_msg = str(e)
        if "SSL" in error_msg or "Connection" in error_msg or "time" in error_msg.lower():
            raise HTTPException(status_code=500, detail="连接阿里云超时。这通常是本地网络问题，请稍后重试，或直接使用“新建模板”手动录入。")
        raise HTTPException(status_code=500, detail=f"同步失败: {error_msg}")

@router.get("/senders/sync")
def sync_senders(db: Session = Depends(get_db)):
    setting = db.query(models.Setting).first()
    if not setting:
        raise HTTPException(status_code=400, detail="请先在设置中配置 AccessKey")
    
    senders = []
    try:
        if setting.access_key_id:
            client = AliyunService.create_client(setting.access_key_id, setting.access_key_secret, setting.region_id)
            res = AliyunService.query_mail_address(client)
            if res.body.data and res.body.data.mail_address:
                for addr in res.body.data.mail_address:
                    status_map = {'0': '正常', '1': '冻结', '2': '待验证'}
                    status_str = status_map.get(str(addr.account_status), str(addr.account_status))
                    senders.append({"email": addr.account_name, "provider": "aliyun", "status": status_str})
    except Exception as e:
        print(f"Sync senders failed: {e}")
    
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