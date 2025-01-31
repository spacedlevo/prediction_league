import sqlite3
import numpy as np

import matplotlib.pyplot as plt


def fetch_data(gameweek):
    query = """
    SELECT 
        pl.player_name,
        p.fixture_id,
        p.home_goals || '-' || p.away_goals AS Score,
        f.gameweek,
        CASE 
            WHEN home_goals > away_goals THEN 'HW'
            WHEN home_goals < away_goals THEN 'AW'
            ELSE 'D' 
        END AS Result
    FROM 
        predictions AS p
        JOIN fixtures AS f ON f.fixture_id = p.fixture_id
        JOIN players AS pl ON p.player_id = pl.player_id
    WHERE 
        gameweek = ?
    """
    conn = sqlite3.connect("data/database.db")
    cursor = conn.cursor()
    cursor.execute(query, (gameweek,))
    data = cursor.fetchall()
    conn.close()
    return data


def compare_players(data):
    players = list(set([row[0] for row in data]))
    player_scores = {player: {} for player in players}
    player_results = {player: {} for player in players}

    for row in data:
        player_name, fixture_id, score, gameweek, result = row
        player_scores[player_name][fixture_id] = score
        player_results[player_name][fixture_id] = result

    score_matrix = np.zeros((len(players), len(players)))
    result_matrix = np.zeros((len(players), len(players)))

    for i, player1 in enumerate(players):
        for j, player2 in enumerate(players):
            if i != j:
                common_fixtures = set(player_scores[player1].keys()).intersection(
                    set(player_scores[player2].keys())
                )
                if common_fixtures:
                    same_scores = sum(
                        1
                        for fixture in common_fixtures
                        if player_scores[player1][fixture]
                        == player_scores[player2][fixture]
                    )
                    same_results = sum(
                        1
                        for fixture in common_fixtures
                        if player_results[player1][fixture]
                        == player_results[player2][fixture]
                    )
                    score_matrix[i, j] = same_scores
                    result_matrix[i, j] = same_results

    return players, score_matrix, result_matrix


def plot_matrices(players, score_matrix, result_matrix, gameweek):
    fig, axes = plt.subplots(1, 2, figsize=(15, 7))
    manager = plt.get_current_fig_manager()
    manager.window.showMaximized()
    fig.suptitle(f"Comparisons for gameweek {gameweek}", fontsize=16)
    cax1 = axes[0].matshow(score_matrix, cmap="coolwarm")
    fig.colorbar(cax1, ax=axes[0])
    axes[0].set_xticks(np.arange(len(players)))
    axes[0].set_yticks(np.arange(len(players)))
    axes[0].set_xticklabels(players)
    axes[0].set_yticklabels(players)
    axes[0].set_title("Number of Same Scores")
    plt.setp(axes[0].get_xticklabels(), rotation=90, ha="left")

    axes[0].grid(True, which="both", color="gray", linestyle="--", linewidth=0.5)
    axes[1].grid(True, which="both", color="gray", linestyle="--", linewidth=0.5)
    cax2 = axes[1].matshow(result_matrix, cmap="coolwarm")
    fig.colorbar(cax2, ax=axes[1])
    axes[1].set_xticks(np.arange(len(players)))
    axes[1].set_yticks(np.arange(len(players)))
    axes[1].set_xticklabels(players)
    axes[1].set_yticklabels(players)
    axes[1].set_title("Number of Same Results")
    plt.setp(axes[1].get_xticklabels(), rotation=90, ha="left")
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    fig.savefig(f"data/comparison{gameweek}.png", bbox_inches="tight")
    plt.show()


def main():
    gameweek = int(input("Enter the gameweek to compare: "))
    data = fetch_data(gameweek)
    players, score_matrix, result_matrix = compare_players(data)
    players = [player.title() for player in players]
    sorted_indices = np.argsort(players)
    players = np.array(players)[sorted_indices]
    score_matrix = score_matrix[sorted_indices, :][:, sorted_indices]
    result_matrix = result_matrix[sorted_indices, :][:, sorted_indices]
    plot_matrices(players, score_matrix, result_matrix, gameweek)


if __name__ == "__main__":
    main()
