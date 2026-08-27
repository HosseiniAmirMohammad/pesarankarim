import sqlite3
import database

print('init_db()...')
database.init_db()
conn = sqlite3.connect(r'c:\Users\Amirinteraction\Desktop\pesarankarim\pesarankarim.db')
print(conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='preuploaded_photos'").fetchone())
conn.close()
