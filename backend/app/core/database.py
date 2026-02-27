from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import sys

# Determine Database Path
# Use current working directory to ensure persistence even in frozen (EXE) mode
BASE_DIR = os.getcwd()
DB_PATH = os.path.join(BASE_DIR, "email_app.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

print(f"--- Database Path: {DB_PATH} ---")

# check_same_thread=False is needed for SQLite + FastAPI/APScheduler
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()