import sqlite3
from datetime import datetime

DB_PATH = "insurance_records.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_setting(key: str, default=None):
    conn = get_connection()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )
    conn.commit()
    conn.close()


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    # Seed defaults
    defaults = {
        "reminder_days":        "3",
        "scheduler_enabled":    "false",
        "scheduler_time":       "09:00",
        "scheduler_last_run":   "",
        "scheduler_last_result": "",
        "message_template": (
            "Dear {owner},\n\n"
            "This is a friendly reminder that your vehicle insurance is due for renewal.\n\n"
            "*Vehicle Number:* {vehicle}\n"
            "*Policy Number:* {policy}\n"
            "*Renewal Date:* {renewal}\n"
            "*Premium Amount:* Rs. {premium}\n"
            "*Status:* {days}\n\n"
            "Please renew before the due date to avoid policy lapse.\n\n"
            "For any queries, feel free to contact us.\n\n"
            "Thank you,\n"
            "Rahane Insurance Agency"
        ),
    }
    for key, value in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS insurance_records (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_name        TEXT,
            mobile_number     TEXT,
            policy_number     TEXT,
            vehicle_number    TEXT,
            chassis_number    TEXT,
            engine_number     TEXT,
            renewal_date      TEXT,
            payment_due_date  TEXT,
            premium_amount    TEXT,
            vehicle_make_model TEXT,
            issuing_office    TEXT,
            reminder_sent     INTEGER DEFAULT 0,
            reminder_sent_at  TEXT,
            pdf_filename      TEXT,
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def insert_record(data: dict) -> int:
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO insurance_records
            (owner_name, mobile_number, policy_number, vehicle_number,
             chassis_number, engine_number, renewal_date, payment_due_date,
             premium_amount, vehicle_make_model, issuing_office, pdf_filename)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data.get("owner_name"),
            data.get("mobile_number"),
            data.get("policy_number"),
            data.get("vehicle_number"),
            data.get("chassis_number"),
            data.get("engine_number"),
            data.get("renewal_date"),
            data.get("payment_due_date"),
            data.get("premium_amount"),
            data.get("vehicle_make_model"),
            data.get("issuing_office"),
            data.get("pdf_filename"),
        ),
    )
    conn.commit()
    record_id = cursor.lastrowid
    conn.close()
    return record_id


def get_all_records() -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM insurance_records ORDER BY renewal_date ASC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_record_by_id(record_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM insurance_records WHERE id = ?", (record_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_record(record_id: int, data: dict):
    allowed = {
        "owner_name", "mobile_number", "policy_number", "vehicle_number",
        "chassis_number", "engine_number", "renewal_date", "payment_due_date",
        "premium_amount", "vehicle_make_model", "issuing_office",
        "reminder_sent", "reminder_sent_at",
    }
    fields, values = [], []
    for field in allowed:
        if field in data:
            fields.append(f"{field} = ?")
            values.append(data[field])

    if not fields:
        return

    values.append(record_id)
    conn = get_connection()
    conn.execute(
        f"UPDATE insurance_records SET {', '.join(fields)} WHERE id = ?", values
    )
    conn.commit()
    conn.close()


def delete_record(record_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM insurance_records WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()
