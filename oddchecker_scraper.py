from time import sleep
import re
import sys
import sqlite3

import requests
from bs4 import BeautifulSoup

db = sqlite3.connect('data/predictions.db')
c = db.cursor()
gw = sys.argv[1]
headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}


baseurl = 'http://www.oddschecker.com/'
sport = 'football/'
country = 'english/'
league = 'premier-league/'
market = 'correct-score/'


def get_fixtures(gw):
    sql_statement = f'''
        SELECT
            fixtures.id,
            home_team.name home_team,
            away_team.name away_team
        FROM fixtures
        inner join teams as away_team on away_team.id = fixtures.away_teamid 
        inner join teams as home_team on home_team.id = fixtures.home_teamid 
        WHERE gameweek = {gw}
    '''
    c.execute(sql_statement)
    return c.fetchall()

def parse_winner(result):
    teamRegex = re.compile(r'^\D+')
    winner = teamRegex.findall(result)
    winner = ''.join(winner)
    winner = winner.rstrip()
    return winner.lower()

def parse_score(score):
    score_regex = re.compile(r'\d-\d')
    result = score_regex.findall(score)
    result = result[0].split('-')
    return result

def fixture_dictonary(fixture_tup, score):
    fixture = {}
    fixture['id'] = fixture_tup[0]
    fixture['home'] = fixture_tup[1]
    fixture['away'] = fixture_tup[2]
    fixture['score'] = parse_score(score)
    fixture['result'] = parse_winner(score)
    return fixture


def check_draw(fixture):
    goals = parse_score(fixture)
    if goals[0] == goals[1]:
        return True
    else:
        return False



def get_oddschecker(fixtures):
    gameweek_data = []
    for fixture in fixtures:
        join_fixture = '-v-'.join(fixture[1:]).replace(' ', '-')  # cleans fixture for url
        url = baseurl + sport + country + league + join_fixture + '/' + market
        print(url)
        try:
            r = requests.get(url, headers=headers)
        except Exception as e:
            print(e)


        soup = BeautifulSoup(r.content, "html.parser")
        tableData = soup.find_all("td", class_="sel nm basket-active")
        for row in tableData:
            print(row.text.strip())
            try:
                if check_draw(row.text.strip()):
                    continue
                elif row.text.strip().lower == 'any other score':
                    continue
                else:
                    score = row.text.strip()
                    gameweek_data.append(fixture_dictonary(fixture, score))
                    break
            except IndexError:
                continue

    return gameweek_data


def write_to_db(gameweek_data):
    for fixture in gameweek_data:
        if fixture['result'] != fixture['home']:
            res = (11, fixture['id'], fixture['score'][1], fixture['score'][0])
        else:
            res = (11, fixture['id'], fixture['score'][0], fixture['score'][1])
        c.execute(''' INSERT OR REPLACE INTO predictions
        (user_id, fixture_id, home_goals, away_goals) VALUES 
        (?,?,?,?) ''', res)
    db.commit()
    return print(f'Added {len(gameweek_data)} predictions')


week_fixtures = get_fixtures(gw)
gameweek_dict = get_oddschecker(week_fixtures)
write_to_db(gameweek_dict)
db.close()