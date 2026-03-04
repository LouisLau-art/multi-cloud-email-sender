from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.database import get_db
import app.core.scheduler as scheduler_module
import app.api.endpoints as endpoints_module
# Import Base directly from models to guarantee it has the tables registered
from app.models.models import Base 
import app.models.models as models_module 
import httpx
import io
import datetime
import uuid

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
ADMIN_PASSWORD = "testpass123"


def _ensure_auth():
    status = client.get("/api/auth/status")
    if status.status_code == 200 and status.json().get("bootstrap_required"):
        response = client.post("/api/auth/bootstrap", json={"password": ADMIN_PASSWORD})
        assert response.status_code == 200


_ensure_auth()

# --- Tests ---

def test_settings_update_multicloud():
    """测试设置接口能否保存腾讯云字段"""
    response = client.post("/api/settings", json={
        "access_key_id": "ali_id",
        "access_key_secret": "ali_secret",
        "region_id": "cn-hangzhou",
        "tencent_secret_id": "tx_id",
        "track_domain": "https://track.example.com",
        "from_alias": "Test Sender"
    })
    assert response.status_code == 200
    
    response = client.get("/api/settings")
    data = response.json()
    assert data["has_access_key_id"] is True
    assert data["has_access_key_secret"] is True
    assert data["has_tencent_secret_id"] is True
    assert data["has_tencent_secret_key"] is False
    assert data["track_domain"] == "https://track.example.com"


def test_dashboard_stats_with_opened_and_clicked_statuses():
    """统计口径：sent/opened/clicked 都计入 sent_count 与 delivered_count"""
    db = TestingSessionLocal()
    try:
        db.query(models_module.CampaignRecipient).delete()
        db.commit()

        now = datetime.datetime.utcnow()
        rows = [
            models_module.CampaignRecipient(
                email="sent@test.com",
                tracking_id=str(uuid.uuid4()),
                status="sent",
                sent_at=now,
            ),
            models_module.CampaignRecipient(
                email="opened@test.com",
                tracking_id=str(uuid.uuid4()),
                status="opened",
                sent_at=now,
                opened_at=now,
            ),
            models_module.CampaignRecipient(
                email="clicked@test.com",
                tracking_id=str(uuid.uuid4()),
                status="clicked",
                sent_at=now,
                opened_at=now,
                clicked_at=now,
            ),
            models_module.CampaignRecipient(
                email="failed@test.com",
                tracking_id=str(uuid.uuid4()),
                status="failed",
                sent_at=now,
            ),
        ]
        db.add_all(rows)
        db.commit()
    finally:
        db.close()

    response = client.get("/api/dashboard/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_recipients"] == 4
    assert data["sent_count"] == 3
    assert data["delivered_count"] == 3
    assert data["opened_count"] == 2
    assert data["clicked_count"] == 1
    assert data["delivery_rate"] == 75.0
    assert data["open_rate"] == 66.67
    assert data["click_rate"] == 33.33


def test_send_campaign_batch_skips_overlapping_trigger(monkeypatch):
    """当已有执行中的批次任务时，新的触发应直接跳过，不再创建 DB 会话。"""

    class BusyLock:
        def acquire(self, blocking=False):
            return False

        def release(self):
            raise AssertionError("release should not be called when acquire fails")

    def fail_get_db_session():
        raise AssertionError(
            "get_db_session should not be called when trigger is skipped"
        )

    monkeypatch.setattr(scheduler_module, "_send_campaign_batch_lock", BusyLock())
    monkeypatch.setattr(scheduler_module, "get_db_session", fail_get_db_session)

    # Should return early without touching DB session.
    scheduler_module.send_campaign_batch()


def test_click_tracking_requires_registered_target():
    """点击追踪只允许跳转到发送时登记过的 URL，防止任意重定向"""
    tracking_id = str(uuid.uuid4())
    target = "https://example.com/path?a=1&b=2"

    db = TestingSessionLocal()
    try:
        db.query(models_module.CampaignRecipientLink).delete()
        db.query(models_module.CampaignRecipient).delete()
        db.commit()

        recipient = models_module.CampaignRecipient(
            email="click@test.com",
            tracking_id=tracking_id,
            status="sent",
            sent_at=datetime.datetime.utcnow(),
        )
        db.add(recipient)
        db.commit()

        # 未登记目标链接，应拒绝
        bad = client.get(
            f"/api/track/click/{tracking_id}",
            params={"target": target},
            follow_redirects=False,
        )
        assert bad.status_code == 404

        db.add(
            models_module.CampaignRecipientLink(
                tracking_id=tracking_id, target_url=target
            )
        )
        db.commit()

        ok = client.get(
            f"/api/track/click/{tracking_id}",
            params={"target": target},
            follow_redirects=False,
        )
        assert ok.status_code == 302
        assert ok.headers.get("location") == target

        db.refresh(recipient)
        assert recipient.clicked_at is not None
        assert recipient.opened_at is not None
        assert recipient.status == "clicked"
    finally:
        db.close()


