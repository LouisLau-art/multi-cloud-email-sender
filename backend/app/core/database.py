import os

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

# Determine Database Path
# Use current working directory to ensure persistence even in frozen (EXE) mode
BASE_DIR = os.getcwd()
DB_PATH = os.path.join(BASE_DIR, "email_app.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

print(f"--- Database Path: {DB_PATH} ---")

# check_same_thread=False is needed for SQLite + FastAPI/APScheduler
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
    poolclass=NullPool,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
