import io
import json
import logging
import re
import time
import uuid
from datetime import datetime
from typing import Iterable, Optional

import pandas as pd
from fastapi import HTTPException
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from ..models.models import (
    Campaign,
    CampaignRecipient,
    CloudAccount,
    Contact,
    ContactList,
    EmailTemplate,
)

logger = logging.getLogger(__name__)

MAX_CSV_ROWS = 300_000
_CSV_ENCODINGS = ("utf-8-sig", "gb18030", "gbk", "utf-16")
_CSV_SEPARATORS = (",", "\t", ";")
_SQLITE_LOCK_RETRY_ATTEMPTS = 3
_SQLITE_LOCK_RETRY_DELAY_SECONDS = 0.5


def _normalize_col(col: object) -> str:
    return str(col).strip().replace("\ufeff", "")


def _normalize_name_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(key).strip().lower())


def _find_email_column(columns: Iterable[object]) -> Optional[str]:
    normalized = [_normalize_col(col) for col in columns]
    for col in normalized:
        if "emailaddr" in col.lower():
            return col
    for col in normalized:
        if "email" in col.lower():
            return col
    return None


def _pick_var_by_alias(extra_vars: dict, aliases: set[str]) -> str:
    for key, value in extra_vars.items():
        if _normalize_name_key(key) in aliases:
            return str(value or "").strip()
    return ""


def _extract_name_fields(extra_vars: dict) -> tuple[str, str, str, str]:
    first_name = _pick_var_by_alias(
        extra_vars,
        {
            "firstname",
            "givenname",
            "given",
            "forename",
            "first",
        },
    )
    middle_name = _pick_var_by_alias(
        extra_vars,
        {
            "middlename",
            "middle",
            "secondname",
        },
    )
    last_name = _pick_var_by_alias(
        extra_vars,
        {
            "lastname",
            "surname",
            "familyname",
            "family",
            "last",
        },
    )
    full_name = _pick_var_by_alias(
        extra_vars,
        {
            "name",
            "username",
            "fullname",
            "displayname",
        },
    )
    if not full_name:
        full_name = " ".join(
            part for part in [first_name, middle_name, last_name] if part
        ).strip()
    return first_name, middle_name, last_name, full_name


def _read_candidate_df(file_content: bytes) -> Optional[pd.DataFrame]:
    for encoding in _CSV_ENCODINGS:
        for sep in _CSV_SEPARATORS:
            try:
                candidate = pd.read_csv(
                    io.BytesIO(file_content),
                    encoding=encoding,
                    sep=sep,
                    dtype=str,
                    keep_default_na=False,
                )
            except Exception:
                continue

            if len(candidate.columns) == 1:
                only_col = _normalize_col(candidate.columns[0])
                if any(token in only_col for token in ("\t", ";", ",")):
                    continue

            if _find_email_column(candidate.columns):
                logger.info(
                    "CSV parser selected encoding=%s separator=%s", encoding, repr(sep)
                )
                return candidate

    # Final fallback for tab-separated exports with unusual BOM/encoding.
    for encoding in _CSV_ENCODINGS:
        try:
            text = file_content.decode(encoding)
        except Exception:
            continue
        if "\t" not in text:
            continue
        try:
            candidate = pd.read_csv(
                io.StringIO(text),
                sep="\t",
                dtype=str,
                keep_default_na=False,
            )
        except Exception:
            continue
        if _find_email_column(candidate.columns):
            logger.info("CSV parser fallback selected encoding=%s with tab split", encoding)
            return candidate

    return None


def is_sqlite_locked_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "database is locked" in message or "database table is locked" in message