def test_click_tracking_supports_mailto_target():
    """mailto 链接也应能被点击追踪并记录状态。"""
    tracking_id = str(uuid.uuid4())
    target = "mailto:someone@example.com?subject=hello"

    db = TestingSessionLocal()
    try:
        db.query(models_module.CampaignRecipientLink).delete()
        db.query(models_module.CampaignRecipient).delete()
        db.commit()

        recipient = models_module.CampaignRecipient(
            email="click-mailto@test.com",
            tracking_id=tracking_id,
            status="sent",
            sent_at=datetime.datetime.utcnow(),
        )
        db.add(recipient)
        db.commit()

        db.add(
            models_module.CampaignRecipientLink(
                tracking_id=tracking_id, target_url=target
            )
        )
        db.commit()

        # NOTE:
        # httpx TestClient currently raises InvalidURL on non-http redirect
        # schemes (mailto/tel/sms), even with follow_redirects=False.
        # Production behavior remains a 302 redirect, so we keep side-effect
        # assertions and only check response headers when client supports it.
        try:
            ok = client.get(
                f"/api/track/click/{tracking_id}",
                params={"target": target},
                follow_redirects=False,
            )
            assert ok.status_code == 302
            assert ok.headers.get("location") == target
        except httpx.InvalidURL:
            pass

        db.refresh(recipient)
        assert recipient.clicked_at is not None
        assert recipient.opened_at is not None
        assert recipient.status == "clicked"
    finally:
        db.close()


def test_click_tracking_rejects_unsupported_scheme():
    """非白名单协议（如 javascript:）必须拒绝。"""
    tracking_id = str(uuid.uuid4())
    target = "javascript:alert(1)"

    db = TestingSessionLocal()
    try:
        db.query(models_module.CampaignRecipientLink).delete()
        db.query(models_module.CampaignRecipient).delete()
        db.commit()

        recipient = models_module.CampaignRecipient(
            email="click-js@test.com",
            tracking_id=tracking_id,
            status="sent",
            sent_at=datetime.datetime.utcnow(),
        )
        db.add(recipient)
        db.commit()

        db.add(
            models_module.CampaignRecipientLink(
                tracking_id=tracking_id, target_url=target
            )
        )
        db.commit()

        bad = client.get(
            f"/api/track/click/{tracking_id}",
            params={"target": target},
            follow_redirects=False,
        )
        assert bad.status_code == 400

        db.refresh(recipient)
        assert recipient.clicked_at is None
        assert recipient.status == "sent"
    finally:
        db.close()


def test_linkify_plain_text_targets_converts_url_and_email():
    body = (
        "<p>官网 www.1000help.com，"
        "联系 lishijing@1000help.com 获取资料。</p>"
    )
    linked = scheduler_module.linkify_plain_text_targets(body)

    assert 'href="https://www.1000help.com"' in linked
    assert ">www.1000help.com</a>" in linked
    assert 'href="mailto:lishijing@1000help.com"' in linked


def test_linkify_plain_text_targets_keeps_existing_anchor():
    body = '<p><a href="https://already.example.com">already</a></p>'
    linked = scheduler_module.linkify_plain_text_targets(body)

    assert linked.count("<a ") == 1
    assert 'href="https://already.example.com"' in linked


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


def test_start_campaign_requeues_unfinished_recipients(monkeypatch):
    def _noop_add_job(*args, **kwargs):
        return None

    monkeypatch.setattr(endpoints_module.scheduler, "add_job", _noop_add_job)

    db = TestingSessionLocal()
    try:
        campaign = models_module.Campaign(
            name="retry-campaign",
            provider="aliyun",
            template_id=1,
            list_id=1,
            account_name="sender@test.com",
            status="completed",
            total_recipients=5,
            sent_count=5,
            batch_size=2000,
            interval_minutes=15,
        )
        db.add(campaign)
        db.flush()

        db.add_all(
            [
                models_module.CampaignRecipient(
                    campaign_id=campaign.id,
                    email="sent@test.com",
                    tracking_id=str(uuid.uuid4()),
                    status="sent",
                ),
                models_module.CampaignRecipient(
                    campaign_id=campaign.id,
                    email="opened@test.com",
                    tracking_id=str(uuid.uuid4()),
                    status="opened",
                ),
                models_module.CampaignRecipient(
                    campaign_id=campaign.id,
                    email="failed1@test.com",
                    tracking_id=str(uuid.uuid4()),
                    status="failed",
                    error_message="provider error",
                ),
                models_module.CampaignRecipient(
                    campaign_id=campaign.id,
                    email="failed2@test.com",
                    tracking_id=str(uuid.uuid4()),
                    status="failed",
                    error_message="network error",
                ),
                models_module.CampaignRecipient(
                    campaign_id=campaign.id,
                    email="sending@test.com",
                    tracking_id=str(uuid.uuid4()),
                    status="sending",
                ),
            ]
        )
        db.commit()
        campaign_id = campaign.id
    finally:
        db.close()

    response = client.post(f"/api/campaigns/{campaign_id}/start")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "started"
    assert payload["requeued_recipients"] == 3

    db = TestingSessionLocal()
    try:
        campaign = (
            db.query(models_module.Campaign)
            .filter(models_module.Campaign.id == campaign_id)
            .first()
        )
        assert campaign.status == "sending"
        assert campaign.sent_count == 2

        recipients = (
            db.query(models_module.CampaignRecipient)
            .filter(models_module.CampaignRecipient.campaign_id == campaign_id)
            .all()
        )
        statuses = [r.status for r in recipients]
        assert statuses.count("pending") == 3
        assert statuses.count("sent") == 1
        assert statuses.count("opened") == 1
    finally:
        db.close()


