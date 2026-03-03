import base64
import json
import logging
import os
from datetime import datetime
from types import SimpleNamespace
from typing import Optional

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.scheduler import scheduler, send_campaign_batch
from ..core.security import (
    ADMIN_SESSION_COOKIE,
    build_admin_session_token,
    decrypt_secret,
    encrypt_secret,
    hash_password,
    verify_admin_session_token,
    verify_password,
)
from ..models import models
from ..services.aliyun_service import AliyunService
from ..services.campaign_service import CampaignService, ContactService

logger = logging.getLogger(__name__)
AUTH_ENABLED = os.getenv("ENABLE_ADMIN_AUTH", "0").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

public_router = APIRouter()


def _auth_cookie_settings(request: Request) -> dict:
    secure = request.url.scheme == "https"
    # When frontend and backend are served from same host, Lax works and avoids
    # browser restrictions around cross-site cookies in internal environments.
    return {
        "httponly": True,
        "secure": secure,
        "samesite": "lax",
        "max_age": 60 * 60 * 24 * 7,
        "path": "/",
    }


def _get_or_create_setting(db: Session) -> models.Setting:
    setting = db.query(models.Setting).first()
    if setting:
        return setting
    setting = models.Setting()
    db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting


def _is_bootstrapped(setting: Optional[models.Setting]) -> bool:
    return bool(setting and setting.admin_password_hash and setting.admin_password_salt)


def _sanitize_setting(setting: Optional[models.Setting]):
    if not setting:
        return None
    return {
        "id": setting.id,
        "region_id": setting.region_id,
        "tencent_region": setting.tencent_region,
        "track_domain": setting.track_domain,
        "from_alias": setting.from_alias,
        "has_access_key_id": bool(setting.access_key_id),
        "has_access_key_secret": bool(setting.access_key_secret),
        "has_tencent_secret_id": bool(setting.tencent_secret_id),
        "has_tencent_secret_key": bool(setting.tencent_secret_key),
        "updated_at": setting.updated_at,
    }


def _decrypt_account(account: models.CloudAccount) -> models.CloudAccount:
    if not account:
        return account
    return SimpleNamespace(
        id=account.id,
        provider=account.provider,
        name=account.name,
        access_key_id=account.access_key_id,
        access_key_secret=decrypt_secret(account.access_key_secret),
        region_id=account.region_id,
        tencent_secret_id=account.tencent_secret_id,
        tencent_secret_key=decrypt_secret(account.tencent_secret_key),
        tencent_region=account.tencent_region,
        from_alias=account.from_alias,
        enabled=account.enabled,
    )


def serialize_cloud_account(account: models.CloudAccount):
    if not account:
        return None
    return {
        "id": account.id,
        "provider": account.provider,
        "name": account.name,
        "access_key_id": account.access_key_id,
        "region_id": account.region_id,
        "tencent_secret_id": account.tencent_secret_id,
        "tencent_region": account.tencent_region,
        "from_alias": account.from_alias,
        "enabled": bool(account.enabled),
        "has_access_key_secret": bool(account.access_key_secret),
        "has_tencent_secret_key": bool(account.tencent_secret_key),
        "created_at": account.created_at,
        "updated_at": account.updated_at,
    }


def _resolve_active_cloud_account_or_400(
    db: Session, account_id: Optional[int], provider: str
) -> models.CloudAccount:
    provider = (provider or "").lower().strip()
    if account_id:
        account = (
            db.query(models.CloudAccount)
            .filter(models.CloudAccount.id == account_id)
            .first()
        )
        if not account:
            raise HTTPException(status_code=400, detail="Cloud account not found")
        if account.provider != provider:
            raise HTTPException(
                status_code=400,
                detail="Template/provider/account mismatch",
            )
        if not account.enabled:
            raise HTTPException(status_code=400, detail="Cloud account is disabled")
        return account

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
        return accounts[0]
    if len(accounts) > 1:
        raise HTTPException(status_code=400, detail="Please select cloud account")
    raise HTTPException(status_code=400, detail="Cloud account not configured")


