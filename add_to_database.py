import sqlite3
import csv
import sys

gw = sys.argv[1]
db = sqlite3.connect("data/database.db")
c = db.cursor()
predictions_file = f"data/predictions/predictions{gw}.csv"


with open(predictions_file) as f:
    csvreader = csv.reader(f)
    next(csvreader)
    for row in csvreader:
        print(row)
        c.execute(
            """ SELECT player_id FROM players WHERE player_name = ? """, (row[1],)
        )
        user_id = c.fetchone()[0]
        c.execute(
            """ SELECT team_id FROM teams WHERE team_name = ? """, (row[2].strip(),)
        )
        home_teamid = c.fetchone()[0]
        c.execute(
            """ SELECT team_id FROM teams WHERE team_name = ? """, (row[3].strip(),)
        )
        away_teamid = c.fetchone()[0]
        c.execute(
            """ SELECT fixture_id FROM fixtures WHERE home_teamid = ? AND away_teamid = ?""",
            (home_teamid, away_teamid),
        )
        fixture_id = c.fetchone()[0]
        home_goals = row[4]
        away_goals = row[5]
        c.execute(
            """ INSERT OR REPLACE INTO predictions (player_id, fixture_id, home_goals, away_goals) VALUES (?, ?, ?, ?)""",
            (user_id, fixture_id, home_goals, away_goals),
        )
db.commit()
db.close()
