import sqlite3
import json
conn = sqlite3.connect("jumps_data.db")
c = conn.cursor()
c.execute("PRAGMA table_info(jumps)")
cols = c.fetchall()
with open("cols_list.json", "w") as f:
    json.dump(cols, f)
conn.close()
