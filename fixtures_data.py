import sqlite3
import requests
import pytz
from datetime import datetime
import logging
import subprocess

logging.basicConfig(
    filename="/home/levo/Documents/projects/prediction_league/logs/fixtures_data.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

odds_api_map = team_mapping = {
    "arsenal": "arsenal",
    "aston villa": "aston villa",
    "bournemouth": "bournemouth",
    "brentford": "brentford",
    "brighton and hove albion": "brighton",
    "chelsea": "chelsea",
    "crystal palace": "crystal palace",
    "everton": "everton",
    "fulham": "fulham",
    "ipswich town": "ipswich",
    "leicester city": "leicester",
    "liverpool": "liverpool",
    "manchester city": "man city",
    "manchester united": "man utd",
    "newcastle united": "newcastle",
    "nottingham forest": "nott'm forest",
    "southampton": "southampton",
    "tottenham hotspur": "spurs",
    "west ham united": "west ham",
    "wolverhampton wanderers": "wolves",
}


season = "2024/25"
uk_tz = pytz.timezone("Europe/London")

fixtures_json = "https://fantasy.premierleague.com/api/fixtures/"
bootstrap = "https://fantasy.premierleague.com/api/bootstrap-static/"
con = sqlite3.connect(
    "/home/levo/Documents/projects/prediction_league/data/database.db"
)
headers = {
    "authority": "users.premierleague.com",
    "cache-control": "max-age=0",
    "upgrade-insecure-requests": "1",
    "origin": "https://fantasy.premierleague.com",
    "content-type": "application/x-www-form-urlencoded",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    "sec-fetch-site": "same-site",
    "sec-fetch-mode": "navigate",
    "sec-fetch-user": "?1",
    "sec-fetch-dest": "document",
    "referer": "https://fantasy.premierleague.com/my-team",
    "accept-language": "en-US,en;q=0.9,he;q=0.8",
}
cur = con.cursor()


def create_tables():
    url = bootstrap
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS teams (
            team_id INTEGER NOT NULL, 
            team_name TEXT, 
            unavailable BOOLEAN,
            strength INTEGER,
            strength_overall_home,
            strength_overall_away,
            strength_attack_home,
            strength_attack_away,
            strength_defence_home,
            strength_defence_away,
            pulse_id INTEGER,
            PRIMARY KEY (team_id)
        )
        """
    )
    cur.execute("SELECT * FROM teams")
    teams = cur.fetchall()
    if len(teams) == 0:
        r = requests.get(url)
        teams = r.json()["teams"]
        team_list = []
        for team in teams:
            team_list.append(
                (
                    team["id"],
                    team["name"].lower(),
                    team["unavailable"],
                    team["strength"],
                    team["strength_overall_home"],
                    team["strength_overall_away"],
                    team["strength_attack_home"],
                    team["strength_attack_away"],
                    team["strength_defence_home"],
                    team["strength_defence_away"],
                    team["pulse_id"],
                )
            )
        con.executemany(
            "INSERT INTO teams VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", team_list
        )
    con.commit()

    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS fixtures (
            fixture_id INTEGER NOT NULL, 
            kickoff_dttm DATETIME, 
            gameweek INTEGER, 
            home_teamid INTEGER NOT NULL, 
            away_teamid INTEGER NOT NULL, 
            finished BOOLEAN, 
            season TEXT,
            PRIMARY KEY (fixture_id, season), 
            UNIQUE (fixture_id, season)
        );
        """
    )

    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS gameweeks (
            gameweek INTEGER NOT NULL,
            deadline_dttm DATETIME,
            deadline_date DATE,
            deadline_time TIME,
            current_gameweek BOOLEAN,
            next_gameweek BOOLEAN,
            finished BOOLEAN,
            PRIMARY KEY (gameweek)
        );
        """
    )
    con.commit()


def add_fixtures():
    with requests.Session() as s:
        try:
            r = s.get(fixtures_json, headers=headers)
            r.raise_for_status()
            json_data = r.json()
            fixtures = []
            for fixture in json_data:
                fixtures.append(
                    (
                        fixture["id"],
                        fixture["kickoff_time"],
                        fixture["event"],
                        fixture["team_h"],
                        fixture["team_a"],
                        fixture["finished"],
                        fixture["pulse_id"],
                        season,
                    )
                )
            cur.executemany(
                "INSERT OR REPLACE INTO fixtures (fixture_id, kickoff_dttm, gameweek, home_teamid, away_teamid, finished,pulse_id, season) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                fixtures,
            )
            con.commit()
            logging.info("Fixtures added successfully.")
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching fixtures: {e}")
        except sqlite3.Error as e:
            logging.error(f"Database error: {e}")


def add_gameweeks():
    url = bootstrap
    try:
        r = requests.get(url)
        r.raise_for_status()
        events = r.json()["events"]
        gameweeks = []

        for event in events:
            start_dttm = event["deadline_time"].replace("Z", "")
            utc_dttm = datetime.strptime(start_dttm, "%Y-%m-%dT%H:%M:%S")
            uk_dttm = utc_dttm.replace(tzinfo=pytz.utc).astimezone(uk_tz)
            deadline_date = uk_dttm.strftime("%Y-%m-%d")
            deadline_time = uk_dttm.strftime("%H:%M")
            current_gameweek = event["is_current"]
            next_gameweek = event["is_next"]
            gameweeks.append(
                (
                    event["id"],
                    event["deadline_time"],
                    deadline_date,
                    deadline_time,
                    current_gameweek,
                    next_gameweek,
                    event["finished"],
                )
            )
        cur.executemany(
            "INSERT OR REPLACE INTO gameweeks VALUES (?, ?, ?, ?, ?, ?, ?)", gameweeks
        )
        con.commit()
        logging.info("Gameweeks added successfully.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching gameweeks: {e}")
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")


def updated():
    dt = datetime.now()
    now = dt.strftime("%d-%m-%Y. %H:%M:%S")
    timestamp = dt.timestamp()
    try:
        cur.execute(
            """INSERT OR REPLACE INTO last_update (table_name, updated, timestamp) 
               VALUES ('fixtures', ?, ?)""",
            (
                now,
                timestamp,
            ),
        )
        con.commit()
        logging.info("Last update timestamp added successfully.")
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")


def add_odds_data():
    odds_db = sqlite3.connect("/home/levo/Documents/projects/odds-api/uefa_odds.db")
    odds_cur = odds_db.cursor()
    try:
        odds_cur.execute(
            """ 
        SELECT 
            home_team_name
            ,away_team_name
            ,average_home_win_odds
            ,average_draw_odds
            ,average_away_win_odds
        FROM 
            pivoted_odds
        WHERE home_team_name IN (
            'arsenal',
            'aston villa',
            'bournemouth',
            'brentford',
            'brighton and hove albion',
            'chelsea',
            'crystal palace',
            'everton',
            'fulham',
            'ipswich town',
            'leicester city',
            'liverpool',
            'manchester city',
            'manchester united',
            'newcastle united',
            'nottingham forest',
            'southampton',
            'tottenham hotspur',
            'west ham united',
            'wolverhampton wanderers'
            )
        AND 
        away_team_name IN (
            'arsenal',
            'aston villa',
            'bournemouth',
            'brentford',
            'brighton and hove albion',
            'chelsea',
            'crystal palace',
            'everton',
            'fulham',
            'ipswich town',
            'leicester city',
            'liverpool',
            'manchester city',
            'manchester united',
            'newcastle united',
            'nottingham forest',
            'southampton',
            'tottenham hotspur',
            'west ham united',
            'wolverhampton wanderers')
        AND (competition = 'soccer_epl' OR competition IS NULL)
        """
        )
        odds_data = odds_cur.fetchall()
        odds_db.close()
        for odds in odds_data:
            home_team = odds_api_map[odds[0]]
            away_team = odds_api_map[odds[1]]

            cur.execute("SELECT team_id FROM teams WHERE team_name = ?", (home_team,))
            home_team_id = cur.fetchone()[0]

            cur.execute("SELECT team_id FROM teams WHERE team_name = ?", (away_team,))
            away_team_id = cur.fetchone()[0]

            cur.execute(
                """
                UPDATE fixtures
                SET home_win_odds = ?, draw_odds = ?, away_win_odds = ?
                WHERE home_teamid = ? AND away_teamid = ? AND season = ?
                """,
                (
                    round(odds[2], 2),
                    round(odds[3], 2),
                    round(odds[4], 2),
                    home_team_id,
                    away_team_id,
                    season,
                ),
            )
        con.commit()
        logging.info("Odds data added successfully.")
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
    finally:
        odds_db.close()


def main():
    create_tables()
    add_fixtures()
    add_gameweeks()
    add_odds_data()
    updated()
    con.close()
    second_script = "/home/levo/Documents/projects/prediction_league/matchdata.py"
    subprocess.run(["python3", second_script], check=True)
    third_script = "/home/levo/Documents/projects/pick_player/playerscores.py"
    try:
        subprocess.run(["python3", third_script], check=True)
        logging.info(f"{third_script} executed successfully.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error executing {third_script}: {e}")


if __name__ == "__main__":
    main()