def try_decode_base64(s: str):
    if not s or len(s) < 4:
        return s
    try:
        decoded_bytes = base64.b64decode(s.strip(), validate=False)
        return decoded_bytes.decode("utf-8")
    except Exception:
        return s


def require_admin_session(
    db: Session = Depends(get_db),
    session_token: Optional[str] = Cookie(default=None, alias=ADMIN_SESSION_COOKIE),
):
    if not AUTH_ENABLED:
        return True
    setting = db.query(models.Setting).first()
    if not _is_bootstrapped(setting):
        raise HTTPException(status_code=401, detail="Admin password not initialized")
    if not verify_admin_session_token(session_token, setting.admin_password_hash):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


router = APIRouter(dependencies=[Depends(require_admin_session)])


# --- Auth / Health (public) ---
class AuthPayload(BaseModel):
    password: str = Field(min_length=8, max_length=128)


@public_router.get("/auth/status")
def auth_status(
    db: Session = Depends(get_db),
    session_token: Optional[str] = Cookie(default=None, alias=ADMIN_SESSION_COOKIE),
):
    if not AUTH_ENABLED:
        return {
            "bootstrap_required": False,
            "authenticated": True,
            "auth_enabled": False,
        }

    setting = db.query(models.Setting).first()
    bootstrap_required = not _is_bootstrapped(setting)
    authenticated = False
    if not bootstrap_required and setting:
        authenticated = verify_admin_session_token(session_token, setting.admin_password_hash)
    return {
        "bootstrap_required": bootstrap_required,
        "authenticated": authenticated,
        "auth_enabled": True,
    }


@public_router.post("/auth/bootstrap")
def bootstrap_auth(payload: AuthPayload, request: Request, response: Response, db: Session = Depends(get_db)):
    if not AUTH_ENABLED:
        return {"status": "disabled", "auth_enabled": False}

    setting = _get_or_create_setting(db)
    if _is_bootstrapped(setting):
        raise HTTPException(status_code=409, detail="Already initialized")
    password_hash, salt = hash_password(payload.password)
    setting.admin_password_hash = password_hash
    setting.admin_password_salt = salt
    db.commit()

    response.set_cookie(
        key=ADMIN_SESSION_COOKIE,
        value=build_admin_session_token(password_hash),
        **_auth_cookie_settings(request),
    )
    return {"status": "ok"}


@public_router.post("/auth/login")
def login_auth(payload: AuthPayload, request: Request, response: Response, db: Session = Depends(get_db)):
    if not AUTH_ENABLED:
        return {"status": "disabled", "auth_enabled": False}

    setting = db.query(models.Setting).first()
    if not _is_bootstrapped(setting):
        raise HTTPException(status_code=400, detail="Admin password not initialized")
    if not verify_password(payload.password, setting.admin_password_hash, setting.admin_password_salt):
        raise HTTPException(status_code=401, detail="Wrong password")

    response.set_cookie(
        key=ADMIN_SESSION_COOKIE,
        value=build_admin_session_token(setting.admin_password_hash),
        **_auth_cookie_settings(request),
    )
    return {"status": "ok"}


@public_router.post("/auth/logout")
def logout_auth(response: Response):
    if not AUTH_ENABLED:
        return {"status": "disabled", "auth_enabled": False}

    response.delete_cookie(key=ADMIN_SESSION_COOKIE, path="/")
    return {"status": "ok"}


@public_router.get("/healthz")
def healthz():
    return {"status": "ok", "scheduler_running": scheduler.running}


