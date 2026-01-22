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
import json
import traceback
import base64
import binascii

router = APIRouter()


# --- Pydantic Models ---
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
    reply_to_address: Optional[str] = None  # New Field


class SavedReplyToCreate(BaseModel):
    address: str


class TemplateImport(BaseModel):
    provider: str  # 'aliyun' or 'tencent'
    template_id: str


# --- Utils ---
def try_decode_base64(s):
    """尝试解码 Base64 字符串，处理填充和编码异常"""
    if not s or len(s) < 4:
        return s
    try:
        # 预处理：去掉空白字符，处理填充
        s = s.strip()
        # 尝试解码
        decoded_bytes = base64.b64decode(s, validate=False)
        return decoded_bytes.decode("utf-8")
    except:
        return s


# --- Routes ---


@router.post("/settings")
def update_settings(setting: SettingUpdate, db: Session = Depends(get_db)):
    existing = db.query(models.Setting).first()
    if not existing:
        existing = models.Setting()
        db.add(existing)

    if setting.access_key_id is not None:
        existing.access_key_id = setting.access_key_id
    if setting.access_key_secret is not None:
        existing.access_key_secret = setting.access_key_secret
    if setting.region_id is not None:
        existing.region_id = setting.region_id
    if setting.tencent_secret_id is not None:
        existing.tencent_secret_id = setting.tencent_secret_id
    if setting.tencent_secret_key is not None:
        existing.tencent_secret_key = setting.tencent_secret_key
    if setting.tencent_region is not None:
        existing.tencent_region = setting.tencent_region
    if setting.from_alias is not None:
        existing.from_alias = setting.from_alias

    db.commit()
    return {"message": "Settings updated"}


@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    return db.query(models.Setting).first()


@router.post("/contacts/upload")
async def upload_contacts(
    file: UploadFile = File(...),
    list_name: str = Form(...),
    db: Session = Depends(get_db),
):
    content = await file.read()
    try:
        contact_list = ContactService.process_csv(db, content, list_name)
        return {"id": contact_list.id, "count": contact_list.total_count}
    except Exception as e:
        print(f"Upload Error Detail: {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/contacts")
def get_contact_lists(db: Session = Depends(get_db)):
    return db.query(models.ContactList).all()


@router.delete("/contacts/{id}")
def delete_contact_list(id: int, db: Session = Depends(get_db)):
    contact_list = (
        db.query(models.ContactList).filter(models.ContactList.id == id).first()
    )
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
    db_template = (
        db.query(models.EmailTemplate).filter(models.EmailTemplate.id == id).first()
    )
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
    templates = db.query(models.EmailTemplate).all()
    # 确保返回给前端的是解码后的内容 (尤其是从云端同步回来的 Base64 模板)
    for t in templates:
        t.body = try_decode_base64(t.body)
    return templates


