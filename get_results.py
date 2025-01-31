import requests
import json
import sqlite3
import pysftp as sftp
import json
from datetime import datetime, timezone, timedelta
import sys
import logging


EVENT_URL = "https://fantasy.premierleague.com/api/fixtures/?event="
DATABASE_FILE = "/home/levo/Documents/projects/prediction_league/data/database.db"
con = sqlite3.connect(DATABASE_FILE)
cur = con.cursor()
season = "2024/25"

# Setup logging
logging.basicConfig(
    filename="/home/levo/Documents/projects/prediction_league/logs/results.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def log_results_change(fixture_id, old_result, new_result):
    logging.info(
        f"Result changed for fixture_id {fixture_id}: {old_result} -> {new_result}"
    )


def log_new_result(fixture_id, result):
    logging.info(f"New result added for fixture_id {fixture_id}: {result}")


def add_to_database(results):
    results_data = []
    for row in results:
        # Get the result from database
        cur.execute(
            """ SELECT home_goals, away_goals FROM results WHERE fixture_id = (
                SELECT fixture_id FROM fixtures WHERE home_teamid = ? AND away_teamid = ? AND season = ?
            ) """,
            (row[0], row[1], season),
        )
        db_result = cur.fetchone()
        # Does the result exist?
        if db_result:
            # Check whether the result is the same as the one we have
            if db_result[0] == row[2] and db_result[1] == row[3]:
                continue
            else:
                fixture_id = cur.execute(
                    """ SELECT fixture_id FROM fixtures WHERE home_teamid = ? AND away_teamid = ? AND season = ? """,
                    (row[0], row[1], season),
                ).fetchone()[0]
                log_results_change(fixture_id, db_result, (row[2], row[3]))
        results_data.append(row)
    for result in results_data:
        cur.execute(
            """ SELECT fixture_id FROM fixtures WHERE home_teamid = ? AND away_teamid = ? AND season = ? """,
            (result[0], result[1], season),
        )
        fixture_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT OR REPLACE INTO results (fixture_id, home_goals, away_goals, season)
            VALUES (?, ?, ?, ?) """,
            (fixture_id, result[2], result[3], season),
        )
        log_new_result(fixture_id, (result[2], result[3]))
    if len(results_data) == 0:
        return False
    else:
        return True


def print_results():
    cur.execute(
        """
    SELECT
        home_team.team_name as home_team,
        results.home_goals as results_home_goals,
        results.away_goals as results_away_goals,
        away_team.team_name as away_team
    from fixtures
    inner join teams as away_team on away_team.team_id = fixtures.away_teamid
    inner join teams as home_team on home_team.team_id = fixtures.home_teamid
    left join results on results.fixture_id = fixtures.fixture_id
    where 
        gameweek = ? 
        AND results_home_goals NOT NULL 
        AND fixtures.season = ?
        """,
        (gw, season),
    )
    results_db = cur.fetchall()
    for i in results_db:
        print(f"{i[0].title()} {i[1]}-{i[2]} {i[3].title()}")


def upload_db():
    # SSH the new database to the website
    last_update = cur.execute(
        """SELECT updated, timestamp FROM last_update WHERE table_name = 'uploaded'"""
    ).fetchone()
    try:
        updated("uploaded")
        with open("/home/levo/Documents/projects/prediction_league/keys.json") as f:
            users_deets = json.load(f)

        with sftp.Connection(
            host="ssh.pythonanywhere.com",
            username=users_deets["user"],
            password=users_deets["psw"],
        ) as ftp:
            ftp.put(DATABASE_FILE, "/home/spacedlevo/database.db")
        logging.info("Database upload successful.")

        return True
    except Exception as e:
        logging.error(f"Failed to upload database: {e}")
        cur.execute(
            """INSERT OR REPLACE INTO last_update (table_name, updated, timestamp) 
        VALUES (?, ?, ?)""",
            ("uploaded", last_update[0], last_update[1]),
        )
        con.commit()
        check_db = cur.execute(
            "SELECT updated FROM last_update WHERE table_name = 'uploaded'"
        ).fetchone()
        logging.info(f"upload time reset to: {check_db[0]}")
        return False


def updated(val):
    try:
        dt = datetime.now()
        now = dt.strftime("%d-%m-%Y. %H:%M:%S")
        timestamp = dt.timestamp()
        cur.execute(
            """INSERT OR REPLACE INTO last_update (table_name, updated, timestamp) 
               VALUES (?, ?, ?)""",
            (val, now, timestamp),
        )
        con.commit()
    except Exception as e:
        logging.error(f"Failed to update {val}: {e}")


def cache_gameweek(current_gw, next_gw_deadline_time):
    cur.execute("""DROP TABLE IF EXISTS gameweek_cache""")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS gameweek_cache (
            current_gw INTEGER PRIMARY KEY,
            next_gw_deadline_time TEXT
        )
        """
    )
    cur.execute(
        """
        INSERT OR REPLACE INTO gameweek_cache (current_gw, next_gw_deadline_time)
        VALUES (?, ?)
        """,
        (current_gw, next_gw_deadline_time),
    )
    updated("gameweek_cache")
    con.commit()


