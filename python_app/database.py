import sqlite3
import json
import time

class DatabaseHandler:
    def __init__(self, db_path="jumps.db"):
        self.db_path = db_path
        self.conn = None
        self.init_db()

    def init_db(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        c = self.conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS jumps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            height_flight REAL,
            height_impulse REAL,
            peak_power REAL,
            avg_power REAL,
            flight_time REAL,
            jumper_weight REAL,
            velocity_takeoff REAL,
            max_force REAL,
            force_curve TEXT,
            formula_peak_power REAL,
            formula_avg_power REAL,
            velocity_flight REAL,
            contact_time REAL,
            contact_start_time REAL,
            contact_end_time REAL,
            curve_start_time REAL
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')
        
        # Add missing columns if upgrading from older schema
        try:
            c.execute("ALTER TABLE jumps ADD COLUMN formula_peak_power REAL")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE jumps ADD COLUMN formula_avg_power REAL")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE jumps ADD COLUMN velocity_flight REAL")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE jumps ADD COLUMN contact_time REAL")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE jumps ADD COLUMN contact_start_time REAL")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE jumps ADD COLUMN contact_end_time REAL")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE jumps ADD COLUMN curve_start_time REAL")
        except sqlite3.OperationalError:
            pass
            
        self.conn.commit()

    def save_jump(self, jump_data):
        curve_json = json.dumps(jump_data.get("force_curve", []))
        
        args = (
            jump_data.get("timestamp", time.time() * 1000),
            jump_data.get("height_flight"),
            jump_data.get("height_impulse", 0),
            jump_data.get("peak_power", 0),
            jump_data.get("avg_power", 0),
            jump_data.get("flight_time", 0),
            jump_data.get("jumper_weight", 0),
            jump_data.get("velocity_takeoff", 0),
            jump_data.get("max_force", 0),
            curve_json,
            jump_data.get("formula_peak_power"),
            jump_data.get("formula_avg_power"),
            jump_data.get("velocity_flight"),
            jump_data.get("contact_time"),
            jump_data.get("contact_start_time"),
            jump_data.get("contact_end_time"),
            jump_data.get("curve_start_time")
        )
        
        c = self.conn.cursor()
        c.execute('''INSERT INTO jumps 
                  (timestamp, height_flight, height_impulse, peak_power, avg_power, 
                   flight_time, jumper_weight, velocity_takeoff, max_force, force_curve,
                   formula_peak_power, formula_avg_power, velocity_flight, contact_time,
                   contact_start_time, contact_end_time, curve_start_time)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', args)
        self.conn.commit()
        return c.lastrowid

    def load_history(self, limit=50):
        c = self.conn.cursor()
        c.execute("SELECT * FROM jumps ORDER BY id DESC LIMIT ?", (limit,))
        rows = c.fetchall()
        
        # Get column names to handle schema variations gracefully
        col_names = [description[0] for description in c.description]
        col_idx = {name: i for i, name in enumerate(col_names)}
        
        history = []
        for r in rows:
            def get_val(name, default=None):
                idx = col_idx.get(name)
                return r[idx] if idx is not None and idx < len(r) else default

            j = {
                "_id": get_val("id"),
                "timestamp": get_val("timestamp"),
                "height_flight": get_val("height_flight"),
                "height_impulse": get_val("height_impulse"),
                "peak_power": get_val("peak_power"),
                "avg_power": get_val("avg_power"),
                "flight_time": get_val("flight_time"),
                "jumper_weight": get_val("jumper_weight"),
                "velocity_takeoff": get_val("velocity_takeoff"),
                "max_force": get_val("max_force"),
                "force_curve": [],
                "formula_peak_power": get_val("formula_peak_power"),
                "formula_avg_power": get_val("formula_avg_power"),
                "velocity_flight": get_val("velocity_flight"),
                "contact_time": get_val("contact_time"),
                "contact_start_time": get_val("contact_start_time"),
                "contact_end_time": get_val("contact_end_time"),
                "curve_start_time": get_val("curve_start_time")
            }
            
            # Remove None values to avoid 'contact_time' in j being true for None
            if j["contact_time"] is None:
                del j["contact_time"]
            
            curve_str = get_val("force_curve")
            if curve_str:
                try:
                    j["force_curve"] = json.loads(curve_str)
                except:
                    pass
                    
            history.append(j)
        return history

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
