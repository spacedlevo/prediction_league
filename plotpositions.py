import pandas as pd
import sqlite3
import seaborn as sns

import matplotlib.pyplot as plt

# Set seaborn theme
sns.set_theme(style="darkgrid")

# Connect to your database
conn = sqlite3.connect("data/database.db")


# Function to get data for each gameweek
def get_gameweek_data(gameweek):
    query = """
    WITH current_table AS (
        SELECT
            players.web_name,
            players.player_id,
            players.paid,
            predictions.fixture_id,
            predictions.home_goals AS [predicted home goals],
            predictions.away_goals AS [predicted away goals],
            results.home_goals,
            results.away_goals,
            CASE
                WHEN
                    CASE
                        WHEN predictions.home_goals > predictions.away_goals THEN 'home win'
                        WHEN predictions.home_goals < predictions.away_goals THEN 'away win'
                        WHEN predictions.home_goals = predictions.away_goals THEN 'draw'
                    END =
                    CASE
                        WHEN results.home_goals > results.away_goals THEN 'home win'
                        WHEN results.home_goals < results.away_goals THEN 'away win'
                        WHEN results.home_goals = results.away_goals THEN 'draw'
                    END
                THEN 1
                ELSE 0
            END AS [correct result point],
            CASE
                WHEN (predictions.home_goals = results.home_goals) AND (predictions.away_goals = results.away_goals) THEN 1
                ELSE 0
            END AS [correct score point]
        FROM predictions
            JOIN results ON results.fixture_id = predictions.fixture_id
            JOIN players ON players.player_id = predictions.player_id
            JOIN fixtures ON fixtures.fixture_id = predictions.fixture_id
        WHERE fixtures.gameweek <= ?
            AND players.player_id IN (13,20,1,31,4,10)
        GROUP BY players.web_name, players.player_id, players.paid, predictions.fixture_id, predictions.home_goals, predictions.away_goals, results.home_goals, results.away_goals
    ),
    current_position AS (
        SELECT
            ROW_NUMBER() OVER (ORDER BY SUM([correct result point] + [correct score point]) DESC, SUM([correct result point]) DESC, SUM([correct score point]) DESC, web_name) AS [current_position],
            web_name,
            player_id,
            paid,
            SUM([correct result point]) AS [Correct Result],
            SUM([correct score point]) AS [Correct Score],
            SUM([correct result point] + [correct score point]) AS [Total Points]
        FROM current_table
        GROUP BY web_name, player_id, paid
    )
    SELECT
        cp.current_position,
        cp.web_name,
        cp.player_id,
        cp.paid,
        cp.[Correct Result],
        cp.[Correct Score],
        cp.[Total Points]
    FROM current_position cp
    ORDER BY cp.current_position, cp.web_name;
    """
    return pd.read_sql_query(query, conn, params=(gameweek,))


# Get the maximum gameweek
max_gameweek = pd.read_sql_query(
    "SELECT gameweek FROM gameweeks WHERE current_gameweek = 1", conn
).iloc[0, 0]

# Initialize lists to store data for plotting
gameweeks = list(range(1, max_gameweek + 1))
player_ranks = {}
player_points = {}

# Iterate through each gameweek and collect data
for gameweek in gameweeks:
    data = get_gameweek_data(gameweek)
    for _, row in data.iterrows():
        player = row["web_name"]
        if player not in player_ranks:
            player_ranks[player] = []
            player_points[player] = []
        player_ranks[player].append(row["current_position"])
        player_points[player].append(row["Total Points"])

# Plot player ranks for each gameweek
plt.figure(figsize=(14, 7))
for player, ranks in player_ranks.items():
    plt.plot(gameweeks, ranks, label=player)
plt.xlabel("Gameweek")
plt.ylabel("Rank")
plt.title("Player Rank by Gameweek")
plt.legend()
plt.gca().invert_yaxis()  # Invert y-axis to show rank 1 at the top
plt.savefig("data/rank.png")
plt.show()

# Plot total points for each gameweek
plt.figure(figsize=(14, 7))
for player, points in player_points.items():
    plt.plot(gameweeks, points, label=player)
plt.xlabel("Gameweek")
plt.ylabel("Total Points")
plt.title("Player Total Points by Gameweek")
plt.legend()
plt.savefig("data/points.png")
plt.show()

# Close the database connection
conn.close()
