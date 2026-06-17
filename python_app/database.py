import json
import sqlite3
import time


JUMP_SCHEMA = [
    ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
    ("timestamp", "REAL"),
    ("height_flight", "REAL"),
    ("height_impulse", "REAL"),
    ("peak_power", "REAL"),
    ("avg_power", "REAL"),
    ("flight_time", "REAL"),
    ("jumper_weight", "REAL"),
    ("velocity_takeoff", "REAL"),
    ("max_force", "REAL"),
    ("force_curve", "TEXT"),
    ("formula_peak_power", "REAL"),
    ("formula_avg_power", "REAL"),
    ("velocity_flight", "REAL"),
    ("contact_time", "REAL"),
    ("contact_start_time", "REAL"),
    ("contact_end_time", "REAL"),
    ("curve_start_time", "REAL"),
    ("unweighting_duration", "REAL"),
    ("braking_duration", "REAL"),
    ("propulsion_duration", "REAL"),
    ("time_unweighting_start", "REAL"),
    ("time_braking_start", "REAL"),
    ("time_propulsion_start", "REAL"),
    ("time_takeoff", "REAL"),
    ("jump_count", "INTEGER"),
    ("avg_height", "REAL"),
    ("best_height", "REAL"),
    ("avg_contact_time", "REAL"),
    ("best_contact_time", "REAL"),
    ("sub_jumps", "TEXT"),
]

INSERT_COLUMNS = [name for name, _ in JUMP_SCHEMA if name != "id"]
SUMMARY_COLUMNS = [
    name for name, _ in JUMP_SCHEMA
    if name not in {"force_curve", "sub_jumps"}
]

SAVE_DEFAULTS = {
    "timestamp": lambda: time.time() * 1000,
    "height_impulse": 0,
    "peak_power": 0,
    "avg_power": 0,
    "flight_time": 0,
    "jumper_weight": 0,
    "velocity_takeoff": 0,
    "max_force": 0,
}


class DatabaseHandler:
    def __init__(self, db_path="jumps.db"):
        self.db_path = db_path
        self.conn = None
        self.init_db()

    def init_db(self):
        self.conn = sqlite3.connect(self.db_path)
        c = self.conn.cursor()
        columns_sql = ",\n            ".join(
            f"{name} {definition}" for name, definition in JUMP_SCHEMA
        )
        c.execute(f"""CREATE TABLE IF NOT EXISTS jumps (
            {columns_sql}
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )""")

        self._ensure_jump_columns(c)
        self.conn.commit()

    def _ensure_jump_columns(self, cursor):
        existing = set(self._jump_column_names(cursor))
        for name, definition in JUMP_SCHEMA:
            if name not in existing:
                cursor.execute(f"ALTER TABLE jumps ADD COLUMN {name} {definition}")

    def _jump_column_names(self, cursor=None):
        cursor = cursor or self.conn.cursor()
        cursor.execute("PRAGMA table_info(jumps)")
        return [row[1] for row in cursor.fetchall()]

    def save_jump(self, jump_data):
        values = [self._value_for_insert(column, jump_data) for column in INSERT_COLUMNS]
        placeholders = ", ".join("?" for _ in INSERT_COLUMNS)
        column_sql = ", ".join(INSERT_COLUMNS)

        c = self.conn.cursor()
        c.execute(
            f"INSERT INTO jumps ({column_sql}) VALUES ({placeholders})",
            values,
        )
        self.conn.commit()
        return c.lastrowid

    def _value_for_insert(self, column, jump_data):
        if column == "force_curve":
            return json.dumps(jump_data.get("force_curve", []))
        if column == "sub_jumps":
            sub_jumps = jump_data.get("sub_jumps")
            return json.dumps(sub_jumps) if sub_jumps else None

        default = SAVE_DEFAULTS.get(column)
        if callable(default):
            default = default()
        return jump_data.get(column, default)

    def load_history(self, limit=50, include_curves=False):
        columns = self._selectable_columns(include_curves=include_curves)
        c = self.conn.cursor()
        c.execute(
            f"SELECT {', '.join(columns)} FROM jumps ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = c.fetchall()
        return [
            self._row_to_jump(row, columns, parse_curves=include_curves)
            for row in rows
        ]

    def load_jump(self, jump_id):
        columns = self._selectable_columns(include_curves=True)
        c = self.conn.cursor()
        c.execute(
            f"SELECT {', '.join(columns)} FROM jumps WHERE id = ?",
            (jump_id,),
        )
        row = c.fetchone()
        if row is None:
            return None
        return self._row_to_jump(row, columns, parse_curves=True)

    def _selectable_columns(self, include_curves):
        desired = [name for name, _ in JUMP_SCHEMA] if include_curves else SUMMARY_COLUMNS
        available = set(self._jump_column_names())
        return [name for name in desired if name in available]

    def _row_to_jump(self, row, columns, parse_curves):
        data = dict(zip(columns, row))
        jump = {"_id": data.pop("id", None)}
        jump.update(data)

        if parse_curves:
            jump["force_curve"] = self._parse_json_list(jump.get("force_curve"))
            sub_jumps = self._parse_json_list(jump.get("sub_jumps"))
            if sub_jumps:
                jump["sub_jumps"] = sub_jumps
            else:
                jump.pop("sub_jumps", None)
            jump["_curve_loaded"] = True
        else:
            jump["force_curve"] = []
            jump["_curve_loaded"] = False

        if jump.get("contact_time") is None:
            jump.pop("contact_time", None)
        return jump

    def _parse_json_list(self, value):
        if not value:
            return []
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []

    def delete_jump(self, jump_id):
        c = self.conn.cursor()
        c.execute("DELETE FROM jumps WHERE id = ?", (jump_id,))
        self.conn.commit()
        return c.rowcount

    def clear(self):
        c = self.conn.cursor()
        c.execute("DELETE FROM jumps")
        self.conn.commit()

    def save_setting(self, key, value):
        c = self.conn.cursor()
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        self.conn.commit()

    def load_setting(self, key, default=None):
        c = self.conn.cursor()
        c.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = c.fetchone()
        return row[0] if row else default
