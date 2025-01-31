import sqlite3


def get_predictions_for_gameweek(player_id, gameweek):
    # This function should return a list of predictions for a given player and gameweek
    # Replace with actual database query or data retrieval logic
    query = """
    SELECT
        p.fixture_id,
        p.home_goals ||'-'|| p.away_goals [score]
    FROM predictions p
        JOIN fixtures f ON p.fixture_id = f.fixture_id
    WHERE p.player_id = ? AND f.gameweek = ?
        and f.gameweek IS NOT NULL
    ORDER BY f.fixture_id
    """
    cursor.execute(query, (player_id, gameweek))
    predictions = cursor.fetchall()
    return predictions


def compare_predictions(player1_id, player2_id, gameweek):
    predictions1 = get_predictions_for_gameweek(player1_id, gameweek)
    predictions2 = get_predictions_for_gameweek(player2_id, gameweek)

    for pred1, pred2 in zip(predictions1, predictions2):
        if pred1 != pred2 or pred1[1] == "9-9" or pred2[1] == "9-9":
            return False
    return True


def flag_identical_predictions(players, gameweek):
    flagged_pairs = []
    for i in range(len(players)):
        for j in range(i + 1, len(players)):
            if compare_predictions(players[i], players[j], gameweek):
                flagged_pairs.append((players[i], players[j]))
    return flagged_pairs


def get_all_players():
    query = """
    SELECT 
        player_id
    FROM players
    WHERE active = 1
    """
    cursor.execute(query)
    players = cursor.fetchall()
    return [player[0] for player in players]


def get_gameweeks():
    query = """
    SELECT DISTINCT
        gameweek
    FROM predictions
        JOIN fixtures ON predictions.fixture_id = fixtures.fixture_id
    WHERE fixtures.gameweek IS NOT NULL
    """
    cursor.execute(query)
    gameweek = cursor.fetchall()
    return [gameweek[0] for gameweek in gameweek]


# Example usage
if __name__ == "__main__":
    # Connect to your database
    conn = sqlite3.connect("data/database.db")
    cursor = conn.cursor()

    players = get_all_players()
    gameweeks = get_gameweeks()

    for gameweek in gameweeks:
        flagged_pairs = flag_identical_predictions(players, gameweek)
        if flagged_pairs:
            print("Identical predictions found for the following player pairs:")
            for pair in flagged_pairs:
                print(f"Player {pair[0]} and Player {pair[1]} in gameweek {gameweek}")
        else:
            print("No identical predictions found in gameweek", gameweek)

    # Close the database connection
    conn.close()
