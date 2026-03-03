from sqlalchemy import text
from .security import encrypt_secret


def _table_exists(conn, table_name: str) -> bool:
    row = conn.execute(
        text(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name=:table_name LIMIT 1"
        ),
        {"table_name": table_name},
    ).fetchone()
    return row is not None


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    rows = conn.execute(text(f"PRAGMA table_info({table_name})")).mappings().all()
    return any(row["name"] == column_name for row in rows)


def _add_column_if_missing(conn, table_name: str, column_name: str, column_sql: str) -> None:
    if not _table_exists(conn, table_name):
        return
    if _column_exists(conn, table_name, column_name):
        return
    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}"))
    print(f"[DB-MIGRATION] Added column {table_name}.{column_name}")


def _query_one_mapping(conn, sql: str, params: dict | None = None):
    return conn.execute(text(sql), params or {}).mappings().first()


def _query_scalar(conn, sql: str, params: dict | None = None):
    row = conn.execute(text(sql), params or {}).fetchone()
    if not row:
        return None
    return row[0]


def _first_account_id(conn, provider: str):
    return _query_scalar(
        conn,
        "SELECT id FROM cloud_accounts WHERE provider=:provider "
        "AND COALESCE(enabled, 1)=1 ORDER BY id LIMIT 1",
        {"provider": provider},
    )


def _ensure_legacy_accounts_from_settings(conn):
    if not _table_exists(conn, "settings"):
        return

    setting = _query_one_mapping(
        conn,
        "SELECT * FROM settings ORDER BY id LIMIT 1",
    )
    if not setting:
        return

    # Aliyun legacy setting -> cloud_accounts
    if setting.get("access_key_id") and setting.get("access_key_secret"):
        existing_aliyun_id = _query_scalar(
            conn,
            "SELECT id FROM cloud_accounts "
            "WHERE provider='aliyun' AND access_key_id=:access_key_id "
            "ORDER BY id LIMIT 1",
            {"access_key_id": setting["access_key_id"]},
        )
        if not existing_aliyun_id:
            conn.execute(
                text(
                    "INSERT INTO cloud_accounts ("
                    "provider, name, access_key_id, access_key_secret, "
                    "region_id, from_alias, enabled, created_at, updated_at"
                    ") VALUES ("
                    "'aliyun', :name, :access_key_id, :access_key_secret, "
                    ":region_id, :from_alias, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP"
                    ")"
                ),
                {
                    "name": "Aliyun-1",
                    "access_key_id": setting.get("access_key_id"),
                    "access_key_secret": setting.get("access_key_secret"),
                    "region_id": setting.get("region_id") or "cn-hangzhou",
                    "from_alias": setting.get("from_alias"),
                },
            )
            print("[DB-MIGRATION] Created legacy Aliyun account from settings")

    # Tencent legacy setting -> cloud_accounts
    if setting.get("tencent_secret_id") and setting.get("tencent_secret_key"):
        existing_tencent_id = _query_scalar(
            conn,
            "SELECT id FROM cloud_accounts "
            "WHERE provider='tencent' AND tencent_secret_id=:tencent_secret_id "
            "ORDER BY id LIMIT 1",
            {"tencent_secret_id": setting["tencent_secret_id"]},
        )
        if not existing_tencent_id:
            conn.execute(
                text(
                    "INSERT INTO cloud_accounts ("
                    "provider, name, tencent_secret_id, tencent_secret_key, "
                    "tencent_region, from_alias, enabled, created_at, updated_at"
                    ") VALUES ("
                    "'tencent', :name, :tencent_secret_id, :tencent_secret_key, "
                    ":tencent_region, :from_alias, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP"
                    ")"
                ),
                {
                    "name": "Tencent-1",
                    "tencent_secret_id": setting.get("tencent_secret_id"),
                    "tencent_secret_key": setting.get("tencent_secret_key"),
                    "tencent_region": setting.get("tencent_region") or "ap-hongkong",
                    "from_alias": setting.get("from_alias"),
                },
            )
            print("[DB-MIGRATION] Created legacy Tencent account from settings")


