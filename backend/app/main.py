from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from .api import endpoints
from .core.database import engine, Base
from .core.scheduler import start_scheduler
import uvicorn

# Create Tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Email Sender MVP")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"Validation Error: {exc.errors()}")
    print(f"Body: {await request.body()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": str(exc)},
    )

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(endpoints.router, prefix="/api")

@app.on_event("startup")
def on_startup():
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