def test_recover_interrupted_campaigns_normalizes_partial_completed(monkeypatch):
    monkeypatch.setattr(scheduler_module, "get_db_session", TestingSessionLocal)

    db = TestingSessionLocal()
    try:
        partial_campaign = models_module.Campaign(
            name="partial-completed",
            provider="aliyun",
            template_id=1,
            list_id=1,
            account_name="sender@test.com",
            status="completed",
            total_recipients=4,
            sent_count=4,
            batch_size=2000,
            interval_minutes=15,
        )
        db.add(partial_campaign)
        db.flush()

        db.add_all(
            [
                models_module.CampaignRecipient(
                    campaign_id=partial_campaign.id,
                    email="p1@test.com",
                    tracking_id=str(uuid.uuid4()),
                    status="sent",
                ),
                models_module.CampaignRecipient(
                    campaign_id=partial_campaign.id,
                    email="p2@test.com",
                    tracking_id=str(uuid.uuid4()),
                    status="sent",
                ),
                models_module.CampaignRecipient(
                    campaign_id=partial_campaign.id,
                    email="p3@test.com",
                    tracking_id=str(uuid.uuid4()),
                    status="failed",
                ),
                models_module.CampaignRecipient(
                    campaign_id=partial_campaign.id,
                    email="p4@test.com",
                    tracking_id=str(uuid.uuid4()),
                    status="failed",
                ),
            ]
        )

        running_campaign = models_module.Campaign(
            name="running-campaign",
            provider="aliyun",
            template_id=1,
            list_id=1,
            account_name="sender@test.com",
            status="sending",
            total_recipients=2,
            sent_count=1,
            batch_size=2000,
            interval_minutes=15,
        )
        db.add(running_campaign)
        db.flush()

        db.add_all(
            [
                models_module.CampaignRecipient(
                    campaign_id=running_campaign.id,
                    email="r1@test.com",
                    tracking_id=str(uuid.uuid4()),
                    status="sending",
                ),
                models_module.CampaignRecipient(
                    campaign_id=running_campaign.id,
                    email="r2@test.com",
                    tracking_id=str(uuid.uuid4()),
                    status="sent",
                ),
            ]
        )

        db.commit()
        partial_campaign_id = partial_campaign.id
        running_campaign_id = running_campaign.id
    finally:
        db.close()

    scheduler_module.recover_interrupted_campaigns()

    db = TestingSessionLocal()
    try:
        partial_campaign = (
            db.query(models_module.Campaign)
            .filter(models_module.Campaign.id == partial_campaign_id)
            .first()
        )
        assert partial_campaign.status == "completed"
        assert partial_campaign.sent_count == 2

        running_campaign = (
            db.query(models_module.Campaign)
            .filter(models_module.Campaign.id == running_campaign_id)
            .first()
        )
        assert running_campaign.status == "sending"

        running_recipients = (
            db.query(models_module.CampaignRecipient)
            .filter(models_module.CampaignRecipient.campaign_id == running_campaign_id)
            .all()
        )
        running_statuses = [r.status for r in running_recipients]
        assert running_statuses.count("pending") == 1
        assert running_statuses.count("sent") == 1
    finally:
        db.close()


def test_finalize_campaign_status_keeps_terminal_campaign_completed():
    """
    任务只剩失败收件人时，不应被自动改为 paused。
    没有 pending/sending 就应保持 completed（终态）。
    """
    db = TestingSessionLocal()
    try:
        campaign = models_module.Campaign(
            name="terminal-with-failures",
            provider="aliyun",
            template_id=1,
            list_id=1,
            account_name="sender@test.com",
            status="sending",
            total_recipients=3,
            sent_count=0,
            batch_size=2000,
            interval_minutes=15,
        )
        db.add(campaign)
        db.flush()

        db.add_all(
            [
                models_module.CampaignRecipient(
                    campaign_id=campaign.id,
                    email="ok@test.com",
                    tracking_id=str(uuid.uuid4()),
                    status="sent",
                ),
                models_module.CampaignRecipient(
                    campaign_id=campaign.id,
                    email="fail1@test.com",
                    tracking_id=str(uuid.uuid4()),
                    status="failed",
                ),
                models_module.CampaignRecipient(
                    campaign_id=campaign.id,
                    email="fail2@test.com",
                    tracking_id=str(uuid.uuid4()),
                    status="failed",
                ),
            ]
        )
        db.commit()

        scheduler_module._finalize_campaign_status(db, campaign)
        db.commit()
        db.refresh(campaign)

        assert campaign.sent_count == 1
        assert campaign.status == "completed"
    finally:
        db.close()


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
