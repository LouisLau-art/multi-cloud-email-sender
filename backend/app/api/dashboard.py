from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from datetime import datetime, timedelta
from ..core.database import get_db
from ..models import models
from pydantic import BaseModel
from typing import List, Optional
import csv
import io

router = APIRouter()


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
def get_dashboard_stats(db: Session = Depends(get_db)):
    total = db.query(models.CampaignRecipient).count()
    success_statuses = ["sent", "opened", "clicked", "unsubscribed"]
    delivered = (
        db.query(models.CampaignRecipient)
        .filter(models.CampaignRecipient.status.in_(success_statuses))
        .count()
    )
    # Sent count in the dashboard is defined as successfully sent recipients.
    sent = delivered
    opened = (
        db.query(models.CampaignRecipient)
        .filter(models.CampaignRecipient.opened_at.isnot(None))
        .count()
    )
    clicked = (
        db.query(models.CampaignRecipient)
        .filter(models.CampaignRecipient.clicked_at.isnot(None))
        .count()
    )

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
def get_chart_data(days: int = 2, db: Session = Depends(get_db)):
    start_date = datetime.utcnow() - timedelta(days=days)

    events = (
        db.query(models.CampaignRecipient)
        .filter(
            or_(
                models.CampaignRecipient.opened_at >= start_date,
                models.CampaignRecipient.clicked_at >= start_date,
            )
        )
        .all()
    )

    data_map = {}

    # Initialize buckets for the last N hours to ensure continuity?
    # Or just return points where data exists. Frontend usually handles gaps or we fill them.
    # Let's return existing data points sorted.

    for r in events:
        if r.opened_at and r.opened_at >= start_date:
            # Group by Hour: 2026-01-22 10:00
            key = r.opened_at.strftime("%Y-%m-%d %H:00")
            if key not in data_map:
                data_map[key] = {"opened": 0, "clicked": 0}
            data_map[key]["opened"] += 1

        if r.clicked_at and r.clicked_at >= start_date:
            key = r.clicked_at.strftime("%Y-%m-%d %H:00")
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


@router.get("/dashboard/export")
def export_recipients_csv(db: Session = Depends(get_db)):
    query = db.query(models.CampaignRecipient).order_by(
        models.CampaignRecipient.sent_at.desc()
    )

    # Generate CSV in memory (using generator for large datasets would be better, but keep simple for now)
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(
        ["Email", "Status", "Sent At", "Opened At", "Clicked At", "Error Message"]
    )

    # Rows
    # Limit to reasonable number if memory is concern, or stream
    # Let's stream it properly using a generator
    output.close()

    def iter_csv():
        # Re-create stringIO buffer for each yield
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        # Write Header
        writer.writerow(
            ["Email", "Status", "Sent At", "Opened At", "Clicked At", "Error Message"]
        )
        buffer.seek(0)
        yield buffer.read()
        buffer.truncate(0)
        buffer.seek(0)

        # Query in chunks to avoid memory overload
        limit = 1000
        offset = 0
        while True:
            chunk = query.offset(offset).limit(limit).all()
            if not chunk:
                break

            for r in chunk:
                writer.writerow(
                    [
                        r.email,
                        r.status,
                        r.sent_at.isoformat() if r.sent_at else "",
                        r.opened_at.isoformat() if r.opened_at else "",
                        r.clicked_at.isoformat() if r.clicked_at else "",
                        r.error_message or "",
                    ]
                )
                buffer.seek(0)
                data = buffer.read()
                buffer.truncate(0)
                buffer.seek(0)
                if data:
                    yield data

            offset += limit

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
    db: Session = Depends(get_db),
):
    query = db.query(models.CampaignRecipient)

    if search:
        query = query.filter(models.CampaignRecipient.email.contains(search))

    if status:
        if status == "opened":
            query = query.filter(models.CampaignRecipient.opened_at.isnot(None))
        elif status == "clicked":
            query = query.filter(models.CampaignRecipient.clicked_at.isnot(None))
        elif status == "failed":
            query = query.filter(models.CampaignRecipient.status == "failed")
        elif status == "sent":
            query = query.filter(models.CampaignRecipient.status == "sent")

    total = query.count()
    items = (
        query.order_by(models.CampaignRecipient.sent_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )

    return {"total": total, "items": items, "page": page, "size": size}
