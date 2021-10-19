import sqlite3
from collections import Counter

database = 'data/archive/predictions.db'
with sqlite3.connect(database) as db:
    cur = db.cursor()
    cur.execute('SELECT home_goals, away_goals FROM results')
    results = cur.fetchall()

occurance_count = Counter(results)
print(occurance_count.most_common(10))