@public_router.get("/readyz")
def readyz(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ready"}


# --- Pydantic Models ---
class SettingUpdate(BaseModel):
    access_key_id: Optional[str] = None
    access_key_secret: Optional[str] = None
    region_id: str = "cn-hangzhou"
    tencent_secret_id: Optional[str] = None
    tencent_secret_key: Optional[str] = None
    tencent_region: str = "ap-hongkong"
    track_domain: Optional[str] = None
    from_alias: Optional[str] = None


class TemplateCreate(BaseModel):
    title: str
    subject: str
    body: str
    from_alias: str
    provider: str = "local"
    account_id: Optional[int] = None


class TemplateUpdate(BaseModel):
    title: str
    subject: str
    body: str
    from_alias: str
    provider: Optional[str] = None
    account_id: Optional[int] = None


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
    reply_to_address: Optional[str] = None
    account_id: Optional[int] = None
    track_opens: bool = True
    track_clicks: bool = True


class SavedReplyToCreate(BaseModel):
    address: str


class TemplateImport(BaseModel):
    provider: str
    template_id: str
    account_id: Optional[int] = None


class CloudAccountCreate(BaseModel):
    provider: str
    name: str
    access_key_id: Optional[str] = None
    access_key_secret: Optional[str] = None
    region_id: Optional[str] = "cn-hangzhou"
    tencent_secret_id: Optional[str] = None
    tencent_secret_key: Optional[str] = None
    tencent_region: Optional[str] = "ap-hongkong"
    from_alias: Optional[str] = None
    enabled: bool = True


class CloudAccountUpdate(BaseModel):
    name: Optional[str] = None
    access_key_id: Optional[str] = None
    access_key_secret: Optional[str] = None
    region_id: Optional[str] = None
    tencent_secret_id: Optional[str] = None
    tencent_secret_key: Optional[str] = None
    tencent_region: Optional[str] = None
    from_alias: Optional[str] = None
    enabled: Optional[bool] = None


# --- Protected Routes ---
@router.post("/settings")
def update_settings(setting: SettingUpdate, db: Session = Depends(get_db)):
    existing = _get_or_create_setting(db)

    if setting.access_key_id is not None:
        existing.access_key_id = setting.access_key_id.strip()
    if setting.access_key_secret is not None:
        existing.access_key_secret = encrypt_secret(setting.access_key_secret)
    if setting.region_id is not None:
        existing.region_id = setting.region_id
    if setting.tencent_secret_id is not None:
        existing.tencent_secret_id = setting.tencent_secret_id.strip()
    if setting.tencent_secret_key is not None:
        existing.tencent_secret_key = encrypt_secret(setting.tencent_secret_key)
    if setting.tencent_region is not None:
        existing.tencent_region = setting.tencent_region
    if setting.track_domain is not None:
        existing.track_domain = setting.track_domain.strip()
    if setting.from_alias is not None:
        existing.from_alias = setting.from_alias

    db.commit()
    return {"message": "Settings updated"}


@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    return _sanitize_setting(db.query(models.Setting).first())


@router.get("/accounts")
def get_cloud_accounts(
    provider: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(models.CloudAccount)
    if provider:
        query = query.filter(models.CloudAccount.provider == provider.lower().strip())
    rows = query.order_by(
        models.CloudAccount.provider.asc(), models.CloudAccount.id.asc()
    ).all()
    return [serialize_cloud_account(row) for row in rows]


@router.post("/accounts")
def create_cloud_account(data: CloudAccountCreate, db: Session = Depends(get_db)):
    provider = (data.provider or "").lower().strip()
    if provider not in {"aliyun", "tencent"}:
        raise HTTPException(status_code=400, detail="Unsupported provider")

    if provider == "aliyun" and (not data.access_key_id or not data.access_key_secret):
        raise HTTPException(status_code=400, detail="Aliyun access key is required")
    if provider == "tencent" and (
        not data.tencent_secret_id or not data.tencent_secret_key
    ):
        raise HTTPException(status_code=400, detail="Tencent secret is required")

    account = models.CloudAccount(
        provider=provider,
        name=(data.name or "").strip() or f"{provider}-account",
        access_key_id=data.access_key_id,
        access_key_secret=encrypt_secret(data.access_key_secret),
        region_id=data.region_id or "cn-hangzhou",
        tencent_secret_id=data.tencent_secret_id,
        tencent_secret_key=encrypt_secret(data.tencent_secret_key),
        tencent_region=data.tencent_region or "ap-hongkong",
        from_alias=data.from_alias,
        enabled=data.enabled,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return serialize_cloud_account(account)


@router.put("/accounts/{account_id}")
def update_cloud_account(
    account_id: int, data: CloudAccountUpdate, db: Session = Depends(get_db)
):
    account = (
        db.query(models.CloudAccount).filter(models.CloudAccount.id == account_id).first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Cloud account not found")

    if data.name is not None:
        account.name = data.name.strip() or account.name
    if data.access_key_id is not None:
        account.access_key_id = data.access_key_id.strip()
    if data.access_key_secret is not None and data.access_key_secret != "":
        account.access_key_secret = encrypt_secret(data.access_key_secret)
    if data.region_id is not None:
        account.region_id = data.region_id
    if data.tencent_secret_id is not None:
        account.tencent_secret_id = data.tencent_secret_id.strip()
    if data.tencent_secret_key is not None and data.tencent_secret_key != "":
        account.tencent_secret_key = encrypt_secret(data.tencent_secret_key)
    if data.tencent_region is not None:
        account.tencent_region = data.tencent_region
    if data.from_alias is not None:
        account.from_alias = data.from_alias
    if data.enabled is not None:
        account.enabled = data.enabled

    # Validate using decrypted values for backward compatibility.
    decrypted = _decrypt_account(account)
    if account.provider == "aliyun":
        if not account.access_key_id or not decrypted.access_key_secret:
            raise HTTPException(status_code=400, detail="Aliyun access key is required")
    if account.provider == "tencent":
        if not account.tencent_secret_id or not decrypted.tencent_secret_key:
            raise HTTPException(status_code=400, detail="Tencent secret is required")

    db.commit()
    db.refresh(account)
    return serialize_cloud_account(account)


@router.delete("/accounts/{account_id}")
def delete_cloud_account(account_id: int, db: Session = Depends(get_db)):
    account = (
        db.query(models.CloudAccount).filter(models.CloudAccount.id == account_id).first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Cloud account not found")

    template_count = (
        db.query(models.EmailTemplate)
        .filter(models.EmailTemplate.account_id == account_id)
        .count()
    )
    campaign_count = (
        db.query(models.Campaign).filter(models.Campaign.account_id == account_id).count()
    )
    if template_count or campaign_count:
        raise HTTPException(
            status_code=400, detail="Account is referenced by templates/campaigns"
        )

    db.delete(account)
    db.commit()
    return {"status": "deleted"}


@router.post("/contacts/upload")
async def upload_contacts(
    file: UploadFile = File(...),
    list_name: str = Form(...),
    db: Session = Depends(get_db),
):
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="CSV 文件过大，最大 50MB")
    try:
        contact_list = ContactService.process_csv(db, content, list_name)
        return {"id": contact_list.id, "count": contact_list.total_count}
    except Exception as e:
        logger.exception("contacts/upload failed")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/contacts")
def get_contact_lists(db: Session = Depends(get_db)):
    return (
        db.query(models.ContactList)
        .order_by(models.ContactList.created_at.desc(), models.ContactList.id.desc())
        .all()
    )


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
    provider = (template.provider or "local").lower().strip()
    if provider not in {"local", "aliyun", "tencent"}:
        raise HTTPException(status_code=400, detail="Unknown provider")

    account_id = template.account_id
    if provider in {"aliyun", "tencent"}:
        account = _resolve_active_cloud_account_or_400(db, account_id, provider)
        account_id = account.id
    else:
        account_id = None

    db_template = models.EmailTemplate(
        title=template.title,
        subject=template.subject,
        body=template.body,
        from_alias=template.from_alias,
        provider=provider,
        account_id=account_id,
    )
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
    if template.provider is not None:
        provider = (template.provider or "local").lower().strip()
        if provider not in {"local", "aliyun", "tencent"}:
            raise HTTPException(status_code=400, detail="Unknown provider")
        db_template.provider = provider
        if provider in {"aliyun", "tencent"}:
            account = _resolve_active_cloud_account_or_400(db, template.account_id, provider)
            db_template.account_id = account.id
        else:
            db_template.account_id = None
    db.commit()
    return db_template


@router.get("/templates")
def get_templates(
    provider: Optional[str] = Query(default=None),
    account_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(models.EmailTemplate)
    if provider:
        query = query.filter(models.EmailTemplate.provider == provider.lower().strip())
    if account_id is not None:
        query = query.filter(models.EmailTemplate.account_id == account_id)
    templates = query.order_by(models.EmailTemplate.id.asc()).all()
    for t in templates:
        t.body = try_decode_base64(t.body)
    account_map = {
        row.id: row
        for row in db.query(models.CloudAccount)
        .filter(models.CloudAccount.id.in_([t.account_id for t in templates if t.account_id]))
        .all()
    }
    result = []
    for t in templates:
        account = account_map.get(t.account_id)
        result.append(
            {
                "id": t.id,
                "title": t.title,
                "subject": t.subject,
                "body": t.body,
                "from_alias": t.from_alias,
                "provider": t.provider,
                "provider_id": t.provider_id,
                "account_id": t.account_id,
                "account_name": account.name if account else None,
                "account_provider": account.provider if account else None,
                "created_at": t.created_at,
            }
        )
    return result


@router.delete("/templates/{id}")
def delete_template(id: int, db: Session = Depends(get_db)):
    template = db.query(models.EmailTemplate).filter(models.EmailTemplate.id == id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    referenced_campaigns = (
        db.query(models.Campaign)
        .filter(models.Campaign.template_id == id)
        .count()
    )
    if referenced_campaigns > 0:
        raise HTTPException(
            status_code=400,
            detail="Template is referenced by campaigns and cannot be deleted",
        )

    db.delete(template)
    db.commit()
    return {"status": "deleted"}


@router.post("/templates/import")
def import_template(data: TemplateImport, db: Session = Depends(get_db)):
    provider = (data.provider or "").lower().strip()
    if provider not in {"aliyun", "tencent"}:
        raise HTTPException(status_code=400, detail="Unknown provider")
    account = _resolve_active_cloud_account_or_400(db, data.account_id, provider)
    account = _decrypt_account(account)
    setting = db.query(models.Setting).first()

    try:
        if provider == "aliyun":
            client = AliyunService.create_client(
                account.access_key_id, account.access_key_secret, account.region_id
            )
            detail_res = AliyunService.desc_template(client, int(data.template_id))
            detail = detail_res.body
            title = detail.template_name
            subject = detail.template_subject
            body = detail.template_text
        else:
            from ..services.tencent_service import TencentService

            client = TencentService.create_client(
                account.tencent_secret_id,
                account.tencent_secret_key,
                account.tencent_region,
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

        existing = (
            db.query(models.EmailTemplate)
            .filter(
                models.EmailTemplate.provider == provider,
                models.EmailTemplate.provider_id == data.template_id,
                models.EmailTemplate.account_id == account.id,
            )
            .first()
        )

        if existing:
            existing.title = title
            existing.subject = subject
            existing.body = body
            db.commit()
            return {"message": "模板已更新", "title": title}

        db.add(
            models.EmailTemplate(
                title=title,
                subject=subject,
                body=body,
                from_alias=account.from_alias or (setting.from_alias if setting else None),
                provider=provider,
                provider_id=data.template_id,
                account_id=account.id,
            )
        )
        db.commit()
        return {"message": "模板已导入", "title": title}
    except Exception as e:
        logger.exception("templates/import failed")
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@router.post("/templates/sync")
def sync_templates(
    provider: Optional[str] = Query(default=None),
    account_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    provider = (provider or "").lower().strip() if provider else None
    if provider and provider not in {"aliyun", "tencent"}:
        raise HTTPException(status_code=400, detail="Unknown provider")
    setting = db.query(models.Setting).first()
    messages = []

    accounts_query = db.query(models.CloudAccount).filter(
        models.CloudAccount.enabled.isnot(False)
    )
    if account_id:
        accounts_query = accounts_query.filter(models.CloudAccount.id == account_id)
    if provider:
        accounts_query = accounts_query.filter(models.CloudAccount.provider == provider)
    accounts = accounts_query.order_by(models.CloudAccount.id.asc()).all()

    if not accounts:
        return {"message": "未配置可用云账号，无法同步"}

    for account in accounts:
        account = _decrypt_account(account)
        if account.provider == "aliyun":
            if not account.access_key_id or not account.access_key_secret:
                messages.append(f"{account.name}: 缺少阿里云密钥，已跳过")
                continue
            try:
                client = AliyunService.create_client(
                    account.access_key_id, account.access_key_secret, account.region_id
                )
                res = AliyunService.query_templates(client)
                count = 0
                if res.body.data and res.body.data.template:
                    for t in res.body.data.template:
                        detail_res = AliyunService.desc_template(client, int(t.template_id))
                        detail = detail_res.body
                        existing = (
                            db.query(models.EmailTemplate)
                            .filter(
                                models.EmailTemplate.provider == "aliyun",
                                models.EmailTemplate.provider_id == str(t.template_id),
                                models.EmailTemplate.account_id == account.id,
                            )
                            .first()
                        )
                        if not existing:
                            db.add(
                                models.EmailTemplate(
                                    title=detail.template_name,
                                    subject=detail.template_subject,
                                    body=detail.template_text,
                                    from_alias=account.from_alias
                                    or (setting.from_alias if setting else None),
                                    provider="aliyun",
                                    provider_id=str(t.template_id),
                                    account_id=account.id,
                                )
                            )
                            count += 1
                        else:
                            existing.title = detail.template_name
                            existing.subject = detail.template_subject
                            existing.body = detail.template_text
                            existing.from_alias = (
                                existing.from_alias
                                or account.from_alias
                                or (setting.from_alias if setting else None)
                            )
                messages.append(f"{account.name}: 阿里云同步 {count} 个")
            except Exception:
                logger.exception("Aliyun template sync failed for %s", account.name)
                messages.append(f"{account.name}: 阿里云同步失败")
            continue

        if not account.tencent_secret_id or not account.tencent_secret_key:
            messages.append(f"{account.name}: 缺少腾讯云密钥，已跳过")
            continue
        try:
            from ..services.tencent_service import TencentService

            client = TencentService.create_client(
                account.tencent_secret_id,
                account.tencent_secret_key,
                account.tencent_region,
            )
            res = TencentService.query_templates(client)
            data = json.loads(res.to_json_string())
            templates_list = data.get("TemplatesMetadata", [])
            count = 0
            for t in templates_list:
                template_id = t.get("TemplateID")
                template_name = t.get("TemplateName")
                try:
                    detail_res = TencentService.get_template(client, template_id)
                    detail_data = json.loads(detail_res.to_json_string())
                    detail_content = detail_data.get("TemplateContent", {})
                    subject = detail_content.get("TemplateSubject", template_name)
                    raw_body = (
                        detail_content.get("Html")
                        or detail_content.get("Text")
                        or "No Content"
                    )
                    body = try_decode_base64(raw_body)
                    existing = (
                        db.query(models.EmailTemplate)
                        .filter(
                            models.EmailTemplate.provider == "tencent",
                            models.EmailTemplate.provider_id == str(template_id),
                            models.EmailTemplate.account_id == account.id,
                        )
                        .first()
                    )
                    if not existing:
                        db.add(
                            models.EmailTemplate(
                                title=template_name,
                                subject=subject,
                                body=body,
                                from_alias=account.from_alias
                                or (setting.from_alias if setting else None),
                                provider="tencent",
                                provider_id=str(template_id),
                                account_id=account.id,
                            )
                        )
                        count += 1
                    else:
                        existing.title = template_name
                        existing.subject = subject
                        existing.body = body
                        existing.from_alias = (
                            existing.from_alias
                            or account.from_alias
                            or (setting.from_alias if setting else None)
                        )
                except Exception:
                    logger.exception(
                        "Failed to fetch Tencent template detail template_id=%s account=%s",
                        template_id,
                        account.name,
                    )
            messages.append(f"{account.name}: 腾讯云同步 {count} 个")
        except Exception:
            logger.exception("Tencent template sync failed for %s", account.name)
            messages.append(f"{account.name}: 腾讯云同步失败")

    db.commit()
    return {"message": " | ".join(messages)}


@router.get("/senders/sync")
def sync_senders(
    provider: Optional[str] = Query(default=None),
    account_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    provider = (provider or "").lower().strip() if provider else None
    if provider and provider not in {"aliyun", "tencent"}:
        raise HTTPException(status_code=400, detail="Unknown provider")
    accounts_query = db.query(models.CloudAccount).filter(
        models.CloudAccount.enabled.isnot(False)
    )
    if account_id:
        accounts_query = accounts_query.filter(models.CloudAccount.id == account_id)
    if provider:
        accounts_query = accounts_query.filter(models.CloudAccount.provider == provider)
    accounts = accounts_query.order_by(models.CloudAccount.id.asc()).all()
    if not accounts:
        return []
    senders = []
    for account in accounts:
        account = _decrypt_account(account)
        if account.provider == "aliyun":
            if not account.access_key_id or not account.access_key_secret:
                continue
            try:
                client = AliyunService.create_client(
                    account.access_key_id, account.access_key_secret, account.region_id
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
                                "label": f"[阿里云][{account.name}] {addr.account_name} ({status_str})",
                                "reply_address": addr.reply_address,
                                "account_id": account.id,
                                "account_label": account.name,
                            }
                        )
            except Exception:
                logger.exception("Aliyun senders sync failed for %s", account.name)
            continue

        if not account.tencent_secret_id or not account.tencent_secret_key:
            continue
        try:
            from ..services.tencent_service import TencentService

            client = TencentService.create_client(
                account.tencent_secret_id,
                account.tencent_secret_key,
                account.tencent_region,
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
                            "label": f"[腾讯云][{account.name}] {email}",
                            "account_id": account.id,
                            "account_label": account.name,
                        }
                    )
        except Exception:
            logger.exception("Tencent senders sync failed for %s", account.name)
    return senders


@router.post("/campaigns")
def create_campaign(campaign: CampaignCreate, db: Session = Depends(get_db)):
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
        campaign.account_id,
        campaign.reply_to_address,
        campaign.track_opens,
        campaign.track_clicks,
    )


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
    campaigns = (
        db.query(models.Campaign)
        .order_by(models.Campaign.created_at.desc(), models.Campaign.id.desc())
        .all()
    )
    account_ids = [c.account_id for c in campaigns if c.account_id]
    account_map = {
        row.id: row
        for row in db.query(models.CloudAccount)
        .filter(models.CloudAccount.id.in_(account_ids))
        .all()
    }
    result = []
    for c in campaigns:
        account = account_map.get(c.account_id)
        result.append(
            {
                "id": c.id,
                "name": c.name,
                "provider": c.provider,
                "account_id": c.account_id,
                "account_label": account.name if account else None,
                "template_id": c.template_id,
                "list_id": c.list_id,
                "account_name": c.account_name,
                "tag_name": c.tag_name,
                "from_alias": c.from_alias,
                "reply_to_address": c.reply_to_address,
                "track_opens": c.track_opens,
                "track_clicks": c.track_clicks,
                "status": c.status,
                "total_recipients": c.total_recipients,
                "sent_count": c.sent_count,
                "batch_size": c.batch_size,
                "interval_minutes": c.interval_minutes,
                "scheduled_start_time": c.scheduled_start_time,
                "scheduled_at": c.scheduled_at,
                "created_at": c.created_at,
            }
        )
    return result


@router.post("/campaigns/{id}/start")
def start_campaign(id: int, db: Session = Depends(get_db)):
    campaign = db.query(models.Campaign).filter(models.Campaign.id == id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.scheduled_start_time and campaign.scheduled_start_time > datetime.utcnow():
        campaign.status = "scheduled"
        db.commit()
        return {"status": "scheduled", "start_time": campaign.scheduled_start_time}

    campaign.status = "sending"
    db.commit()
    try:
        scheduler.add_job(
            send_campaign_batch,
            "date",
            run_date=datetime.now(),
            id=f"campaign_start_{id}",
            replace_existing=True,
        )
    except Exception as e:
        campaign.status = "error"
        db.commit()
        logger.exception("Trigger campaign failed id=%s", id)
        raise HTTPException(status_code=500, detail=f"Failed to start campaign: {e}")
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
