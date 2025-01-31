import sqlite3


def get_top_5_similar_players(db_path):
    query = """
    WITH CTE AS (
        SELECT
            p1.player_id as [player 1],
            p1.home_goals [home goals p1],
            p1.away_goals [away goals p1],
            p2.player_id as [player 2],
            p2.home_goals [home goals p2],
            p2.away_goals [away goals p2],
            CASE WHEN p1.home_goals = p2.home_goals and p1.away_goals = p2.away_goals THEN 1 ELSE 0 END AS [is same?]
        FROM 
            predictions as p1
            join predictions as p2 on p2.fixture_id = p1.fixture_id
        WHERE p1.player_id = ? and p2.player_id = ?
    )
    SELECT 
        SUM([is same?]) AS [Same],
        COUNT(*) AS [Total]
    FROM cte
    """

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT player_id FROM predictions")
    players = [row[0] for row in cursor.fetchall()]

    similarity_scores = []

    for i in range(len(players)):
        for j in range(i + 1, len(players)):
            cursor.execute(query, (players[i], players[j]))
            same, total = cursor.fetchone()
            similarity_percentage = (same / total) * 100 if total > 0 else 0
            similarity_scores.append(((players[i], players[j]), similarity_percentage))

    conn.close()

    # Sort by similarity percentage in descending order and get the top 5
    top_5_pairs = sorted(similarity_scores, key=lambda x: x[1], reverse=True)

    return top_5_pairs


def players_name(player_id):
    query = """
    SELECT player_name FROM players WHERE player_id = ?
    """
    conn = sqlite3.connect("data/database.db")
    cursor = conn.cursor()
    cursor.execute(query, (player_id,))
    name = cursor.fetchone()[0]
    conn.close()
    return name


if __name__ == "__main__":
    db_path = "data/database.db"
    top_5_pairs = get_top_5_similar_players(db_path)

    for pair, similarity in top_5_pairs:
        print(
            f"The players {players_name(pair[0]).title()} and {players_name(pair[1]).title()} have {similarity:.2f}% similar scores."
        )
