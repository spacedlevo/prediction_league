import requests
import json
import sys
import sqlite3
import pandas as pd
import pysftp as sftp
import json
from score_games import score_players


EVENT_URL = 'https://fantasy.premierleague.com/api/fixtures/?event='
DATABASE_FILE = '/home/levo/Documents/projects/prediction_league/data/predictions.db'
con = sqlite3.connect(DATABASE_FILE)
cur = con.cursor()

# Current GW is helpd in Dropbox to help sync with Siri Shortcuts.
# On rewrite may just take this directly from the API
with open('/home/levo/Dropbox/Apps/predictions_league/gameweek.txt') as f:
    gw = int(f.read().strip()) - 1

def create_table():
    cur.execute(''' 
    CREATE TABLE IF NOT EXISTS `results` (
        `id` INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
        `fixture_id` INTEGER,
        `home_goals` INTEGER,
        `away_goals` INTEGER )
    ''')

def add_to_database(results):
    results_data = []
    for row in results:
        cur.execute(''' SELECT id FROM fixtures WHERE home_teamid = ? AND away_teamid = ? ''',(row[0], row[1]))
        fixture_id = cur.fetchone()[0]
        results_data = [fixture_id, row[2], row[3]]
        cur.execute(''' 
            INSERT OR REPLACE INTO results (fixture_id, home_goals, away_goals) 
            VALUES (?, ?, ?) ''', 
            (results_data[0], results_data[1], results_data[2]))

    con.commit()


def print_results():
    print('entered')
    cur.execute('''
    SELECT
        home_team.name home_team,
        results.home_goals as results_home_goals,
        results.away_goals as results_away_goals,
        away_team.name away_team
    from fixtures
    inner join teams as away_team on away_team.id = fixtures.away_teamid
    inner join teams as home_team on home_team.id = fixtures.home_teamid
    left join results on results.fixture_id = fixtures.id
    where gameweek = ? AND results_home_goals NOT NULL ''', (gw, )
    )
    results_db = cur.fetchall()
    for i in results_db:
        print(f'{i[0].title()} {i[1]}-{i[2]} {i[3].title()}')



def upload_db():
    # SSH the new database to the website
    with open('/home/levo/Documents/projects/prediction_league/keys.json') as f:
        users_deets = json.load(f)

    with sftp.Connection(host='ssh.pythonanywhere.com', username=users_deets['user'], password=users_deets['psw']) as ftp:
        ftp.put(DATABASE_FILE, '/home/spacedlevo/predictions.db')





results = []
r = requests.get(f'{EVENT_URL}{gw}')
print(f'Getting {EVENT_URL}{gw}')
result_json = r.json()
for result in result_json:
    if result['started']:
        results.append([result['team_h'], result['team_a'], 
            result['team_h_score'], result['team_a_score']])


create_table()
add_to_database(results)
print_results()
score_players()
upload_db()
con.close()
