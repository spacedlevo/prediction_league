import sqlite3
import sys
import matplotlib.pyplot as plt

import numpy as np


def get_top_5_similar_players(db_path, gw):
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
            JOIN fixtures as f ON f.fixture_id = p1.fixture_id
        WHERE p1.player_id = ? and p2.player_id = ?
            AND f.gameweek = ?
    )
    SELECT 
        SUM([is same?]) AS [Same],
        COUNT(*) AS [Total]
    FROM cte
    """

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT 
            DISTINCT predictions.player_id 
        FROM predictions 
            JOIN fixtures ON fixtures.fixture_id = predictions.fixture_id 
            JOIN players ON players.player_id = predictions.player_id
        WHERE gameweek = ? AND home_goals <> 9 AND away_goals <> 9 AND active = 1
            """,
        (gw,),
    )
    players = [row[0] for row in cursor.fetchall()]

    similarity_scores = []

    for i in range(len(players)):
        for j in range(i + 1, len(players)):
            cursor.execute(query, (players[i], players[j], gw))
            same, total = cursor.fetchone()
            similarity_percentage = (same / total) * 100 if total > 0 else 0
            similarity_scores.append(((players[i], players[j]), similarity_percentage))

    conn.close()

    # Sort by similarity percentage in descending order and get the top 5
    sorted_comparisons = sorted(similarity_scores, key=lambda x: x[1], reverse=True)
    top_5_pairs = [pair for pair in sorted_comparisons]

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


def plot_similarity_heatmap(similarity_scores, players):
    player_ids = list(set([player for pair, _ in similarity_scores for player in pair]))
    player_ids.sort()
    player_index = {player_id: idx for idx, player_id in enumerate(player_ids)}

    matrix = np.zeros((len(player_ids), len(player_ids)))
    player_ids.sort(key=lambda player_id: players_name(player_id))
    fig, ax = plt.subplots()
    fig.set_size_inches(20, 20)
    ax.set_xticks(np.arange(len(player_ids)) + 0.5, minor=False)
    ax.set_yticks(np.arange(len(player_ids)) + 0.5, minor=False)
    ax.tick_params(axis="both", which="both", length=0)
    for (player1, player2), similarity in similarity_scores:
        idx1 = player_index[player1]
        idx2 = player_index[player2]
        matrix[idx1, idx2] = similarity
        matrix[idx2, idx1] = similarity
    cax = ax.matshow(matrix, cmap="coolwarm")
    fig.colorbar(cax)

    ax.set_xticks(np.arange(len(player_ids)))
    ax.set_yticks(np.arange(len(player_ids)))

    ax.set_xticklabels(
        [players_name(player_id) for player_id in player_ids], rotation=90
    )
    ax.set_yticklabels([players_name(player_id) for player_id in player_ids])

    plt.xlabel("Players")
    plt.ylabel("Players")
    plt.title("Similarity Heatmap of Players Predictions")
    plt.show()
    print("Similarity Matrix:")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python comparegameweek.py <gameweek>")
        sys.exit(1)

    gw = int(sys.argv[1])
    db_path = "data/database.db"
    top_5_pairs = get_top_5_similar_players(db_path, gw)

    for pair, similarity in top_5_pairs:
        if similarity >= 60:
            print(
                f"The players {players_name(pair[0]).title()} and {players_name(pair[1]).title()} have {similarity:.2f}% similar scores."
            )
    players = list(set([player for pair, _ in top_5_pairs for player in pair]))
    plot_similarity_heatmap(top_5_pairs, players)
