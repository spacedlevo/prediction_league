import sqlite3
import dropbox
from sys import argv

player_id = 11

db = sqlite3.connect('data/predictions.db')
c = db.cursor()
dbx = dropbox.Dropbox('byE-wqKe7LsAAAAAAAKj7Ye0ZDuRuqE43Udl8mznxQMjVSAtpCLm97whnpuRxW-M')
gw = argv[1]

c.execute(''' 
    select 
        home_team.name home_team, 
        predictions.home_goals,
        predictions.away_goals,
        away_team.name away_team
    from fixtures
    inner join teams as away_team on away_team.id = fixtures.away_teamid 
    inner join teams as home_team on home_team.id = fixtures.home_teamid 
    inner join predictions on predictions.fixture_id = fixtures.id
    WHERE user_id = 11 AND fixtures.gameweek = ?
        ''', (gw, ))

week_predictions = c.fetchall()
formatted_fix = []
for prediction in week_predictions:
    formatted_fix.append(f'{prediction[0].title()} {prediction[1]}-{prediction[2]} {prediction[3].title()}')

fixture_str = '\n'.join(formatted_fix)
print(fixture_str)
dbx.files_upload(str.encode(fixture_str), f'/predictions/gameweek{gw}.txt', mode=dropbox.files.WriteMode("overwrite"))
db.close()