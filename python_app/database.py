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
            force_curve TEXT
        )''')
        self.conn.commit()

    def save_jump(self, jump_data):
        curve_json = json.dumps(jump_data.get("force_curve", []))
        
        args = (
            jump_data.get("timestamp", time.time() * 1000),
            jump_data.get("height_flight", 0),
            jump_data.get("height_impulse", 0),
            jump_data.get("peak_power", 0),
            jump_data.get("avg_power", 0),
            jump_data.get("flight_time", 0),
            jump_data.get("jumper_weight", 0),
            jump_data.get("velocity_takeoff", 0),
            jump_data.get("max_force", 0),
            curve_json
        )
        
        c = self.conn.cursor()
        c.execute('''INSERT INTO jumps 
                  (timestamp, height_flight, height_impulse, peak_power, avg_power, flight_time, jumper_weight, velocity_takeoff, max_force, force_curve)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', args)
        self.conn.commit()
        return c.lastrowid

    def load_history(self, limit=50):
        c = self.conn.cursor()
        c.execute("SELECT * FROM jumps ORDER BY id DESC LIMIT ?", (limit,))
        rows = c.fetchall()
        
        history = []
        for r in rows:
            # Map back to dict
            j = {
                "_id": r[0],
                "timestamp": r[1],
                "height_flight": r[2],
                "height_impulse": r[3],
                "peak_power": r[4],
                "avg_power": r[5],
                "flight_time": r[6],
                "jumper_weight": r[7],
                "velocity_takeoff": r[8],
                "max_force": r[9],
                "force_curve": json.loads(r[10])
            }
            history.append(j)
        return history

    def clear(self):
        c = self.conn.cursor()
        c.execute("DELETE FROM jumps")
        self.conn.commit()
