import sqlite3 as sql
import pandas as pd
import time
from collections import Counter

db = sql.connect('data/predictions.db')
cur = db.cursor()

def get_gameweeks():
    cur.execute('SELECT fixtures.gameweek FROM results JOIN fixtures on fixtures.id = results.fixture_id ORDER BY gameweek DESC')
    gws = cur.fetchone()[0]
    return gws

def get_gameweek_results(gw, player_1, player_2):
    player_results = '''
        SELECT
            players.name as player,
            score.correct_score,
            score.correct_result,
            score.points
        FROM players
        JOIN score on score.player_id = players.id
        JOIN fixtures on fixtures.id = score.fixture_id
        WHERE gameweek = ? AND (player_id = ? OR player_id = ?)
        '''
    
    df = pd.read_sql(player_results, db, params=[gw, player_1, player_2])
    gw_totals = df.groupby('player').sum()
    gw_totals.reset_index(inplace=True)
    winner = gw_totals[gw_totals['points']==gw_totals['points'].max()]
    if len(winner) == 1:
        return winner.player.values[0]
    elif len(winner) == 2:
        winner = winner[winner['correct_result'] == winner['correct_result'].max()]
        return winner.player.values[0]
    else:
        return None


gw = get_gameweeks()
winners = []
for i in range(1, gw):
    gw_winner = get_gameweek_results(i, 2, 26)
    if gw_winner is not None:
        winners.append(gw_winner)
print(Counter(winners))

