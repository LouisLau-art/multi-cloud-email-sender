from fastapi import APIRouter, Depends, HTTPException, Response, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from datetime import datetime
from ..core.database import get_db
from ..models import models
import base64
import json
from html import escape
from urllib.parse import urlparse

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
    parsed = urlparse(target)
    scheme = (parsed.scheme or "").lower()
    if scheme in {"http", "https"}:
        if not parsed.netloc:
            raise HTTPException(status_code=400, detail="Invalid redirect target")
    elif scheme == "mailto":
        if not parsed.path:
            raise HTTPException(status_code=400, detail="Invalid redirect target")
    elif scheme in {"tel", "sms"}:
        if not parsed.path:
            raise HTTPException(status_code=400, detail="Invalid redirect target")
    else:
        raise HTTPException(status_code=400, detail="Invalid redirect target")

    allowed = (
        db.query(models.CampaignRecipientLink)
        .filter(
            models.CampaignRecipientLink.tracking_id == tracking_id,
            models.CampaignRecipientLink.target_url == target,
        )
        .first()
    )
    if not allowed:
        raise HTTPException(status_code=404, detail="Tracking target not found")

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

    if scheme in {"http", "https"}:
        return RedirectResponse(url=target, status_code=302)

    escaped_href = escape(target, quote=True)
    # httpx TestClient cannot parse non-http Location redirects (mailto/tel/sms),
    # so for these schemes we return a tiny handoff page and trigger navigation client-side.
    handoff_html = (
        "<!doctype html>"
        "<html><head><meta charset='utf-8'><title>Redirecting</title></head>"
        "<body>"
        f"<script>window.location.href = {json.dumps(target)};</script>"
        f"<a href=\"{escaped_href}\">Continue</a>"
        "</body></html>"
    )
    return HTMLResponse(content=handoff_html, status_code=200)