@router.post("/templates/import")
def import_template(data: TemplateImport, db: Session = Depends(get_db)):
    setting = db.query(models.Setting).first()
    if not setting:
        raise HTTPException(status_code=400, detail="请先在设置中配置 AccessKey")

    try:
        if data.provider == "aliyun":
            client = AliyunService.create_client(
                setting.access_key_id, setting.access_key_secret, setting.region_id
            )
            detail_res = AliyunService.desc_template(client, int(data.template_id))
            detail = detail_res.body
            title = detail.template_name
            subject = detail.template_subject
            body = detail.template_text

        elif data.provider == "tencent":
            from ..services.tencent_service import TencentService

            client = TencentService.create_client(
                setting.tencent_secret_id,
                setting.tencent_secret_key,
                setting.tencent_region,
            )
            detail_res = TencentService.get_template(client, int(data.template_id))
            detail_data = json.loads(detail_res.to_json_string())
            detail_content = detail_data.get("TemplateContent", {})
            title = (
                detail_content.get("TemplateName")
                or detail_data.get("TemplateName")
                or f"Tencent-{data.template_id}"
            )
            subject = detail_content.get("TemplateSubject", title)
            raw_body = (
                detail_content.get("Html") or detail_content.get("Text") or "No Content"
            )
            body = try_decode_base64(raw_body)
        else:
            raise HTTPException(status_code=400, detail="Unknown provider")

        existing = (
            db.query(models.EmailTemplate)
            .filter(
                models.EmailTemplate.provider == data.provider,
                models.EmailTemplate.provider_id == data.template_id,
            )
            .first()
        )

        if existing:
            existing.title = title
            existing.subject = subject
            existing.body = body
            db.commit()
            return {"message": "模板已更新", "title": title}
        else:
            new_t = models.EmailTemplate(
                title=title,
                subject=subject,
                body=body,
                from_alias=setting.from_alias,
                provider=data.provider,
                provider_id=data.template_id,
            )
            db.add(new_t)
            db.commit()
            return {"message": "模板已导入", "title": title}
    except Exception as e:
        print(f"Import Error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@router.post("/templates/sync")
def sync_templates(db: Session = Depends(get_db)):
    setting = db.query(models.Setting).first()
    if not setting:
        raise HTTPException(status_code=400, detail="请先在设置中配置 AccessKey")

    messages = []

    # --- 1. Aliyun Sync ---
    if setting.access_key_id and setting.access_key_secret:
        try:
            client = AliyunService.create_client(
                setting.access_key_id, setting.access_key_secret, setting.region_id
            )
            res = AliyunService.query_templates(client)
            if res.body.data and res.body.data.template:
                count = 0
                for t in res.body.data.template:
                    existing = (
                        db.query(models.EmailTemplate)
                        .filter(models.EmailTemplate.title == t.template_name)
                        .first()
                    )
                    detail_res = AliyunService.desc_template(client, int(t.template_id))
                    detail = detail_res.body
                    if not existing:
                        new_t = models.EmailTemplate(
                            title=detail.template_name,
                            subject=detail.template_subject,
                            body=detail.template_text,
                            from_alias=setting.from_alias,
                            provider="aliyun",
                            provider_id=str(t.template_id),
                        )
                        db.add(new_t)
                        count += 1
                    else:
                        existing.subject = detail.template_subject
                        existing.body = detail.template_text
                        existing.provider = "aliyun"
                        existing.provider_id = str(t.template_id)
                messages.append(f"阿里云同步 {count} 个")
        except Exception as e:
            print(f"Aliyun Sync Error: {e}")
            messages.append("阿里云同步失败")

    # --- 2. Tencent Sync ---
    if setting.tencent_secret_id and setting.tencent_secret_key:
        try:
            from ..services.tencent_service import TencentService

            client = TencentService.create_client(
                setting.tencent_secret_id,
                setting.tencent_secret_key,
                setting.tencent_region,
            )
            res = TencentService.query_templates(client)
            data = json.loads(res.to_json_string())
            templates_list = data.get("TemplatesMetadata", [])

            if templates_list:
                count = 0
                for t in templates_list:
                    template_id = t.get("TemplateID")
                    template_name = t.get("TemplateName")
                    try:
                        detail_res = TencentService.get_template(client, template_id)
                        detail_data = json.loads(detail_res.to_json_string())
                        detail_content = detail_data.get("TemplateContent", {})
                        existing = (
                            db.query(models.EmailTemplate)
                            .filter(models.EmailTemplate.title == template_name)
                            .first()
                        )

                        subject = detail_content.get("TemplateSubject", template_name)
                        raw_body = (
                            detail_content.get("Html")
                            or detail_content.get("Text")
                            or "No Content"
                        )
                        body = try_decode_base64(raw_body)

                        if not existing:
                            new_t = models.EmailTemplate(
                                title=template_name,
                                subject=subject,
                                body=body,
                                from_alias=setting.from_alias,
                                provider="tencent",
                                provider_id=str(template_id),
                            )
                            db.add(new_t)
                            count += 1
                        else:
                            existing.subject = subject
                            existing.body = body
                            existing.provider = "tencent"
                            existing.provider_id = str(template_id)
                    except Exception as e:
                        print(f"Failed to get details for template {template_id}: {e}")
                messages.append(f"腾讯云同步 {count} 个")
        except Exception as e:
            print(f"Tencent Sync Error Detail: {traceback.format_exc()}")
            messages.append(f"腾讯云同步失败: {str(e)}")

    db.commit()
    if not messages:
        if (setting.access_key_id and setting.access_key_secret) or (
            setting.tencent_secret_id and setting.tencent_secret_key
        ):
            return {"message": "同步完成。未发现新模板（请确认云端模板已审核通过）"}
        return {"message": "未配置任何云服务商，无法同步"}
    return {"message": " | ".join(messages)}


@router.get("/senders/sync")
def sync_senders(db: Session = Depends(get_db)):
    setting = db.query(models.Setting).first()
    if not setting:
        raise HTTPException(status_code=400, detail="请先在设置中配置 AccessKey")

    senders = []
    if setting.access_key_id and setting.access_key_secret:
        try:
            client = AliyunService.create_client(
                setting.access_key_id, setting.access_key_secret, setting.region_id
            )
            res = AliyunService.query_mail_address(client)
            if res.body.data and res.body.data.mail_address:
                for addr in res.body.data.mail_address:
                    status_map = {"0": "正常", "1": "冻结", "2": "待验证"}
                    status_str = status_map.get(
                        str(addr.account_status), str(addr.account_status)
                    )
                    senders.append(
                        {
                            "email": addr.account_name,
                            "provider": "aliyun",
                            "status": status_str,
                            "label": f"[阿里云] {addr.account_name} ({status_str})",
                            "reply_address": addr.reply_address,  # 同步阿里云的回信地址
                        }
                    )
        except Exception as e:
            print(f"Aliyun Senders Error: {e}")

    if setting.tencent_secret_id and setting.tencent_secret_key:
        try:
            from ..services.tencent_service import TencentService

            client = TencentService.create_client(
                setting.tencent_secret_id,
                setting.tencent_secret_key,
                setting.tencent_region,
            )
            res = TencentService.query_senders(client)
            data = json.loads(res.to_json_string())
            if "EmailIdentities" in data and data["EmailIdentities"]:
                for identity in data["EmailIdentities"]:
                    email = identity.get("IdentityName")
                    senders.append(
                        {
                            "email": email,
                            "provider": "tencent",
                            "status": "已验证",
                            "label": f"[腾讯云] {email}",
                        }
                    )
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
        campaign.from_alias,
        campaign.provider,
        campaign.reply_to_address,
    )


