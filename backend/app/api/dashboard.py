from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from datetime import datetime, timedelta, timezone
from ..core.database import get_db
from .endpoints import require_admin_session
from ..models import models
from pydantic import BaseModel
from typing import List, Optional, Literal
import csv
import io

router = APIRouter(dependencies=[Depends(require_admin_session)])
BEIJING_TZ = timezone(timedelta(hours=8))
SUCCESS_STATUSES = ("sent", "opened", "clicked", "unsubscribed")


def _to_beijing_time(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    # DB stores UTC as naive datetime; attach UTC before converting.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BEIJING_TZ)


def _format_beijing_time(dt: Optional[datetime]) -> str:
    beijing_dt = _to_beijing_time(dt)
    return beijing_dt.strftime("%Y-%m-%d %H:%M:%S") if beijing_dt else ""


def _apply_status_filter(query, status: Optional[str]):
    if not status:
        return query
    if status == "opened":
        return query.filter(models.CampaignRecipient.opened_at.isnot(None))
    if status == "clicked":
        return query.filter(models.CampaignRecipient.clicked_at.isnot(None))
    if status == "failed":
        return query.filter(models.CampaignRecipient.status == "failed")
    if status == "sent":
        return query.filter(models.CampaignRecipient.status == "sent")
    if status == "delivered":
        return query.filter(models.CampaignRecipient.status.in_(SUCCESS_STATUSES))
    return query


def _normalize_query_datetime(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    # Incoming query datetimes may be timezone-aware; DB stores UTC naive.
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _apply_sent_time_filter(
    query, start_time: Optional[datetime], end_time: Optional[datetime]
):
    start = _normalize_query_datetime(start_time)
    end = _normalize_query_datetime(end_time)

    if start and end and start > end:
        start, end = end, start

    if start:
        query = query.filter(models.CampaignRecipient.sent_at >= start)
    if end:
        query = query.filter(models.CampaignRecipient.sent_at <= end)
    return query


def _full_name_from_recipient(recipient: models.CampaignRecipient) -> str:
    full_name = (recipient.name_snapshot or "").strip()
    if full_name:
        return full_name
    return " ".join(
        part
        for part in [
            (recipient.first_name_snapshot or "").strip(),
            (recipient.middle_name_snapshot or "").strip(),
            (recipient.last_name_snapshot or "").strip(),
        ]
        if part
    ).strip()


class DashboardStats(BaseModel):
    total_recipients: int
    sent_count: int
    delivered_count: int
    opened_count: int
    clicked_count: int
    open_rate: float
    click_rate: float
    delivery_rate: float


class ChartDataPoint(BaseModel):
    time: str
    opened: int
    clicked: int


@router.get("/dashboard/stats", response_model=DashboardStats)
def get_dashboard_stats(
    campaign_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    base_query = db.query(models.CampaignRecipient)
    if campaign_id is not None:
        base_query = base_query.filter(
            models.CampaignRecipient.campaign_id == campaign_id
        )

    total = base_query.count()
    delivered = base_query.filter(
        models.CampaignRecipient.status.in_(SUCCESS_STATUSES)
    ).count()
    # Sent count in the dashboard is defined as successfully sent recipients.
    sent = delivered
    opened = base_query.filter(models.CampaignRecipient.opened_at.isnot(None)).count()
    clicked = base_query.filter(models.CampaignRecipient.clicked_at.isnot(None)).count()

    # Avoid DivisionByZero
    delivery_rate = round((delivered / total * 100), 2) if total > 0 else 0
    open_rate = round((opened / delivered * 100), 2) if delivered > 0 else 0
    click_rate = round((clicked / delivered * 100), 2) if delivered > 0 else 0

    return {
        "total_recipients": total,
        "sent_count": sent,
        "delivered_count": delivered,
        "opened_count": opened,
        "clicked_count": clicked,
        "delivery_rate": delivery_rate,
        "open_rate": open_rate,
        "click_rate": click_rate,
    }


@router.get("/dashboard/chart", response_model=List[ChartDataPoint])
def get_chart_data(
    days: int = 2,
    campaign_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    start_date = datetime.utcnow() - timedelta(days=days)

    events_query = db.query(models.CampaignRecipient).filter(
        or_(
            models.CampaignRecipient.opened_at >= start_date,
            models.CampaignRecipient.clicked_at >= start_date,
        )
    )
    if campaign_id is not None:
        events_query = events_query.filter(
            models.CampaignRecipient.campaign_id == campaign_id
        )
    events = events_query.all()

    data_map = {}

    # Initialize buckets for the last N hours to ensure continuity?
    # Or just return points where data exists. Frontend usually handles gaps or we fill them.
    # Let's return existing data points sorted.

    for r in events:
        if r.opened_at and r.opened_at >= start_date:
            # Group by Beijing hour for dashboard consistency.
            key = _to_beijing_time(r.opened_at).strftime("%Y-%m-%d %H:00")
            if key not in data_map:
                data_map[key] = {"opened": 0, "clicked": 0}
            data_map[key]["opened"] += 1

        if r.clicked_at and r.clicked_at >= start_date:
            key = _to_beijing_time(r.clicked_at).strftime("%Y-%m-%d %H:00")
            if key not in data_map:
                data_map[key] = {"opened": 0, "clicked": 0}
            data_map[key]["clicked"] += 1

    result = []
    for time_str in sorted(data_map.keys()):
        result.append(
            {
                "time": time_str,
                "opened": data_map[time_str]["opened"],
                "clicked": data_map[time_str]["clicked"],
            }
        )

    return result


@router.get("/dashboard/campaigns")
def get_dashboard_campaigns(db: Session = Depends(get_db)):
    campaigns = (
        db.query(models.Campaign)
        .order_by(models.Campaign.created_at.desc(), models.Campaign.id.desc())
        .all()
    )
    result = []
    for campaign in campaigns:
        campaign_query = db.query(models.CampaignRecipient).filter(
            models.CampaignRecipient.campaign_id == campaign.id
        )
        total = campaign_query.count()
        delivered = campaign_query.filter(
            models.CampaignRecipient.status.in_(SUCCESS_STATUSES)
        ).count()
        opened = campaign_query.filter(
            models.CampaignRecipient.opened_at.isnot(None)
        ).count()
        clicked = campaign_query.filter(
            models.CampaignRecipient.clicked_at.isnot(None)
        ).count()
        delivery_rate = round((delivered / total * 100), 2) if total else 0
        open_rate = round((opened / delivered * 100), 2) if delivered else 0
        click_rate = round((clicked / delivered * 100), 2) if delivered else 0
        result.append(
            {
                "id": campaign.id,
                "name": campaign.name,
                "status": campaign.status,
                "created_at": campaign.created_at,
                "total_recipients": total,
                "sent_count": delivered,
                "delivered_count": delivered,
                "opened_count": opened,
                "clicked_count": clicked,
                "delivery_rate": delivery_rate,
                "open_rate": open_rate,
                "click_rate": click_rate,
            }
        )
    return result


@router.get("/dashboard/export")
def export_recipients_csv(
    campaign_id: Optional[int] = Query(default=None),
    search: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    scope: Literal["all", "page"] = Query(default="all"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    query = (
        db.query(
            models.CampaignRecipient,
            models.Campaign.name.label("campaign_name"),
        )
        .join(models.Campaign, models.Campaign.id == models.CampaignRecipient.campaign_id)
    )

    if campaign_id is not None:
        query = query.filter(models.CampaignRecipient.campaign_id == campaign_id)
    if search:
        query = query.filter(
            or_(
                models.CampaignRecipient.email.contains(search),
                models.CampaignRecipient.name_snapshot.contains(search),
                models.CampaignRecipient.first_name_snapshot.contains(search),
                models.CampaignRecipient.middle_name_snapshot.contains(search),
                models.CampaignRecipient.last_name_snapshot.contains(search),
                models.Campaign.name.contains(search),
            )
        )
    query = _apply_status_filter(query, status)
    query = _apply_sent_time_filter(query, start_time, end_time)
    query = query.order_by(
        models.CampaignRecipient.sent_at.desc(), models.CampaignRecipient.id.desc()
    )

    def iter_chunks():
        if scope == "page":
            yield query.offset((page - 1) * size).limit(size).all()
            return

        limit = 1000
        offset = 0
        while True:
            chunk = query.offset(offset).limit(limit).all()
            if not chunk:
                break
            yield chunk
            offset += limit

    def iter_csv():
        # Re-create stringIO buffer for each yield
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        # Write Header
        writer.writerow(
            [
                "Campaign",
                "Email",
                "First Name",
                "Middle Name",
                "Last Name",
                "Full Name",
                "Status",
                "Sent At (Asia/Shanghai)",
                "Opened At (Asia/Shanghai)",
                "Clicked At (Asia/Shanghai)",
                "Error Message",
            ]
        )
        buffer.seek(0)
        yield buffer.read()
        buffer.truncate(0)
        buffer.seek(0)

        # Query in chunks to avoid memory overload.
        for chunk in iter_chunks():
            for r, campaign_name in chunk:
                writer.writerow(
                    [
                        campaign_name or "",
                        r.email,
                        r.first_name_snapshot or "",
                        r.middle_name_snapshot or "",
                        r.last_name_snapshot or "",
                        _full_name_from_recipient(r),
                        r.status,
                        _format_beijing_time(r.sent_at),
                        _format_beijing_time(r.opened_at),
                        _format_beijing_time(r.clicked_at),
                        r.error_message or "",
                    ]
                )
                buffer.seek(0)
                data = buffer.read()
                buffer.truncate(0)
                buffer.seek(0)
                if data:
                    yield data

    return StreamingResponse(
        iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=export_report.csv"},
    )


@router.get("/dashboard/details")
def get_recipient_details(
    page: int = 1,
    size: int = 10,
    search: str = None,
    status: str = None,
    campaign_id: Optional[int] = Query(default=None),
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db),
):
    query = (
        db.query(
            models.CampaignRecipient,
            models.Campaign.name.label("campaign_name"),
        )
        .join(models.Campaign, models.Campaign.id == models.CampaignRecipient.campaign_id)
    )

    if campaign_id is not None:
        query = query.filter(models.CampaignRecipient.campaign_id == campaign_id)
    if search:
        query = query.filter(
            or_(
                models.CampaignRecipient.email.contains(search),
                models.CampaignRecipient.name_snapshot.contains(search),
                models.CampaignRecipient.first_name_snapshot.contains(search),
                models.CampaignRecipient.middle_name_snapshot.contains(search),
                models.CampaignRecipient.last_name_snapshot.contains(search),
                models.Campaign.name.contains(search),
            )
        )
    query = _apply_status_filter(query, status)
    query = _apply_sent_time_filter(query, start_time, end_time)

    total = query.count()
    rows = (
        query.order_by(
            models.CampaignRecipient.sent_at.desc(),
            models.CampaignRecipient.id.desc(),
        )
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    items = []
    for recipient, campaign_name in rows:
        items.append(
            {
                "id": recipient.id,
                "campaign_id": recipient.campaign_id,
                "campaign_name": campaign_name,
                "email": recipient.email,
                "status": recipient.status,
                "first_name": recipient.first_name_snapshot,
                "middle_name": recipient.middle_name_snapshot,
                "last_name": recipient.last_name_snapshot,
                "name": _full_name_from_recipient(recipient),
                "sent_at": recipient.sent_at,
                "opened_at": recipient.opened_at,
                "clicked_at": recipient.clicked_at,
                "error_message": recipient.error_message,
            }
        )

    return {"total": total, "items": items, "page": page, "size": size}
