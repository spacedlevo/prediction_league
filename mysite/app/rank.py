import sqlite3
import pandas as pd
import seaborn as sns

import matplotlib.pyplot as plt

# Set seaborn style
sns.set(style="whitegrid")
# Connect to the SQLite database
conn = sqlite3.connect("data/database.db")

# Initialize a dictionary to store ranks
ranks = {}

# Iterate through gameweeks from 1 to 38
for gameweek in range(1, 24):
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
            JOIN fixtures ON fixtures.fixture_id = results.fixture_id
        WHERE 1=1
            AND fixtures.gameweek <= ?
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
    WHERE 1=1
        AND cp.player_id IN (13, 10, 1, 4, 20, 31)
    ORDER BY cp.current_position, cp.web_name
    """

    # Execute the query
    df = pd.read_sql_query(query, conn, params=(gameweek,))

    # Store the ranks
    for index, row in df.iterrows():
        if row["web_name"] not in ranks:
            ranks[row["web_name"]] = []
        ranks[row["web_name"]].append(row["current_position"])

# Close the database connection
conn.close()

# Plot the ranks
plt.figure(figsize=(12, 8))
for player, rank in ranks.items():
    plt.plot(range(1, 24), rank, label=player)
    plt.scatter(range(1, 24), rank, s=50)

plt.xlabel("Gameweek")
plt.ylabel("Rank")
plt.title("Player Ranks Over Gameweeks")
plt.legend()
plt.gca().invert_yaxis()  # Invert y-axis to show rank 1 at the top
plt.show()
