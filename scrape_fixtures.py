import sqlite3
import requests
import dropbox
from config import keys
from time import sleep
from tqdm import tqdm


dbx = dropbox.Dropbox(keys['dropbox'])

base_url = f'https://fantasy.premierleague.com/api/fixtures/?event='
bootstrap = 'https://fantasy.premierleague.com/api/bootstrap-static/'
con = sqlite3.connect('data/predictions.db')
cur = con.cursor() 

def gameweeks():
    r = requests.get(bootstrap)
    data = r.json()['events']
    return len(data)

    

def create_table():
    url = bootstrap
    cur.executescript(
        '''
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY,
            name TEXT
        );
        '''
    )
    cur.execute('SELECT * FROM teams')
    teams = cur.fetchall()
    if len(teams) == 0:
        r = requests.get(url)
        teams = r.json()['teams']
        team_list = []
        for team in teams:
            team_list.append((team['id'], team['name'].lower()))
        con.executemany('INSERT INTO teams VALUES (?, ?)', (team_list))
    con.commit()

def add_fixtures(gw):
    cur.executescript(
        '''
        DROP TABLE fixtures;

        CREATE TABLE IF NOT EXISTS fixtures (
            `id` INTEGER NOT NULL PRIMARY KEY UNIQUE,
            `gameweek` INTEGER,
            `home_teamid` INTEGER NOT NULL,
            `away_teamid` INTEGER NOT NULL 
        );
        '''
    )

    fixtures_list = []

    for gw in tqdm(range(1, gw + 1)):
        r = requests.get(f'{base_url}{gw}')
        sleep(1)
        json_data = r.json()
        for fixture in json_data:
            fixtures_list.append((fixture['id'], gw, fixture['team_h'], fixture['team_a']))
    cur.executemany('INSERT INTO fixtures VALUES (?, ?, ?, ?)', fixtures_list)
    con.commit()


def create_text_files(gw):
    for week in tqdm(range(1, gw + 1)):
        cur.execute(''' 
            SELECT
                home_team.name home_team,
                away_team.name away_team
            FROM fixtures
            inner join teams as away_team on away_team.id = fixtures.away_teamid 
            inner join teams as home_team on home_team.id = fixtures.home_teamid 
            WHERE gameweek = ?
            ''', (week, ))

        fixtures = cur.fetchall()
        formatted_fixtures = [' - '.join(fixture).title() for fixture in fixtures]
        formatted_fixtures = '\n'.join(formatted_fixtures)
        dbx.files_upload(str.encode(formatted_fixtures), f'/fixtures/fixtures{week}.txt', mode=dropbox.files.WriteMode("overwrite"))

    

def main():
    rounds = gameweeks()
    create_table()
    add_fixtures(rounds)
    create_text_files(rounds)

if __name__ == "__main__":
    main()
