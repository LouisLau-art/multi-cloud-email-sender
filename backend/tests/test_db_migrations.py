from sqlalchemy import create_engine, text

from app.core.db_migrations import run_startup_migrations


def _create_legacy_schema(engine):
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE settings ("
                "id INTEGER PRIMARY KEY, "
                "access_key_id VARCHAR, "
                "access_key_secret VARCHAR, "
                "region_id VARCHAR, "
                "tencent_secret_id VARCHAR, "
                "tencent_secret_key VARCHAR, "
                "tencent_region VARCHAR, "
                "from_alias VARCHAR, "
                "updated_at DATETIME"
                ")"
            )
        )
        conn.execute(
            text(
                "INSERT INTO settings ("
                "id, access_key_id, access_key_secret, region_id, "
                "tencent_secret_id, tencent_secret_key, tencent_region, from_alias"
                ") VALUES ("
                "1, 'ali_legacy_id', 'ali_legacy_secret', 'cn-hangzhou', "
                "'tx_legacy_id', 'tx_legacy_secret', 'ap-hongkong', 'LegacyAlias'"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE templates ("
                "id INTEGER PRIMARY KEY, "
                "title VARCHAR, "
                "subject VARCHAR, "
                "body TEXT, "
                "from_alias VARCHAR, "
                "provider VARCHAR, "
                "provider_id VARCHAR, "
                "created_at DATETIME"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE campaigns ("
                "id INTEGER PRIMARY KEY, "
                "name VARCHAR, "
                "provider VARCHAR, "
                "template_id INTEGER, "
                "list_id INTEGER, "
                "account_name VARCHAR, "
                "tag_name VARCHAR, "
                "from_alias VARCHAR, "
                "reply_to_address VARCHAR, "
                "status VARCHAR, "
                "total_recipients INTEGER, "
                "sent_count INTEGER, "
                "batch_size INTEGER, "
                "interval_minutes INTEGER, "
                "scheduled_start_time DATETIME, "
                "scheduled_at DATETIME, "
                "created_at DATETIME"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE campaign_recipients ("
                "id INTEGER PRIMARY KEY, "
                "campaign_id INTEGER, "
                "contact_id INTEGER, "
                "email VARCHAR, "
                "status VARCHAR, "
                "error_message TEXT, "
                "sent_at DATETIME, "
                "opened_at DATETIME, "
                "clicked_at DATETIME, "
                "tracking_id VARCHAR UNIQUE"
                ")"
            )
        )
        conn.execute(
            text(
                "INSERT INTO campaigns "
                "(id, name, provider, status) "
                "VALUES (1, 'legacy-campaign', 'aliyun', 'pending')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO templates "
                "(id, title, subject, body, provider, provider_id) "
                "VALUES (1, 'legacy-template', 's', 'b', 'aliyun', '1001')"
            )
        )


def _column_names(conn, table_name):
    rows = conn.execute(text(f"PRAGMA table_info({table_name})")).mappings().all()
    return {row["name"] for row in rows}


def test_startup_migration_upgrades_legacy_sqlite_schema(tmp_path):
    db_path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{db_path}")
    _create_legacy_schema(engine)

    run_startup_migrations(engine)
    run_startup_migrations(engine)  # idempotency check

    with engine.connect() as conn:
        settings_cols = _column_names(conn, "settings")
        campaign_cols = _column_names(conn, "campaigns")
        template_cols = _column_names(conn, "templates")
        recipient_cols = _column_names(conn, "campaign_recipients")

        assert "track_domain" in settings_cols
        assert "track_opens" in campaign_cols
        assert "track_clicks" in campaign_cols
        assert "account_id" in campaign_cols
        assert "account_id" in template_cols
        assert "message_id" in recipient_cols
        assert "provider" in recipient_cols

        track_opens, track_clicks = conn.execute(
            text("SELECT track_opens, track_clicks FROM campaigns WHERE id=1")
        ).fetchone()
        assert track_opens == 1
        assert track_clicks == 1

        link_table_exists = conn.execute(
            text(
                "SELECT 1 FROM sqlite_master "
                "WHERE type='table' AND name='campaign_recipient_links'"
            )
        ).fetchone()
        assert link_table_exists is not None

        cloud_accounts_exists = conn.execute(
            text(
                "SELECT 1 FROM sqlite_master "
                "WHERE type='table' AND name='cloud_accounts'"
            )
        ).fetchone()
        assert cloud_accounts_exists is not None

        aliyun_account_id = conn.execute(
            text(
                "SELECT id FROM cloud_accounts "
                "WHERE provider='aliyun' AND access_key_id='ali_legacy_id' LIMIT 1"
            )
        ).fetchone()
        assert aliyun_account_id is not None

        campaign_account_id = conn.execute(
            text("SELECT account_id FROM campaigns WHERE id=1")
        ).fetchone()[0]
        template_account_id = conn.execute(
            text("SELECT account_id FROM templates WHERE id=1")
        ).fetchone()[0]
        assert campaign_account_id == aliyun_account_id[0]
        assert template_account_id == aliyun_account_id[0]