def current_gameweek():
    cur.execute("SELECT current_gw, next_gw_deadline_time FROM gameweek_cache")
    row = cur.fetchone()
    if row:
        current_gw, next_gw_deadline_time = row
        next_gw_deadline_time = datetime.strptime(
            next_gw_deadline_time, "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
        if next_gw_deadline_time > datetime.now(timezone.utc):
            print("Using Cache")
            return current_gw
    response = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/")
    data = response.json()
    gw = next(event["id"] for event in data["events"] if event["is_current"])
    next_gameweek = next(
        event["deadline_time"] for event in data["events"] if event["is_next"]
    )
    next_gameweek = (
        datetime.strptime(next_gameweek, "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=1)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    cache_gameweek(gw, next_gameweek)
    return gw


def get_results(gw):
    results = []
    r = requests.get(f"{EVENT_URL}{gw}")
    print(f"Getting {EVENT_URL}{gw}")
    result_json = r.json()
    for result in result_json:
        if result["started"]:
            results.append(
                [
                    result["team_h"],
                    result["team_a"],
                    result["team_h_score"],
                    result["team_a_score"],
                ]
            )
    return results


def get_gameweek_deadlines():
    cur.execute(
        """
        SELECT gameweek, deadline_dttm FROM gameweeks
        """
    )
    return cur.fetchall()


def runtimes(gw):
    cur.execute(
        """
        SELECT MIN(kickoff_dttm), MAX(kickoff_dttm)
        FROM fixtures 
        WHERE 
			gameweek = ? AND season = ?
			AND DATE(kickoff_dttm) = DATE('now')
        """,
        (gw, season),
    )

    min_kickoff, max_kickoff = cur.fetchone()
    current_time = datetime.now(timezone.utc)

    if min_kickoff is None or max_kickoff is None:
        print("No fixtures found for the current gameweek.")
        return False

    # Remove the 'Z' and replace 'T' with a space
    min_kickoff = min_kickoff.replace("Z", "").replace("T", " ")
    max_kickoff = max_kickoff.replace("Z", "").replace("T", " ")

    min_kickoff_dt = datetime.strptime(min_kickoff, "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=timezone.utc
    )
    max_kickoff_dt = datetime.strptime(max_kickoff, "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=timezone.utc
    )

    if (
        min_kickoff_dt
        <= current_time
        <= max_kickoff_dt + timedelta(hours=2, minutes=30)
    ):
        print("Current time is within the range.")
        return True
    else:
        print("Current time is outside the range.")
        return False


def predictions_updated_after_results():
    cur.execute(
        """
        SELECT updated FROM last_update WHERE table_name = 'predictions'
        """
    )
    predictions_updated = cur.fetchone()

    cur.execute(
        """
        SELECT updated FROM last_update WHERE table_name = 'uploaded'
        """
    )
    results_updated = cur.fetchone()

    if predictions_updated and results_updated:
        predictions_time = datetime.strptime(
            predictions_updated[0], "%d-%m-%Y. %H:%M:%S"
        )
        results_time = datetime.strptime(results_updated[0], "%d-%m-%Y. %H:%M:%S")
        return predictions_time > results_time
    return False


def predictions_updated_before_uploaded():
    cur.execute(
        """
        SELECT MAX(timestamp), updated FROM last_update WHERE updated <> 'uploaded'
        """
    )
    predictions_updated = cur.fetchone()

    cur.execute(
        """
        SELECT updated FROM last_update WHERE table_name = 'uploaded'
        """
    )
    uploaded_updated = cur.fetchone()

    if predictions_updated[1] and uploaded_updated and uploaded_updated[0]:
        predictions_time = datetime.strptime(
            predictions_updated[1], "%d-%m-%Y. %H:%M:%S"
        )
        uploaded_time = datetime.strptime(uploaded_updated[0], "%d-%m-%Y. %H:%M:%S")
        return uploaded_time < predictions_time
    return False


def uploaded_within_last_30_minutes():
    cur.execute(
        """
        SELECT timestamp FROM last_update WHERE table_name = 'uploaded'
        """
    )
    uploaded_updated = cur.fetchone()

    if uploaded_updated and uploaded_updated[0] is not None:
        uploaded_time = uploaded_updated[0]
        current_time = datetime.now().timestamp()
        time_difference = current_time - uploaded_time
        if time_difference < 1740:
            return True
    return False


def main():
    gw = current_gameweek()
    run_schedule = runtimes(gw)
    if run_schedule:
        results = get_results(gw)
        need_to_update = add_to_database(results)
        if need_to_update:
            updated("results")
            upload_db()
            print("Database uploaded")
        elif predictions_updated_after_results():
            logging.info("New predictions found, database uploaded.")
            upload_db()

        else:
            logging.info("Check ran, but no new results were added.")
            print("No new results to upload")
    elif predictions_updated_before_uploaded():
        logging.info("New predictions found, database uploaded.")
        upload_db()

    if len(sys.argv) > 1 and sys.argv[1] == "o":
        results = get_results(gw)
        need_to_update = add_to_database(results)
        updated("results")
        upload_db()
        print("Database uploaded")
        logging.info("Override used, database uploaded")
    if uploaded_within_last_30_minutes() is False:
        print("Database not uploaded within the last 30 minutes")
        if upload_db():
            logging.info("Laptop health check completed, database uploaded")
    con.close()


if __name__ == "__main__":
    main()