def _backfill_account_links(conn):
    if _table_exists(conn, "templates") and _column_exists(conn, "templates", "account_id"):
        aliyun_id = _first_account_id(conn, "aliyun")
        if aliyun_id:
            conn.execute(
                text(
                    "UPDATE templates SET account_id=:account_id "
                    "WHERE account_id IS NULL AND provider='aliyun'"
                ),
                {"account_id": aliyun_id},
            )
        tencent_id = _first_account_id(conn, "tencent")
        if tencent_id:
            conn.execute(
                text(
                    "UPDATE templates SET account_id=:account_id "
                    "WHERE account_id IS NULL AND provider='tencent'"
                ),
                {"account_id": tencent_id},
            )

    if _table_exists(conn, "campaigns") and _column_exists(conn, "campaigns", "account_id"):
        aliyun_id = _first_account_id(conn, "aliyun")
        if aliyun_id:
            conn.execute(
                text(
                    "UPDATE campaigns SET account_id=:account_id "
                    "WHERE account_id IS NULL AND provider='aliyun'"
                ),
                {"account_id": aliyun_id},
            )
        tencent_id = _first_account_id(conn, "tencent")
        if tencent_id:
            conn.execute(
                text(
                    "UPDATE campaigns SET account_id=:account_id "
                    "WHERE account_id IS NULL AND provider='tencent'"
                ),
                {"account_id": tencent_id},
            )


