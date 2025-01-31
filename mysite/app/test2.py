import sqlite3
import pprint

db_dir = "data/database.db"
season = "2024/25"

db = sqlite3.connect(db_dir)
c = db.cursor()

c.execute(
    """
WITH playerscte AS (
    SELECT player_id, web_name FROM players WHERE active = 1
),
gameweekscte AS (
    SELECT DISTINCT 
        fixtures.gameweek
    FROM 
        fixtures
        JOIN predictions ON predictions.fixture_id = fixtures.fixture_id
    WHERE gameweek IS NOT NULL AND fixtures.season = ?
)

SELECT
    gw.gameweek,
    p.web_name,
    IFNULL(ninenine.count, 0) AS count
FROM 
    gameweekscte gw
CROSS JOIN 
    playerscte p
LEFT JOIN 
    (
        SELECT
            pl.player_id,
            F.gameweek,
            COUNT(*) AS count
        FROM 
            predictions AS P
        JOIN players AS pl ON pl.player_id = P.player_id
        JOIN fixtures AS F ON F.fixture_id = P.fixture_id
        WHERE P.home_goals = 9 AND P.away_goals = 9
            AND p.season = ?
        GROUP BY F.gameweek, pl.player_id
    ) AS ninenine 
ON ninenine.player_id = p.player_id AND ninenine.gameweek = gw.gameweek
ORDER BY gw.gameweek, p.web_name;

""",
    (season, season),
)
predictions_9_9 = c.fetchall()

max_gameweek = max([i[0] for i in predictions_9_9 if i[0] is not None])
# Last updated time and date of the table
c.execute("SELECT * FROM last_update")
last_updated = c.fetchall()
players = set([i[1] for i in predictions_9_9])

predictions_9_9_dict = {player: [0] * max_gameweek for player in players}
for gw, player, count in predictions_9_9:
    predictions_9_9_dict[player][gw - 1] = count

predictions_9_9_list = [
    [player] + counts for player, counts in predictions_9_9_dict.items()
]

number_of_players = len(players)


c.execute(
    """
    SELECT 
        gameweek, 
        COUNT(*) 
    FROM fixtures 
    GROUP BY gameweek
    """
)
fixture_counts = c.fetchall()
fixture_counts_dict = {i[0]: i[1] for i in fixture_counts}
not_submitted = sum(
    1
    for player_data in predictions_9_9_list
    if player_data[-1] == fixture_counts_dict[max_gameweek]
)

total_submitted = number_of_players - not_submitted
print(total_submitted)
