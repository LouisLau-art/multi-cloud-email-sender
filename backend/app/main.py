from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from .api import endpoints
from .core.database import engine, Base
from .core.scheduler import scheduler
from fastapi.staticfiles import StaticFiles
import os
import sys

app = FastAPI(title="Email Marketing System")

# CORS Configuration
# ... (keep existing CORS)

app.include_router(endpoints.router, prefix="/api")

# --- Static Files (Frontend Integration) ---
# 检查前端构建产物是否存在
# 在 PyInstaller 打包后，路径可能需要特殊处理，或者我们在打包时将 dist 放在同级
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "dist")

# 如果是通过 PyInstaller 运行 (_MEIPASS 是 PyInstaller 解压临时目录)
if getattr(sys, 'frozen', False):
    frontend_dist = os.path.join(sys._MEIPASS, "frontend_dist")

if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")

@app.on_event("startup")
def on_startup():
# ... (keep existing)
    start_scheduler()
    
    # Initialize Sample Data
    db = next(endpoints.get_db())
    try:
        if not db.query(endpoints.models.EmailTemplate).first():
            sample = endpoints.models.EmailTemplate(
                title="欢迎示例模板",
                subject="你好 {Name}，欢迎体验新系统！",
                body="<p>亲爱的 {Name}：</p><p>这是系统自动生成的测试模板。</p><p>如果您的 CSV 中包含 <b>Birthday</b> 列，它会显示在这里：{Birthday}</p>",
                from_alias="系统通知"
            )
            db.add(sample)
            db.commit()
            print("--- Sample Template Created ---")
    finally:
        db.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
