import sqlite3 as sql
from datetime import datetime, timedelta
import subprocess
import requests

predictions_db_location = (
    "/home/levo/Documents/projects/prediction_league/data/database.db"
)
gameweek_file = "/home/levo/Dropbox/Apps/predictions_league/gameweek.txt"
PUSHOVER_API = {
    "PUSHOVER_USER": "h1bpxMpSULKQIZHXT57tOztVxXcx8G",
    "PUSHOVER_TOKEN": "",
}


def fetch_next_deadline():
    conn = sql.connect(predictions_db_location)
    c = conn.cursor()
    c.execute(
        """
        SELECT 
	        gameweek
	        ,CAST(strftime('%s', deadline_dttm) AS INT) [deadline_dttm]
        FROM gameweeks WHERE deadline_dttm > datetime("now") ORDER BY deadline_dttm ASC LIMIT 1
    """
    )
    deadline = c.fetchone()
    conn.close()
    return deadline


def is_within_12_hours(timestamp):
    now = datetime.now()
    print(f"Deadline: {datetime.fromtimestamp(timestamp)}")
    print(f"Now: {now}")
    hours_until_deadline = (timestamp - now.timestamp()) / 3600
    print(f"Hours until deadline: {hours_until_deadline:.2f}")
    target_time = datetime.fromtimestamp(timestamp)
    return now <= target_time <= now + timedelta(hours=24)


def run_createdata_script(gw):
    script_path = "/home/levo/Documents/projects/odds-api/createdata.py"
    script_path2 = "/home/levo/Documents/projects/odds-api/predictions.py"
    subprocess.run(["python3", script_path, "--market", "soccer_epl"])
    subprocess.run(["python3", script_path2, str(gw)])


def read_predictions_file(gw):
    file_path = (
        f"/home/levo/Dropbox/Apps/predictions_league/predictions/predictions{gw}.txt"
    )
    with open(file_path, "r") as file:
        predictions = file.read()
    predictions = "\nTom Levin\n\n" + predictions
    return predictions


def save_predictions(gw, predictions):
    file_path = f"/home/levo/Dropbox/Predictions/2024_25/gameweek{gw}.txt"
    with open(file_path, "a") as file:
        file.write(predictions)


def check_if_predictions_exist(gw):
    conn = sql.connect(predictions_db_location)
    c = conn.cursor()
    c.execute(
        """
        SELECT 
            COUNT(*)
        FROM fixtures
        WHERE 
            gameweek = ?
              """,
        (gw,),
    )

    count = c.fetchone()[0]

    c.execute(
        """
            SELECT 
                home_goals
                ,away_goals
            FROM 
                predictions
                JOIN fixtures ON predictions.fixture_id = fixtures.fixture_id
            WHERE 
                player_id = 10
                AND gameweek = ?
            ORDER BY home_goals DESC
              """,
        (gw,),
    )
    predictions = c.fetchall()
    conn.close()
    if count != len(predictions):
        return False
    if not predictions or (predictions[0] == 9):
        return False
    else:
        return True


def fetch_fixtures(gw):
    conn = sql.connect(predictions_db_location)
    c = conn.cursor()
    c.execute(
        """
        SELECT 
            ht.team_name
            ,at.team_name
            ,deadline_time
        FROM 
            fixtures AS F
            JOIN teams AS ht ON ht.team_id = home_teamid
            JOIN teams AS at ON at.team_id = away_teamid 
            JOIN gameweeks AS gw on gw.gameweek = F.gameweek
        WHERE 
            f.gameweek = ?
        ORDER BY f.kickoff_dttm
              """,
        (gw,),
    )
    fixtures = c.fetchall()
    conn.close()
    return fixtures


def create_string():
    gw, deadline = fetch_next_deadline()
    fixtures = fetch_fixtures(gw)
    fixtures_str = "\n".join(
        [f"{home.title()} v {away.title()}" for home, away, _ in fixtures]
    )
    deadline_time = datetime.fromtimestamp(deadline).strftime("%H:%M")
    result = f"{fixtures_str}\n\nDeadline tomorrow at {deadline_time}"
    return result


def send_pushover_message(message):

    url = "https://api.pushover.net/1/messages.json"
    data = {
        "token": PUSHOVER_API["PUSHOVER_TOKEN"],
        "user": PUSHOVER_API["PUSHOVER_USER"],
        "message": message,
    }

    response = requests.post(url, data=data)
    if response.status_code != 200:
        raise Exception(f"Error sending message: {response.text}")


def main():
    gw, deadline = fetch_next_deadline()
    if is_within_12_hours(deadline) and not check_if_predictions_exist(gw):
        run_createdata_script(gw)
        with open(gameweek_file, "w") as file:
            file.write(str(gw))
        predictions = read_predictions_file(gw)
        save_predictions(gw, predictions)
        message = create_string()
        send_pushover_message(message)
        predictions = predictions.replace("\nTom Levin\n\n", "").strip()
        print(predictions)
        send_pushover_message(predictions)
        print("Data Saved")
    else:
        print("No deadline within 24 hours")


main()
