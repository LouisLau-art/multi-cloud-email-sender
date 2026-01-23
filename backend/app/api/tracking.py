from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.orm import Session
from datetime import datetime
from ..core.database import get_db
from ..models import models
import base64

router = APIRouter()

# 1x1 Transparent GIF
PIXEL_GIF_DATA = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)


@router.get("/open/{tracking_id}")
def track_open(tracking_id: str, request: Request, db: Session = Depends(get_db)):
    """
    Tracking pixel endpoint.
    Records the open event and returns a transparent 1x1 GIF.
    """
    recipient = (
        db.query(models.CampaignRecipient)
        .filter(models.CampaignRecipient.tracking_id == tracking_id)
        .first()
    )

    if recipient:
        # Update status if not already opened (or update last open time)
        if not recipient.opened_at:
            recipient.opened_at = datetime.utcnow()
            if recipient.status == "sent":
                recipient.status = "opened"
            db.commit()

            # Update Campaign stats (optional, but good for quick cache)
            # Currently we calculate on fly or stored in CampaignRecipient
            pass

    return Response(content=PIXEL_GIF_DATA, media_type="image/gif")


@router.get("/click/{tracking_id}")
def track_click(tracking_id: str, target: str, db: Session = Depends(get_db)):
    """
    Link tracking endpoint.
    Records the click event and redirects to the target URL.
    """
    recipient = (
        db.query(models.CampaignRecipient)
        .filter(models.CampaignRecipient.tracking_id == tracking_id)
        .first()
    )

    if recipient:
        if not recipient.clicked_at:
            recipient.clicked_at = datetime.utcnow()
            # Click implies Open
            if not recipient.opened_at:
                recipient.opened_at = datetime.utcnow()

            recipient.status = "clicked"
            db.commit()

    return Response(status_code=302, headers={"Location": target})
