import sqlite3 as sql

con = sql.connect("data/database.db")
cur = con.cursor()

cur.executescript(
    """CREATE TABLE IF NOT EXISTS "players" (
	"player_id"	INTEGER NOT NULL,
	"player_name" TEXT,
	"paid"	INTEGER,
	"active"	INTEGER NOT NULL DEFAULT 1,
	PRIMARY KEY("player_id"),
	UNIQUE("player_id")
)"""
)

cur.execute(
    """
    CREATE TABLE IF NOT EXISTS "predictions" (
	"id"	INTEGER NOT NULL UNIQUE,
	"player_id"	INTEGER,
	"fixture_id"	INTEGER,
	"home_goals"	INTEGER,
	"away_goals"	INTEGER,
	"season"	TEXT NOT NULL DEFAULT '2024/25',
	PRIMARY KEY("id" AUTOINCREMENT)
)"""
)

cur.execute(
    """CREATE TABLE IF NOT EXISTS fixtures (
            fixture_id INTEGER NOT NULL, 
            kickoff_dttm DATETIME, 
            gameweek INTEGER, 
            home_teamid INTEGER NOT NULL, 
            away_teamid INTEGER NOT NULL, 
            finished BOOLEAN, 
            season TEXT,
            PRIMARY KEY (fixture_id, season), 
            UNIQUE (fixture_id, season)
        )"""
)

cur.execute(
    """CREATE TABLE IF NOT EXISTS "last_update" (
    "table_name"	TEXT PRIMARY KEY,
    "updated"	TEXT
)"""
)

cur.execute(
    """CREATE TABLE IF NOT EXISTS "results" (
	"id"	INTEGER UNIQUE,
	"fixture_id"	INTEGER UNIQUE,
	"home_goals"	INTEGER,
	"away_goals"	INTEGER,
	"season"	TEXT NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT)
)"""
)


cur.execute(
    """CREATE TABLE IF NOT EXISTS teams (
            team_id INTEGER NOT NULL, 
            team_name TEXT, 
            unavailable BOOLEAN, 
            PRIMARY KEY (team_id)
        )"""
)

cur.execute(
    """
    CREATE TABLE IF NOT EXIST gameweeks (
            gameweek INTEGER NOT NULL,
            deadline_dttm DATETIME,
            deadline_date DATE,
            deadline_time TIME,
            PRIMARY KEY (gameweek)
        )
    """
)


con.commit()
con.close()