def run_startup_migrations(engine) -> None:
    """
    Run lightweight, idempotent migrations for SQLite deployments.
    This keeps old `email_app.db` files compatible after model updates.
    """
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        # settings.track_domain
        _add_column_if_missing(
            conn,
            "settings",
            "track_domain",
            "track_domain VARCHAR DEFAULT 'http://192.168.2.8:8000'",
        )
        _add_column_if_missing(
            conn,
            "settings",
            "admin_password_hash",
            "admin_password_hash VARCHAR",
        )
        _add_column_if_missing(
            conn,
            "settings",
            "admin_password_salt",
            "admin_password_salt VARCHAR",
        )

        # campaigns.track_opens / track_clicks
        _add_column_if_missing(
            conn, "campaigns", "track_opens", "track_opens BOOLEAN DEFAULT 1"
        )
        _add_column_if_missing(
            conn, "campaigns", "track_clicks", "track_clicks BOOLEAN DEFAULT 1"
        )
        if _table_exists(conn, "campaigns"):
            conn.execute(
                text("UPDATE campaigns SET track_opens = 1 WHERE track_opens IS NULL")
            )
            conn.execute(
                text("UPDATE campaigns SET track_clicks = 1 WHERE track_clicks IS NULL")
            )

        # campaign_recipients.message_id / provider
        _add_column_if_missing(
            conn,
            "campaign_recipients",
            "message_id",
            "message_id VARCHAR",
        )
        _add_column_if_missing(
            conn,
            "campaign_recipients",
            "provider",
            "provider VARCHAR",
        )
        _add_column_if_missing(
            conn,
            "campaign_recipients",
            "name_snapshot",
            "name_snapshot VARCHAR",
        )
        _add_column_if_missing(
            conn,
            "campaign_recipients",
            "first_name_snapshot",
            "first_name_snapshot VARCHAR",
        )
        _add_column_if_missing(
            conn,
            "campaign_recipients",
            "middle_name_snapshot",
            "middle_name_snapshot VARCHAR",
        )
        _add_column_if_missing(
            conn,
            "campaign_recipients",
            "last_name_snapshot",
            "last_name_snapshot VARCHAR",
        )
        _add_column_if_missing(
            conn,
            "campaign_recipients",
            "extra_vars_snapshot",
            "extra_vars_snapshot TEXT",
        )
        _add_column_if_missing(
            conn,
            "campaign_recipients",
            "send_order",
            "send_order INTEGER",
        )
        if _table_exists(conn, "campaign_recipients"):
            conn.execute(
                text(
                    "UPDATE campaign_recipients "
                    "SET status='pending' "
                    "WHERE status IS NULL OR TRIM(status)=''"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS "
                    "ix_campaign_recipients_message_id "
                    "ON campaign_recipients (message_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS "
                    "ix_campaign_recipients_send_order "
                    "ON campaign_recipients (send_order)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS "
                    "ix_campaign_recipients_campaign_status "
                    "ON campaign_recipients (campaign_id, status)"
                )
            )

        # campaign_recipient_links table for click target allow-list
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS campaign_recipient_links ("
                "id INTEGER PRIMARY KEY, "
                "tracking_id VARCHAR NOT NULL, "
                "target_url TEXT NOT NULL, "
                "created_at DATETIME, "
                "FOREIGN KEY(tracking_id) REFERENCES campaign_recipients(tracking_id)"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "uq_campaign_recipient_link_target "
                "ON campaign_recipient_links (tracking_id, target_url)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_campaign_recipient_links_tracking_id "
                "ON campaign_recipient_links (tracking_id)"
            )
        )

        # cloud_accounts table
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS cloud_accounts ("
                "id INTEGER PRIMARY KEY, "
                "provider VARCHAR NOT NULL, "
                "name VARCHAR NOT NULL, "
                "access_key_id VARCHAR, "
                "access_key_secret VARCHAR, "
                "region_id VARCHAR DEFAULT 'cn-hangzhou', "
                "tencent_secret_id VARCHAR, "
                "tencent_secret_key VARCHAR, "
                "tencent_region VARCHAR DEFAULT 'ap-hongkong', "
                "from_alias VARCHAR, "
                "enabled BOOLEAN DEFAULT 1, "
                "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
                "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_cloud_accounts_provider ON cloud_accounts (provider)"
            )
        )

        # templates.account_id / campaigns.account_id
        _add_column_if_missing(
            conn,
            "templates",
            "account_id",
            "account_id INTEGER",
        )
        _add_column_if_missing(
            conn,
            "campaigns",
            "account_id",
            "account_id INTEGER",
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_templates_account_id ON templates (account_id)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_campaigns_account_id ON campaigns (account_id)"
            )
        )

        # contacts name parts
        _add_column_if_missing(
            conn,
            "contacts",
            "first_name",
            "first_name VARCHAR",
        )
        _add_column_if_missing(
            conn,
            "contacts",
            "middle_name",
            "middle_name VARCHAR",
        )
        _add_column_if_missing(
            conn,
            "contacts",
            "last_name",
            "last_name VARCHAR",
        )

        _ensure_legacy_accounts_from_settings(conn)
        _backfill_account_links(conn)

        # Encrypt legacy plaintext secrets in-place.
        if _table_exists(conn, "settings"):
            row = _query_one_mapping(
                conn,
                "SELECT id, access_key_secret, tencent_secret_key FROM settings ORDER BY id LIMIT 1",
            )
            if row:
                updates = {}
                if row.get("access_key_secret"):
                    updates["access_key_secret"] = encrypt_secret(row["access_key_secret"])
                if row.get("tencent_secret_key"):
                    updates["tencent_secret_key"] = encrypt_secret(row["tencent_secret_key"])
                if updates:
                    conn.execute(
                        text(
                            "UPDATE settings "
                            "SET access_key_secret=:access_key_secret, "
                            "tencent_secret_key=:tencent_secret_key "
                            "WHERE id=:id"
                        ),
                        {
                            "id": row["id"],
                            "access_key_secret": updates.get(
                                "access_key_secret", row.get("access_key_secret")
                            ),
                            "tencent_secret_key": updates.get(
                                "tencent_secret_key", row.get("tencent_secret_key")
                            ),
                        },
                    )

        if _table_exists(conn, "cloud_accounts"):
            rows = conn.execute(
                text(
                    "SELECT id, access_key_secret, tencent_secret_key FROM cloud_accounts"
                )
            ).mappings().all()
            for row in rows:
                encrypted_ak = encrypt_secret(row.get("access_key_secret"))
                encrypted_tk = encrypt_secret(row.get("tencent_secret_key"))
                conn.execute(
                    text(
                        "UPDATE cloud_accounts "
                        "SET access_key_secret=:access_key_secret, "
                        "tencent_secret_key=:tencent_secret_key "
                        "WHERE id=:id"
                    ),
                    {
                        "id": row["id"],
                        "access_key_secret": encrypted_ak,
                        "tencent_secret_key": encrypted_tk,
                    },
                )
