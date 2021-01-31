import sqlite3

db = 'data/predictions.db'
conn = sqlite3.connect(db)
c = conn.cursor()

gw = input("Which gameweek do you want? ")

def get_fixtures(gameweek):
    c.execute(''' 
        SELECT
            fixtures.id,
            home_team.name home_team,
            away_team.name away_team
        FROM fixtures
        inner join teams as away_team on away_team.id = fixtures.away_teamid 
        inner join teams as home_team on home_team.id = fixtures.home_teamid 
        WHERE gameweek = ?
        ''', (gameweek, ))
    
    fixtures = c.fetchall()
    return fixtures

def get_predictions(fixture_id):
    c.execute('''select
        players.name as player,
        home_team.name home_team,
        predictions.home_goals as predictions_home_goals,
        away_team.name away_team,
        predictions.away_goals as predictions_away_goals
    from fixtures
    inner join teams as away_team on away_team.id = fixtures.away_teamid
    inner join teams as home_team on home_team.id = fixtures.home_teamid
    left join predictions on predictions.fixture_id = fixtures.id
    join players on players.id = predictions.user_id
    where gameweek = ? and fixtures.id = ? 
    ORDER BY player;''', (gw, fixture_id))
    return c.fetchall()

count = {'h':0, 'd':0, 'a':0}
def count_predictions(fixture):
    if fixture[2] > fixture[4]:
        count['h'] += 1
    elif fixture[4] > fixture[2]:
        count['a'] += 1
    else:
        count['d'] += 1

    

 
for i in get_fixtures(gw):
    print(i)

fix_id = input("Which fixture? ")
print('\n')

for i in get_predictions(fix_id):
    count_predictions(i)
    print(' '.join(map(str, i)).title())

print('\n')
print(f"Home Wins: {count['h']}, Draw: {count['d']}, Away Wins {count['a']}" )