class ContactService:
    @staticmethod
    def _persist_contacts(db: Session, df: pd.DataFrame, list_name: str):
        var_columns = [col for col in df.columns if col.lower() != "emailaddr"]

        contact_list = ContactList(name=list_name, total_count=0)
        db.add(contact_list)
        db.flush()

        contacts = []
        for _, row in df.iterrows():
            extra_vars = {
                key: str(row[key]).strip() if str(row[key]).strip() else ""
                for key in var_columns
            }
            (
                first_name,
                middle_name,
                last_name,
                contact_name,
            ) = _extract_name_fields(extra_vars)
            contacts.append(
                Contact(
                    email=row["EmailAddr"],
                    name=contact_name,
                    first_name=first_name or None,
                    middle_name=middle_name or None,
                    last_name=last_name or None,
                    extra_vars=json.dumps(extra_vars, ensure_ascii=False),
                    list_id=contact_list.id,
                )
            )

        for i in range(0, len(contacts), 1000):
            db.bulk_save_objects(contacts[i : i + 1000])

        contact_list.total_count = len(contacts)
        db.commit()
        db.refresh(contact_list)
        return contact_list

    @staticmethod
    def process_csv(db: Session, file_content: bytes, list_name: str):
        df = _read_candidate_df(file_content)
        if df is None:
            raise ValueError("无法解析文件。请确保文件包含 EmailAddr 列。")

        # Normalize headers.
        renamed = {_raw: _normalize_col(_raw) for _raw in df.columns}
        df = df.rename(columns=renamed)

        email_col = _find_email_column(df.columns)
        if not email_col:
            raise ValueError(f"未找到 EmailAddr 列。检测到列: {list(df.columns)}")
        if email_col != "EmailAddr":
            df = df.rename(columns={email_col: "EmailAddr"})

        # Clean and validate rows.
        df["EmailAddr"] = (
            df["EmailAddr"].astype(str).str.strip().str.replace("\t", "", regex=False)
        )
        df = df[df["EmailAddr"].str.contains("@", na=False)]
        df = df.drop_duplicates(subset=["EmailAddr"], keep="first")

        if df.empty:
            raise ValueError("CSV 文件中没有有效的收件人数据")
        if len(df) > MAX_CSV_ROWS:
            raise ValueError(f"CSV 行数超限，最多支持 {MAX_CSV_ROWS} 行")

        for attempt in range(1, _SQLITE_LOCK_RETRY_ATTEMPTS + 1):
            try:
                return ContactService._persist_contacts(db, df, list_name)
            except OperationalError as exc:
                db.rollback()
                if not is_sqlite_locked_error(exc) or attempt >= _SQLITE_LOCK_RETRY_ATTEMPTS:
                    raise

                logger.warning(
                    "SQLite locked during contact upload for list=%s, retry %s/%s",
                    list_name,
                    attempt,
                    _SQLITE_LOCK_RETRY_ATTEMPTS,
                )
                time.sleep(_SQLITE_LOCK_RETRY_DELAY_SECONDS * attempt)
            except Exception:
                db.rollback()
                raise


class CampaignService:
    @staticmethod
    def create_campaign(
        db: Session,
        name: str,
        template_id: int,
        list_id: int,
        account_name: str,
        batch_size: int,
        interval_minutes: int,
        scheduled_start_time: datetime = None,
        from_alias: str = None,
        provider: str = "aliyun",
        account_id: int = None,
        reply_to_address: str = None,
        track_opens: bool = True,
        track_clicks: bool = True,
    ):
        provider = (provider or "").lower().strip() or "aliyun"

        template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=400, detail="Template not found")

        contact_list = db.query(ContactList).filter(ContactList.id == list_id).first()
        if not contact_list:
            raise HTTPException(status_code=400, detail="Contact list not found")

        account = None
        if provider in {"aliyun", "tencent"} and account_id:
            account = db.query(CloudAccount).filter(CloudAccount.id == account_id).first()
            if not account:
                raise HTTPException(status_code=400, detail="Cloud account not found")
            if account.provider != provider:
                raise HTTPException(
                    status_code=400,
                    detail="Template/provider/account mismatch",
                )

        if template.provider in {"aliyun", "tencent"}:
            if template.provider != provider:
                raise HTTPException(
                    status_code=400,
                    detail="Template/provider/account mismatch",
                )
            if account_id and template.account_id and template.account_id != account_id:
                raise HTTPException(
                    status_code=400,
                    detail="Template/provider/account mismatch",
                )

        recipients_query = (
            db.query(Contact)
            .filter(Contact.list_id == list_id)
            .order_by(Contact.id.asc())
        )
        total_recipients = recipients_query.count()
        if total_recipients == 0:
            raise HTTPException(status_code=400, detail="Contact list is empty")

        try:
            campaign = Campaign(
                name=name,
                provider=provider,
                account_id=account_id,
                template_id=template_id,
                list_id=list_id,
                account_name=account_name,
                batch_size=batch_size,
                interval_minutes=interval_minutes,
                scheduled_start_time=scheduled_start_time,
                from_alias=from_alias,
                reply_to_address=reply_to_address,
                track_opens=track_opens,
                track_clicks=track_clicks,
                total_recipients=total_recipients,
                sent_count=0,
                status="pending",
            )
            db.add(campaign)
            db.flush()

            send_order = 1
            batch = []
            for contact in recipients_query.yield_per(1000):
                try:
                    extra_vars = json.loads(contact.extra_vars) if contact.extra_vars else {}
                except Exception:
                    extra_vars = {}

                batch.append(
                    CampaignRecipient(
                        campaign_id=campaign.id,
                        contact_id=contact.id,
                        email=contact.email,
                        name_snapshot=contact.name,
                        first_name_snapshot=contact.first_name,
                        middle_name_snapshot=contact.middle_name,
                        last_name_snapshot=contact.last_name,
                        extra_vars_snapshot=json.dumps(extra_vars, ensure_ascii=False),
                        send_order=send_order,
                        status="pending",
                        tracking_id=str(uuid.uuid4()),
                    )
                )
                send_order += 1

                if len(batch) >= 1000:
                    db.bulk_save_objects(batch)
                    batch.clear()

            if batch:
                db.bulk_save_objects(batch)

            db.commit()
            db.refresh(campaign)
            return campaign
        except Exception:
            db.rollback()
            raise
