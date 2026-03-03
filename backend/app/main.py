import logging
import os
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import endpoints, tracking, dashboard
from .core.database import Base, engine
from .core.db_migrations import run_startup_migrations
from .core.scheduler import scheduler, start_scheduler

logger = logging.getLogger(__name__)


def _configure_stdout_encoding():
    """Use UTF-8 stdout/stderr so Chinese logs don't turn into mojibake on Windows."""
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        # Keep startup robust even if stream reconfiguration is unavailable.
        pass


_configure_stdout_encoding()

# Ensure Database Tables Exist
Base.metadata.create_all(bind=engine)
run_startup_migrations(engine)

app = FastAPI(title="Email Marketing System")

# --- 1. CORS Configuration ---
CORS_ALLOW_ORIGIN_REGEX = os.getenv(
    "CORS_ALLOW_ORIGIN_REGEX",
    r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=CORS_ALLOW_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. API Routes ---
app.include_router(endpoints.public_router, prefix="/api")
app.include_router(endpoints.router, prefix="/api")
app.include_router(tracking.router, prefix="/api/track")
app.include_router(dashboard.router, prefix="/api")

# --- 3. Frontend Integration (Static Files) ---
# Determine path to frontend dist folder
# Normal Mode: ../frontend/dist
# Frozen Mode (EXE): sys._MEIPASS/frontend_dist
frontend_dist = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "dist"
)

if getattr(sys, "frozen", False):
    frontend_dist = os.path.join(sys._MEIPASS, "frontend_dist")

if os.path.exists(frontend_dist):
    logger.info("Mounting frontend from: %s", frontend_dist)
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
else:
    logger.warning("Frontend dist not found at: %s. Running in API-only mode.", frontend_dist)


# --- 4. Startup Events ---
@app.on_event("startup")
def on_startup():
    logger.info("Application Startup: Starting Scheduler...")
    start_scheduler()

    # Initialize Sample Data
    try:
        db = next(endpoints.get_db())
        if not db.query(endpoints.models.EmailTemplate).first():
            sample = endpoints.models.EmailTemplate(
                title="欢迎示例模板",
                subject="你好 {UserName}，欢迎体验新系统！",
                body="<p>亲爱的 {UserName}：</p><p>这是系统自动生成的测试模板。</p><p>如果您的 CSV 中包含 <b>Birthday</b> 列，它会显示在这里：{Birthday}</p>",
                from_alias="系统通知",
            )
            db.add(sample)
            db.commit()
            logger.info("--- Sample Template Created ---")
    except Exception as e:
        logger.exception("Error creating sample data: %s", e)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
