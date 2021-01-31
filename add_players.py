import sqlite3 as sql

db = sql.connect('data/archive/predictions.db')

c = db.cursor()

with db: 
    c.execute("SELECT * FROM players")
    players = c.fetchall()

db = sql.connect('data/predictions.db')
c = db.cursor()

with db:
    for player in players:
        c.execute("INSERT INTO players(name, paid) VALUES (?, ?) ", (player[1], 0))
        db.commit()