import sqlite3
import pandas as pd
import numpy as np
from scipy.stats import poisson

# Database connection
conn = sqlite3.connect(
    "/home/levo/Documents/projects/prediction_league/data/database.db"
)


def fetch_fixtures_and_team_data(gameweek, conn):
    """
    Fetch fixtures for the given gameweek and team strength data.
    """
    fixtures_query = """
    SELECT 
        f.fixture_id, 
        f.home_teamid, 
        f.away_teamid, 
        t1.strength_attack_home AS home_attack, 
        t1.strength_defence_home AS home_defense, 
        t2.strength_attack_away AS away_attack, 
        t2.strength_defence_away AS away_defense
    FROM 
        fixtures f
    JOIN 
        teams t1 ON f.home_teamid = t1.team_id
    JOIN 
        teams t2 ON f.away_teamid = t2.team_id
    WHERE 
        f.gameweek = ?
    """
    fixtures_df = pd.read_sql_query(fixtures_query, conn, params=(gameweek,))
    return fixtures_df


def fetch_team_stats(conn):
    """
    Calculate average goals scored and conceded for each team based on past results.
    """
    query = """
    SELECT 
        r.season, 
        r.fixture_id, 
        f.home_teamid AS team_id, 
        r.home_goals AS goals_scored, 
        r.away_goals AS goals_conceded
    FROM results r
    JOIN fixtures f ON r.fixture_id = f.fixture_id
    UNION ALL
    SELECT 
        r.season, 
        r.fixture_id, 
        f.away_teamid AS team_id, 
        r.away_goals AS goals_scored, 
        r.home_goals AS goals_conceded
    FROM results r
    JOIN fixtures f ON r.fixture_id = f.fixture_id
    """
    results_df = pd.read_sql_query(query, conn)

    # Calculate averages grouped by team
    team_stats = results_df.groupby("team_id").agg(
        avg_goals_scored=("goals_scored", "mean"),
        avg_goals_conceded=("goals_conceded", "mean"),
    )
    return team_stats


def normalize_strengths(fixtures_df):
    """
    Normalize strength values to a range around 1.
    """
    avg_strength = (
        fixtures_df[["home_attack", "home_defense", "away_attack", "away_defense"]]
        .mean()
        .mean()
    )
    fixtures_df[
        ["home_attack", "home_defense", "away_attack", "away_defense"]
    ] /= avg_strength
    return fixtures_df


def calculate_expected_goals(
    row, team_stats, league_avg_goals=2.93, home_advantage=0.2
):
    """
    Calculate expected goals for the home and away teams using strengths and historical averages.
    """
    home_id = row["home_teamid"]
    away_id = row["away_teamid"]

    # Historical averages
    avg_home_goals_scored = team_stats.loc[home_id, "avg_goals_scored"]
    avg_home_goals_conceded = team_stats.loc[home_id, "avg_goals_conceded"]
    avg_away_goals_scored = team_stats.loc[away_id, "avg_goals_scored"]
    avg_away_goals_conceded = team_stats.loc[away_id, "avg_goals_conceded"]

    # Calculate expected goals
    home_expected_goals = (
        row["home_attack"]
        * row["away_defense"]
        * avg_home_goals_scored
        * avg_away_goals_conceded
        / league_avg_goals
        + home_advantage
    )
    away_expected_goals = (
        row["away_attack"]
        * row["home_defense"]
        * avg_away_goals_scored
        * avg_home_goals_conceded
        / league_avg_goals
    )
    return home_expected_goals, away_expected_goals


def predict_scores(fixtures_df, team_stats):
    """
    Predict scorelines for each fixture.
    """
    predictions = []
    for _, row in fixtures_df.iterrows():
        home_expected, away_expected = calculate_expected_goals(row, team_stats)

        # Poisson distributions for scores
        home_goals_dist = poisson.pmf(np.arange(0, 10), home_expected)
        away_goals_dist = poisson.pmf(np.arange(0, 10), away_expected)

        # Predict most likely scoreline
        most_likely_home_goals = np.argmax(home_goals_dist)
        most_likely_away_goals = np.argmax(away_goals_dist)

        predictions.append(
            {
                "fixture_id": row["fixture_id"],
                "home_teamid": row["home_teamid"],
                "away_teamid": row["away_teamid"],
                "home_goals": most_likely_home_goals,
                "away_goals": most_likely_away_goals,
            }
        )
    return pd.DataFrame(predictions)


def main(gameweek):
    """
    Main function to calculate score predictions for a given gameweek.
    """
    # Fetch fixtures and team strength data
    fixtures_df = fetch_fixtures_and_team_data(gameweek, conn)
    team_stats = fetch_team_stats(conn)

    # Normalize strength values
    fixtures_df = normalize_strengths(fixtures_df)

    # Predict scores
    predictions_df = predict_scores(fixtures_df, team_stats)

    print("Predictions for Gameweek", gameweek)
    print(predictions_df)
    return predictions_df


# Replace `gameweek` with the desired gameweek number
gameweek = 21
predictions = main(gameweek)

# Optionally save predictions to a database or CSV
# predictions.to_sql("predictions", conn, if_exists="replace", index=False)
# predictions.to_csv("predictions_gameweek_{}.csv".format(gameweek), index=False)
