from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from .api import endpoints
from .core.database import engine, Base
from .core.scheduler import scheduler, start_scheduler
import os
import sys
import uvicorn

# Ensure Database Tables Exist
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Email Marketing System")

# --- 1. CORS Configuration (Permissive for Troubleshooting) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow ALL origins to fix connection issues
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. API Routes ---
app.include_router(endpoints.router, prefix="/api")

# --- 3. Frontend Integration (Static Files) ---
# Determine path to frontend dist folder
# Normal Mode: ../frontend/dist
# Frozen Mode (EXE): sys._MEIPASS/frontend_dist
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "dist")

if getattr(sys, 'frozen', False):
    frontend_dist = os.path.join(sys._MEIPASS, "frontend_dist")

if os.path.exists(frontend_dist):
    print(f"Mounting frontend from: {frontend_dist}")
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
else:
    print(f"Frontend dist not found at: {frontend_dist}. Running in API-only mode.")

# --- 4. Startup Events ---
@app.on_event("startup")
def on_startup():
    print("Application Startup: Starting Scheduler...")
    start_scheduler()
    
    # Initialize Sample Data
    try:
        db = next(endpoints.get_db())
        if not db.query(endpoints.models.EmailTemplate).first():
            sample = endpoints.models.EmailTemplate(
                title="欢迎示例模板",
                subject="你好 {UserName}，欢迎体验新系统！",
                body="<p>亲爱的 {UserName}：</p><p>这是系统自动生成的测试模板。</p><p>如果您的 CSV 中包含 <b>Birthday</b> 列，它会显示在这里：{Birthday}</p>",
                from_alias="系统通知"
            )
            db.add(sample)
            db.commit()
            print("--- Sample Template Created ---")
    except Exception as e:
        print(f"Error creating sample data: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)