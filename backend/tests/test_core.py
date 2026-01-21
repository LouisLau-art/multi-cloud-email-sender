from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.database import get_db
# Import Base directly from models to guarantee it has the tables registered
from app.models.models import Base 
import app.models.models as models_module 
import io
import datetime

# Setup in-memory DB for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool 
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

# --- Tests ---

def test_settings_update_multicloud():
    """测试设置接口能否保存腾讯云字段"""
    response = client.post("/api/settings", json={
        "access_key_id": "ali_id",
        "access_key_secret": "ali_secret",
        "region_id": "cn-hangzhou",
        "tencent_secret_id": "tx_id",
        "from_alias": "Test Sender"
    })
    assert response.status_code == 200
    
    response = client.get("/api/settings")
    data = response.json()
    assert data["access_key_id"] == "ali_id"
    assert data["tencent_secret_id"] == "tx_id"

def test_csv_parsing_tab_delimiter():
    """测试 CSV 解析的暴力 Tab 拆分功能"""
    # 模拟一个 Excel 导出的 Tab 分隔文件 (UTF-16 常见，但这里简单模拟内容结构)
    # 假设它是被错误识别为单列的
    content = b"EmailAddr\tUserName\tGender\nlouis@test.com\tLouis\tMale"
    
    # 我们没法完全模拟 pandas 的失败，但我们可以测试 process_csv 能否处理这种 bytes
    files = {"file": ("tab_file.csv", content, "text/csv")}
    
    response = client.post("/api/contacts/upload", files=files, data={"list_name": "Tab List"})
    if response.status_code != 200:
        print(response.json())
        
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    
    # 验证变量是否解析正确 (这需要查库，或者信任 process_csv 的逻辑)
    # 我们可以通过发信日志侧面验证，但单元测试里很难 hook 日志。
    # 这里只要 200 OK 且 count=1，说明解析器至少没崩，且识别出了 EmailAddr。

def test_scheduled_campaign():
    """测试计划任务逻辑"""
    # 1. 准备数据
    client.post("/api/templates", json={"title": "T", "subject": "S", "body": "B", "from_alias": "F"})
    content = b"EmailAddr\na@a.com"
    client.post("/api/contacts/upload", files={"file": ("c.csv", content, "text/csv")}, data={"list_name": "L"})
    
    # 2. 创建未来任务
    future_time = (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).isoformat()
    response = client.post("/api/campaigns", json={
        "name": "Future Camp",
        "template_id": 1,
        "list_id": 1,
        "account_name": "sender@test.com",
        "scheduled_start_time": future_time
    })
    assert response.status_code == 200
    
    # 3. 验证状态
    # 此时并未 Start，状态应为 pending
    # 调用 Start 接口
    camp_id = response.json()["id"]
    res_start = client.post(f"/api/campaigns/{camp_id}/start")
    assert res_start.status_code == 200
    assert res_start.json()["status"] == "scheduled"
    
    # 4. 再验证 DB 状态
    res_list = client.get("/api/campaigns")
    camp = next(c for c in res_list.json() if c["id"] == camp_id)
    assert camp["status"] == "scheduled"