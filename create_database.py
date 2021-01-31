import sqlite3 as sql

con = sql.connect('data/predictions.db')
cur = con.cursor()

cur.executescript('''CREATE TABLE IF NOT EXISTS "players" (
	`id`	INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
	`name`	TEXT,
	`paid`	INTEGER DEFAULT 0
)''')

cur.executescript('''
    CREATE TABLE IF NOT EXISTS "predictions" (
        `id`	INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
        `user_id`	INTEGER,
        `fixture_id`	INTEGER,
        `home_goals`	INTEGER,
        `away_goals`	INTEGER
)
''')
con.commit()
con.close()