# --- Saved Reply-To Endpoints ---
@router.get("/settings/reply_tos")
def get_saved_reply_tos(db: Session = Depends(get_db)):
    return (
        db.query(models.SavedReplyTo)
        .order_by(models.SavedReplyTo.created_at.desc())
        .all()
    )


@router.post("/settings/reply_tos")
def add_saved_reply_to(data: SavedReplyToCreate, db: Session = Depends(get_db)):
    existing = (
        db.query(models.SavedReplyTo)
        .filter(models.SavedReplyTo.address == data.address)
        .first()
    )
    if existing:
        return existing

    new_addr = models.SavedReplyTo(address=data.address)
    db.add(new_addr)
    db.commit()
    db.refresh(new_addr)
    return new_addr


@router.get("/campaigns")
def get_campaigns(db: Session = Depends(get_db)):
    return db.query(models.Campaign).all()


@router.post("/campaigns/{id}/start")
def start_campaign(id: int, db: Session = Depends(get_db)):
    campaign = db.query(models.Campaign).filter(models.Campaign.id == id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if (
        campaign.scheduled_start_time
        and campaign.scheduled_start_time > datetime.utcnow()
    ):
        campaign.status = "scheduled"
        db.commit()
        return {"status": "scheduled", "start_time": campaign.scheduled_start_time}
    else:
        campaign.status = "sending"
        db.commit()
        try:
            scheduler.add_job(send_campaign_batch, "date")
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
