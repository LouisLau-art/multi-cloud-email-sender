from sqlalchemy import text


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
    if _column_exists(conn, table_name, column_name):
        return
    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}"))
    print(f"[DB-MIGRATION] Added column {table_name}.{column_name}")


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
        if _table_exists(conn, "campaign_recipients"):
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS "
                    "ix_campaign_recipients_message_id "
                    "ON campaign_recipients (message_id)"
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

