import logging
import os
from datetime import datetime
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import endpoints, tracking, dashboard
from .core.database import Base, DB_PATH, engine
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

def _is_sqlite_corruption_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "database disk image is malformed" in message
        or "file is not a database" in message
    )


def _archive_corrupted_sqlite_files(db_path: str) -> list[str]:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    archived_paths: list[str] = []
    for suffix in ("", "-wal", "-shm"):
        source_path = f"{db_path}{suffix}"
        if not os.path.exists(source_path):
            continue
        target_path = f"{db_path}.{timestamp}.corrupt{suffix}"
        os.replace(source_path, target_path)
        archived_paths.append(target_path)
    return archived_paths


def _init_database_with_recovery() -> None:
    try:
        Base.metadata.create_all(bind=engine)
        run_startup_migrations(engine)
        return
    except Exception as exc:
        if not _is_sqlite_corruption_error(exc):
            raise

        logger.error(
            "Detected SQLite corruption at startup (%s): %s",
            DB_PATH,
            exc,
        )
        engine.dispose()
        archived_paths = _archive_corrupted_sqlite_files(DB_PATH)
        logger.error("Corrupted SQLite files archived to: %s", archived_paths)

    # Retry once with a clean database file.
    Base.metadata.create_all(bind=engine)
    run_startup_migrations(engine)
    logger.warning(
        "Recreated a fresh SQLite database after corruption recovery. "
        "Old data is kept in *.corrupt* backup files."
    )


_init_database_with_recovery()

app = FastAPI(title="Email Marketing System")

# --- 1. CORS Configuration ---
CORS_ALLOW_ORIGIN_REGEX = os.getenv(
    "CORS_ALLOW_ORIGIN_REGEX",
    r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})(:\d+)?$",
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
