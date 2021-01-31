import sqlite3
import pandas as pd

db = sqlite3.connect('/home/levo/Documents/projects/prediction_league/data/predictions.db')
c = db.cursor()

def result(home_goals, away_goals):
    if home_goals > away_goals: 
        return 1 # home win
    elif home_goals < away_goals: 
        return 2 # away win
    else:
        return 3 # draw

def correct_score(phome, paway, rhome, raway):
    if phome == rhome and paway == raway:
        return 1
    else:
        return 0
    
def correct_result(phome, paway, rhome, raway):
    if result(phome, paway) == result(rhome, raway):
        return 1
    else: 
        return 0


def score_players():
    c.executescript(''' DROP TABLE IF EXISTS score;
    
    CREATE TABLE "score" ( `player_id` INTEGER, 
        `fixture_id` INTEGER, 
        `predictions_id` INTEGER,
        `correct_score` INTEGER, 
        `correct_result` INTEGER, 
        `points` INTEGER )'''
    )

    predict_result_sql = ''' SELECT
        players.id as player_id,
        fixtures.id as fixture_id, 
        results.home_goals as results_home_goals, 
        results.away_goals as results_away_goals, 
        predictions.id as predictions_id,
        predictions.home_goals as predictions_home_goals, 
        predictions.away_goals as predictions_away_goals 
    FROM fixtures
    INNER JOIN results on results.fixture_id = fixtures.id 
    LEFT JOIN predictions on predictions.fixture_id = fixtures.id
    LEFT JOIN players on players.id = predictions.user_id 
    '''

    predict_df = pd.read_sql(predict_result_sql, db)
    predict_df['correct_score'] = predict_df.apply(lambda row: correct_score(row.predictions_home_goals, row.predictions_away_goals, row.results_home_goals, row.results_away_goals), axis=1)
    predict_df['correct_result'] = predict_df.apply(lambda row: correct_result(row.predictions_home_goals, row.predictions_away_goals, row.results_home_goals, row.results_away_goals), axis=1)
    predict_df['points'] = predict_df['correct_result'] + predict_df['correct_score']
    league_table = predict_df[['player_id','fixture_id','predictions_id','correct_score','correct_result', 'points']]
    league_table.to_sql('score' , db, if_exists='replace', index=False)

if __name__ == "__main__":
    score_players()