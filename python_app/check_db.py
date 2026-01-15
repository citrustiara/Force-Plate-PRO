import sqlite3
conn = sqlite3.connect("jumps_data.db")
c = conn.cursor()
c.execute("PRAGMA table_info(jumps)")
cols = c.fetchall()
for col in cols:
    print(col)
conn.close()
