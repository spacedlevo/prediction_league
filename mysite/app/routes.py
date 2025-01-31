from app import app

from flask import render_template, jsonify, Response
import sqlite3
from datetime import datetime, timedelta
import requests


db_dir = "/home/spacedlevo/database.db"
season = "2024/25"


@app.context_processor
def inject_current_gw():
    db = sqlite3.connect(db_dir)
    c = db.cursor()
    response = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/")
    data = response.json()
    current_gw = next(event["id"] for event in data["events"] if event["is_current"])

    c.execute("SELECT timestamp FROM last_update WHERE table_name = 'uploaded'")
    last_updated = c.fetchone()[0]

    now = datetime.now()  # Current time in UTC

    print(last_updated)
    print(now.timestamp())

    time_difference = now.timestamp() - last_updated
    print(time_difference)
    is_stale = time_difference > 1800  # True if the difference exceeds 1800 seconds

    db.close()
    return dict(current_gw=current_gw, is_stale=is_stale)


@app.route("/")
@app.route("/index")
def index():
    db = sqlite3.connect(db_dir)
    c = db.cursor()
    c.execute(
        "SELECT max(fixtures.gameweek) FROM results JOIN fixtures on fixtures.fixture_id = results.fixture_id WHERE results.season = ? ",
        (season,),
    )

    response = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/")
    data = response.json()
    gw = next(event["id"] for event in data["events"] if event["is_current"])

    sql_statement = """
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
            WHERE 
                predictions.season = ?
                AND players.active = 1
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
        ),
        previous_position AS (
            SELECT
                ROW_NUMBER() OVER (ORDER BY SUM([correct result point] + [correct score point]) DESC, SUM([correct result point]) DESC, SUM([correct score point]) DESC, web_name) AS [previous_position],
                web_name,
                player_id
            FROM (
                SELECT
                    players.web_name,
                    players.player_id,
                    players.paid,
                    fixtures.gameweek,
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
                WHERE 
                    fixtures.gameweek <= (
                        SELECT 
                            MAX(gameweek) - 1
                        FROM 
                            gameweeks
                        WHERE
                            datetime(deadline_dttm) < datetime('now', 'utc')
                    )
                    AND predictions.season = ?
                    AND players.active = 1
                GROUP BY players.web_name, players.player_id, players.paid, fixtures.gameweek, predictions.fixture_id, predictions.home_goals, predictions.away_goals, results.home_goals, results.away_goals
            ) AS previous_results
            GROUP BY web_name, player_id
        )

        SELECT
            cp.current_position,
            IFNULL(pp.previous_position, cp.current_position) [pp.previous_position],
            cp.web_name,
            cp.player_id,
            cp.paid,
            cp.[Correct Result],
            cp.[Correct Score],
            cp.[Total Points]
        FROM current_position cp
        LEFT JOIN previous_position pp ON cp.player_id = pp.player_id
        ORDER BY cp.current_position, cp.web_name;

        """

    gameweek_table_sql = """
        WITH cte AS (
            SELECT
                players.web_name,
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
            WHERE 
                fixtures.gameweek = ?
                AND fixtures.season = ?
                AND players.active = 1
            GROUP BY players.web_name, predictions.fixture_id, predictions.home_goals, predictions.away_goals, results.home_goals, results.away_goals
        )

        SELECT
            web_name,
            SUM([correct result point]) AS [Correct Result],
            SUM([correct score point]) AS [Correct Score],
            SUM([correct result point] + [correct score point]) AS [Total Points]
        FROM cte
        GROUP BY web_name
        ORDER BY 4 DESC, 2 DESC;
    """

    gw_results_sql = """
        SELECT
            home_team.team_name
            ,results.home_goals
            ,results.away_goals
            ,away_team.team_name
        FROM results
            JOIN fixtures ON results.fixture_id = fixtures.fixture_id
            inner join teams as away_team on away_team.team_id = fixtures.away_teamid
            inner join teams as home_team on home_team.team_id = fixtures.home_teamid
        where gameweek = ? AND results.season = ?
    """

    next_deadline_sql = """

    SELECT 
	    gameweek
        ,deadline_dttm
        ,deadline_date
        ,deadline_time  
    FROM gameweeks 
    WHERE datetime(deadline_dttm) > datetime('now', 'utc')
    LIMIT 1
    """

    league_table = c.execute(sql_statement, (season, season)).fetchall()

    gameweek_table = c.execute(gameweek_table_sql, (gw, season)).fetchall()
    next_deadline = c.execute(next_deadline_sql).fetchone()

    next_deadline_dict = {
        "gameweek": next_deadline[0],
        "deadline_dttm": next_deadline[1],
        "deadline_date": datetime.strptime(next_deadline[2], "%Y-%m-%d").strftime(
            "%a %d %b"
        ),
        "deadline_time": next_deadline[3],
    }

    try:
        week_average = sum([int(i[3]) for i in gameweek_table]) / len(gameweek_table)
    except ZeroDivisionError:
        week_average = 0

    gw_results = c.execute(gw_results_sql, (gw, season)).fetchall()
    league_table_dict = [
        {
            "current_position": row[0],
            "previous_position": row[1],
            "player_name": row[2],
            "player_id": row[3],
            "paid": row[4],
            "correct_result": row[5],
            "correct_score": row[6],
            "total_points": row[7],
        }
        for row in league_table
    ]
    return render_template(
        "index.html",
        league_table=league_table_dict,
        results=gw_results,
        gw=gw,
        week_average=int(round(week_average)),
        gameweek_table=gameweek_table,
        next_deadline=next_deadline_dict,
    )


@app.route("/mini")
def mini():
    db = sqlite3.connect(db_dir)
    c = db.cursor()
    c.execute(
        "SELECT max(fixtures.gameweek) FROM results JOIN fixtures on fixtures.fixture_id = results.fixture_id WHERE results.season = ? ",
        (season,),
    )

    response = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/")
    data = response.json()
    gw = next(event["id"] for event in data["events"] if event["is_current"])

    sql_statement = """
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
            WHERE predictions.season = ?
            AND fixtures.gameweek >= 20
            AND predictions.home_goals <> 9 AND predictions.away_goals <> 9
            AND players.player_id IN (20, 1, 8 ,10 ,21 , 23, 31, 32, 37)
            GROUP BY players.web_name, players.player_id, players.paid, predictions.fixture_id, predictions.home_goals, predictions.away_goals, results.home_goals, results.away_goals
        ),
        current_position AS (
            SELECT
                ROW_NUMBER() OVER (ORDER BY SUM([correct result point] + [correct score point]) DESC, SUM([correct score point]) DESC, SUM([correct result point]) DESC, web_name) AS [current_position],
                web_name,
                player_id,
                paid,
                SUM([correct result point]) AS [Correct Result],
                SUM([correct score point]) AS [Correct Score],
                SUM([correct result point] + [correct score point]) AS [Total Points]
            FROM current_table
            GROUP BY web_name, player_id, paid
        ),
        previous_position AS (
            SELECT
                ROW_NUMBER() OVER (ORDER BY SUM([correct result point] + [correct score point]) DESC, SUM([correct score point]) DESC, SUM([correct result point]) DESC, web_name) AS [previous_position],
                web_name,
                player_id
            FROM (
                SELECT
                    players.web_name,
                    players.player_id,
                    players.paid,
                    fixtures.gameweek,
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
                WHERE 
                    fixtures.gameweek <= (
                        SELECT 
                            MAX(gameweek) - 1
                        FROM 
                            gameweeks
                        WHERE
                            datetime(deadline_dttm) < datetime('now', 'utc')
                    )
                AND fixtures.gameweek >= 20
                AND predictions.season = ?
                AND predictions.home_goals <> 9 AND predictions.away_goals <> 9
                AND players.player_id IN (20, 1, 8 ,10 ,21 , 23, 31, 32, 37)

                GROUP BY players.web_name, players.player_id, players.paid, fixtures.gameweek, predictions.fixture_id, predictions.home_goals, predictions.away_goals, results.home_goals, results.away_goals
            ) AS previous_results
            GROUP BY web_name, player_id
        )

        SELECT
            cp.current_position,
            IFNULL(pp.previous_position, cp.current_position) [pp.previous_position],
            cp.web_name,
            cp.player_id,
            cp.paid,
            cp.[Correct Result],
            cp.[Correct Score],
            cp.[Total Points]
        FROM current_position cp
        LEFT JOIN previous_position pp ON cp.player_id = pp.player_id
        ORDER BY cp.current_position, cp.web_name;

        """

    gameweek_table_sql = """
        WITH cte AS (
            SELECT
                players.web_name,
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
            WHERE 
                fixtures.gameweek = ?
                AND fixtures.season = ?
                AND predictions.home_goals <> 9 AND predictions.away_goals <> 9
                AND players.player_id IN (20, 1, 8 ,10 ,21 , 23, 31, 32, 37)
            GROUP BY players.web_name, predictions.fixture_id, predictions.home_goals, predictions.away_goals, results.home_goals, results.away_goals
        )

        SELECT
            web_name,
            SUM([correct result point]) AS [Correct Result],
            SUM([correct score point]) AS [Correct Score],
            SUM([correct result point] + [correct score point]) AS [Total Points]
        FROM cte
        GROUP BY web_name
        ORDER BY 4 DESC, 2 DESC;
    """

    gw_results_sql = """
        SELECT
            home_team.team_name
            ,results.home_goals
            ,results.away_goals
            ,away_team.team_name
        FROM results
            JOIN fixtures ON results.fixture_id = fixtures.fixture_id
            inner join teams as away_team on away_team.team_id = fixtures.away_teamid
            inner join teams as home_team on home_team.team_id = fixtures.home_teamid
        where gameweek = ? AND results.season = ?
    """

    next_deadline_sql = """

    SELECT 
	    gameweek
        ,deadline_dttm
        ,deadline_date
        ,deadline_time  
    FROM gameweeks 
    WHERE datetime(deadline_dttm) > datetime('now', 'utc')
    LIMIT 1
    """

    league_table = c.execute(sql_statement, (season, season)).fetchall()

    gameweek_table = c.execute(gameweek_table_sql, (gw, season)).fetchall()
    next_deadline = c.execute(next_deadline_sql).fetchone()

    next_deadline_dict = {
        "gameweek": next_deadline[0],
        "deadline_dttm": next_deadline[1],
        "deadline_date": datetime.strptime(next_deadline[2], "%Y-%m-%d").strftime(
            "%a %d %b"
        ),
        "deadline_time": next_deadline[3],
    }

    try:
        week_average = sum([int(i[3]) for i in gameweek_table]) / len(gameweek_table)
    except ZeroDivisionError:
        week_average = 0

    gw_results = c.execute(gw_results_sql, (gw, season)).fetchall()
    league_table_dict = [
        {
            "current_position": row[0],
            "previous_position": row[1],
            "player_name": row[2],
            "player_id": row[3],
            "paid": row[4],
            "correct_result": row[5],
            "correct_score": row[6],
            "total_points": row[7],
        }
        for row in league_table
    ]
    return render_template(
        "index.html",
        league_table=league_table_dict,
        results=gw_results,
        gw=gw,
        week_average=int(round(week_average)),
        gameweek_table=gameweek_table,
        next_deadline=next_deadline_dict,
    )


@app.route("/gameweek/<gw>")
def gameweek_page(gw):
    db = sqlite3.connect(db_dir)
    c = db.cursor()

    gameweek_table_sql = """
        WITH cte AS (
            SELECT
                players.web_name,
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
            WHERE 
                fixtures.gameweek = ?
                AND fixtures.season = ?
                AND players.active = 1
            GROUP BY players.web_name, predictions.fixture_id, predictions.home_goals, predictions.away_goals, results.home_goals, results.away_goals
        )

        SELECT
			row_number() OVER (ORDER BY  SUM([correct result point] + [correct score point]) DESC, SUM([correct result point]) DESC, SUM([correct score point]) DESC) [Position],
            web_name,
            SUM([correct result point]) AS [Correct Result],
            SUM([correct score point]) AS [Correct Score],
            SUM([correct result point] + [correct score point]) AS [Total Points]
        FROM cte
        GROUP BY web_name
        ORDER BY 1 
    """

    gw_results_sql = """
        SELECT
            home_team.team_name [Home Team]
            ,results.home_goals
            ,results.away_goals
            ,away_team.team_name [Away Team]
        FROM results
            JOIN fixtures ON results.fixture_id = fixtures.fixture_id
            inner join teams as away_team on away_team.team_id = fixtures.away_teamid
            inner join teams as home_team on home_team.team_id = fixtures.home_teamid
        where gameweek = ? AND results.season = ?
        ORDER BY fixtures.kickoff_dttm
    """

    gameweek_table = c.execute(gameweek_table_sql, (gw, season)).fetchall()
    gw_results = c.execute(gw_results_sql, (gw, season)).fetchall()

    try:
        week_average = sum([int(i[4]) for i in gameweek_table]) / len(gameweek_table)
    except ZeroDivisionError:
        week_average = 0

    predictions_sql = """
            WITH CTE AS (
            SELECT 
                f.fixture_id,
                MAX(CASE WHEN home_goals = 9 AND away_goals = 9 THEN 1 ELSE 0 END) AS [Not Provided],
                f.kickoff_dttm,
                CASE 
                    WHEN datetime(f.kickoff_dttm) > datetime('now', 'utc') THEN 1
                    ELSE 0
                END AS is_future_event
            FROM
                predictions AS P
                JOIN fixtures AS F ON F.fixture_id = P.fixture_id
                JOIN players AS pl ON pl.player_id = p.player_id
            WHERE 
                f.gameweek = ? AND f.season = ?
                AND pl.active = 1

            GROUP BY 
                f.fixture_id, 
                f.kickoff_dttm
            )

            SELECT 
                pl.web_name
                ,p.home_goals
                ,p.away_goals
                ,ht.team_name [home_team]
                ,at.team_name [away_team]
				,f.kickoff_dttm
                ,f.fixture_id

            FROM 
                cte
                JOIN predictions AS P ON P.fixture_id = cte.fixture_id
                JOIN players AS pl ON pl.player_id = p.player_id
                JOIN fixtures AS f ON f.fixture_id = p.fixture_id
                JOIN teams AS ht on ht.team_id = f.home_teamid
                JOIN teams AS at on at.team_id = f.away_teamid
            WHERE 1=1 
                AND (
                (is_future_event = 1 AND [Not Provided] = 0)  
                OR
                is_future_event = 0)
                AND pl.active = 1
            ORDER BY web_name, cte.kickoff_dttm
    """
    predictions = c.execute(predictions_sql, (gw, season)).fetchall()

    predictions_dict = {}
    for row in predictions:
        match = f"{row[3].title()} v {row[4].title()}"
        if match not in predictions_dict:
            predictions_dict[match] = []
        predictions_dict[match].append(
            {
                "player_name": row[0],
                "predicted_home_goals": row[1],
                "predicted_away_goals": row[2],
                "kickoff_dttm": row[5],
                "fixture_id": row[6],
            }
        )

    prediction_percentages = {}
    for match, predictions in predictions_dict.items():
        total_predictions = len(predictions)
        home_win_count = sum(
            1
            for p in predictions
            if p["predicted_home_goals"] > p["predicted_away_goals"]
        )
        draw_count = sum(
            1
            for p in predictions
            if p["predicted_home_goals"] == p["predicted_away_goals"]
        )
        away_win_count = sum(
            1
            for p in predictions
            if p["predicted_home_goals"] < p["predicted_away_goals"]
        )

        prediction_percentages[match] = {
            "home_win": (
                round((home_win_count / total_predictions) * 100, 1)
                if total_predictions
                else 0
            ),
            "draw": (
                round((draw_count / total_predictions) * 100, 1)
                if total_predictions
                else 0
            ),
            "away_win": (
                round((away_win_count / total_predictions) * 100, 1)
                if total_predictions
                else 0
            ),
            "kickoff_dttm": predictions[0]["kickoff_dttm"],
            "home_win_count": home_win_count,
            "draw_count": draw_count,
            "away_win_count": away_win_count,
            "fixture_id": predictions[0]["fixture_id"],
        }

        # Sort the dictionary by kickoff_dttm
    sorted_predictions = dict(
        sorted(prediction_percentages.items(), key=lambda item: item[1]["kickoff_dttm"])
    )

    league_table_dict = [
        {
            "position": row[0],
            "player_name": row[1],
            "correct_result": row[2],
            "correct_score": row[3],
            "total_points": row[4],
        }
        for row in gameweek_table
    ]
    results_dict = [
        {
            "Home_Team": row[0],
            "Home_Goals": row[1],
            "Away_Goals": row[2],
            "Away_Team": row[3],
        }
        for row in gw_results
    ]

    db.close()
    return render_template(
        "gameweek.html",
        gameweek=gw,
        week_average=int(round(week_average)),
        gameweek_table=league_table_dict,
        results=results_dict,
        predictions_dict=predictions_dict,
        prediction_percentages=sorted_predictions,
    )


@app.route("/<player_id>")
def player_page(player_id):
    db = sqlite3.connect(db_dir)
    c = db.cursor()
    sql_statement = """
        WITH cte AS (
            SELECT
                players.web_name,
                players.player_name,
			    fixtures.fixture_id,
                fixtures.gameweek,
				predictions.player_id,
                HT.team_name AS [Home Team],
                predictions.home_goals AS [predicted home goals],
                predictions.away_goals AS [predicted away goals],
				AT.team_name AS [Away Team],
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
                END AS [correct score point],
                fixtures.kickoff_dttm

            FROM predictions
                JOIN results ON results.fixture_id = predictions.fixture_id
                JOIN players ON players.player_id = predictions.player_id
				JOIN fixtures ON fixtures.fixture_id = predictions.fixture_id
				INNER JOIN teams AS HT ON HT.team_id = fixtures.home_teamid
				INNER JOIN teams AS AT ON AT.team_id = fixtures.away_teamid
            WHERE predictions.season = ?
                -- AND players.active = 1

            GROUP BY players.web_name, predictions.fixture_id, predictions.home_goals, predictions.away_goals, results.home_goals, results.away_goals
        )

	Select * from cte

	where player_id = ?

	order by datetime(kickoff_dttm)    
    """
    predictions = c.execute(sql_statement, (season, player_id)).fetchall()
    gameweeks = set([i[3] for i in predictions])
    web_name = predictions[0][0]
    player_name = predictions[0][1]

    prediction_data = {}
    for gw in gameweeks:
        prediction_data[gw] = []  # Initialize an empty list for each gameweek
        for prediction in predictions:
            if gw == prediction[3]:
                prediction_data[gw].append(
                    prediction[5:]
                )  # Append prediction data to the list
    return render_template(
        "player_page.html",
        prediction_data=prediction_data,
        player_name=player_name,
        web_name=web_name,
    )


@app.route("/results")
def results():
    db = sqlite3.connect(db_dir)
    c = db.cursor()
    c.execute(
        "SELECT fixtures.gameweek FROM results JOIN fixtures on fixtures.fixture_id = results.fixture_id WHERE results.season = ? ORDER BY gameweek DESC",
        (season,),
    )
    gw = c.fetchone()[0]

    gameweek_table_sql = """
        WITH cte AS (
            SELECT
                players.web_name,
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
            WHERE fixtures.gameweek = ?
                AND fixtures.season = ?
                AND players.active = 1
            GROUP BY players.web_name, predictions.fixture_id, predictions.home_goals, predictions.away_goals, results.home_goals, results.away_goals
        )

        SELECT
            web_name,
            SUM([correct result point]),
            SUM([correct score point]),
            SUM([correct result point] + [correct score point]) AS [Total Points]
        FROM cte
        GROUP BY web_name
        ORDER BY 4 DESC, 2 DESC;
    """

    c.execute(gameweek_table_sql, (gw, season))
    data = c.fetchall()
    db.close()

    result = []
    for row in data:
        player_name, total_points = row[0], row[3]
        result.append(
            {"player_name": player_name.title(), "Total Points": total_points}
        )

    return jsonify(result)


@app.route("/fixtures/<gw>")
def fixtures(gw):
    db = sqlite3.connect(db_dir)
    c = db.cursor()
    fixtures_sql = f"""
        SELECT
            ht.team_name
            ,aw.team_name
        FROM fixtures
            JOIN teams AS ht ON fixtures.home_teamid = ht.team_id
            JOIN teams AS aw ON fixtures.away_teamid = aw.team_id
        WHERE fixtures.gameweek = ?
            and fixtures.season = ?
        ORDER BY fixtures.kickoff_dttm
    """

    deadline_time_sql = f"""
        SELECT
            deadline_date, deadline_time
        FROM 
            gameweeks
        WHERE gameweek = ?
    """

    c.execute(fixtures_sql, (gw, season))
    data = c.fetchall()
    c.execute(deadline_time_sql, (gw,))
    deadline = c.fetchone()
    db.close()
    text = ""
    for row in data:
        text = text + f"{row[0].title()} - {row[1].title()}\n"

    current_date = datetime.now().date()
    deadline_date = datetime.strptime(deadline[0], "%Y-%m-%d").date()

    if deadline_date == current_date + timedelta(days=1):
        text += "\nDeadline tomorrow at " + deadline[1]
    elif deadline_date == current_date:
        text += "Deadline today at " + deadline[1]
    else:
        text += f"\nDeadline on: {deadline_date.strftime('%d %b %Y')} at: {deadline[1]}"

    response = Response(text, 200)
    response.mimetype = "text/plain"
    return response


@app.route("/fixtures")
def fixtures_list():
    """Homepage with links to available gameweeks."""
    db = sqlite3.connect(db_dir)
    c = db.cursor()
    c.execute(
        "SELECT DISTINCT gameweek FROM fixtures WHERE gameweek IS NOT NULL and fixtures.season = ? ORDER BY gameweek",
        (season,),
    )
    gameweeks = [row[0] for row in c.fetchall()]
    db.close()
    links_html = "\n".join(
        f'<li><a href="/fixtures/{gw}">Gameweek {gw}</a></li>' for gw in gameweeks
    )
    page_content = f"<ul>{links_html}</ul>"
    return Response(page_content, 200)


@app.route("/secondchance")
def second():
    second_chance_start = 23
    db = sqlite3.connect(db_dir)
    c = db.cursor()
    c.execute(
        "SELECT max(fixtures.gameweek) FROM results JOIN fixtures on fixtures.fixture_id = results.fixture_id WHERE results.season = ? ",
        (season,),
    )

    response = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/")
    data = response.json()
    gw = next(event["id"] for event in data["events"] if event["is_current"])

    sql_statement = """
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
            WHERE predictions.season = ?
				AND fixtures.gameweek >= ?
                AND players.active = 1
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
        ),
        previous_position AS (
            SELECT
                ROW_NUMBER() OVER (ORDER BY SUM([correct result point] + [correct score point]) DESC, SUM([correct result point]) DESC, SUM([correct score point]) DESC, web_name) AS [previous_position],
                web_name,
                player_id
            FROM (
                SELECT
                    players.web_name,
                    players.player_id,
                    players.paid,
                    fixtures.gameweek,
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
                WHERE 
                    fixtures.gameweek <= (
                        SELECT 
                            MAX(gameweek) - 1
                        FROM 
                            gameweeks
                        WHERE
                            datetime(deadline_dttm) < datetime('now', 'utc')
                    )
                    AND predictions.season = ?
					AND fixtures.gameweek = ?
                    AND players.active = 1
                GROUP BY players.web_name, players.player_id, players.paid, fixtures.gameweek, predictions.fixture_id, predictions.home_goals, predictions.away_goals, results.home_goals, results.away_goals
            ) AS previous_results
            GROUP BY web_name, player_id
        )

        SELECT
            cp.current_position,
            IFNULL(pp.previous_position, cp.current_position) [pp.previous_position],
            cp.web_name,
            cp.player_id,
            cp.paid,
            cp.[Correct Result],
            cp.[Correct Score],
            cp.[Total Points]
        FROM current_position cp
        LEFT JOIN previous_position pp ON cp.player_id = pp.player_id
        ORDER BY cp.current_position, cp.web_name;

        """

    gameweek_table_sql = """
        WITH cte AS (
            SELECT
                players.web_name,
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
            WHERE 
                fixtures.gameweek = ?
                AND fixtures.season = ?
                AND players.active = 1
            GROUP BY players.web_name, predictions.fixture_id, predictions.home_goals, predictions.away_goals, results.home_goals, results.away_goals
        )

        SELECT
            web_name,
            SUM([correct result point]) AS [Correct Result],
            SUM([correct score point]) AS [Correct Score],
            SUM([correct result point] + [correct score point]) AS [Total Points]
        FROM cte
        GROUP BY web_name
        ORDER BY 4 DESC, 2 DESC;
    """

    gw_results_sql = """
        SELECT
            home_team.team_name
            ,results.home_goals
            ,results.away_goals
            ,away_team.team_name
        FROM results
            JOIN fixtures ON results.fixture_id = fixtures.fixture_id
            inner join teams as away_team on away_team.team_id = fixtures.away_teamid
            inner join teams as home_team on home_team.team_id = fixtures.home_teamid
        where gameweek = ? AND results.season = ?
    """

    next_deadline_sql = """

    SELECT 
	    gameweek
        ,deadline_dttm
        ,deadline_date
        ,deadline_time  
    FROM gameweeks 
    WHERE datetime(deadline_dttm) > datetime('now', 'utc')
    LIMIT 1
    """

    league_table = c.execute(
        sql_statement, (season, second_chance_start, season, second_chance_start)
    ).fetchall()

    gameweek_table = c.execute(gameweek_table_sql, (gw, season)).fetchall()
    next_deadline = c.execute(next_deadline_sql).fetchone()

    next_deadline_dict = {
        "gameweek": next_deadline[0],
        "deadline_dttm": next_deadline[1],
        "deadline_date": datetime.strptime(next_deadline[2], "%Y-%m-%d").strftime(
            "%a %d %b"
        ),
        "deadline_time": next_deadline[3],
    }

    try:
        week_average = sum([int(i[3]) for i in gameweek_table]) / len(gameweek_table)
    except ZeroDivisionError:
        week_average = 0

    gw_results = c.execute(gw_results_sql, (gw, season)).fetchall()
    league_table_dict = [
        {
            "current_position": row[0],
            "previous_position": row[1],
            "player_name": row[2],
            "player_id": row[3],
            "paid": row[4],
            "correct_result": row[5],
            "correct_score": row[6],
            "total_points": row[7],
        }
        for row in league_table
    ]
    return render_template(
        "index.html",
        league_table=league_table_dict,
        results=gw_results,
        gw=gw,
        week_average=int(round(week_average)),
        gameweek_table=gameweek_table,
        next_deadline=next_deadline_dict,
    )


@app.route("/<player_name>/<team_name>")
def team_predictions(player_name, team_name):
    player_name = player_name.lower().replace("-", " ")
    team_name = team_name.lower().replace("-", " ")
    db = sqlite3.connect(db_dir)
    c = db.cursor()
    sql_statement = """
        SELECT
            players.web_name,
            ht.team_name AS home_team,
            predictions.home_goals,
            predictions.away_goals,
            at.team_name AS away_team,
            fixtures.kickoff_dttm
        FROM predictions
            JOIN players ON players.player_id = predictions.player_id
            JOIN fixtures ON fixtures.fixture_id = predictions.fixture_id
            JOIN teams AS ht ON ht.team_id = fixtures.home_teamid
            JOIN teams AS at ON at.team_id = fixtures.away_teamid
        WHERE players.player_name = ? AND (ht.team_name = ? OR at.team_name = ?)
        	AND datetime('now', 'utc') >= datetime(fixtures.kickoff_dttm)   
        ORDER BY fixtures.kickoff_dttm
    """
    predictions = c.execute(
        sql_statement, (player_name, team_name, team_name)
    ).fetchall()
    db.close()
    predictions_dict = [
        {
            "player_name": row[0],
            "home_team": row[1],
            "predicted_home_goals": row[2],
            "predicted_away_goals": row[3],
            "away_team": row[4],
            "kickoff_time": row[5],
        }
        for row in predictions
    ]
    return render_template(
        "team_predictions.html",
        player_name=player_name,
        team_name=team_name,
        predictions=predictions_dict,
    )


@app.route("/league_table/<player_name>")
def get_league_table(player_name):
    player_name = player_name.lower().replace("-", " ")
    db = sqlite3.connect(db_dir)
    c = db.cursor()
    sql_statement = """
        WITH actual_cte AS (
            SELECT 
                ht.team_name AS "Home Team",
                ht.team_id AS home_id,
                results.home_goals,
                results.away_goals,
                at.team_id AS away_id,
                at.team_name AS "Away Team",
                CASE 
                    WHEN results.home_goals > results.away_goals THEN 'Home Win'
                    WHEN results.home_goals < results.away_goals THEN 'Home Loss'
                    ELSE 'Draw' 
                END AS HomeResult,
                CASE 
                    WHEN results.home_goals > results.away_goals THEN 'Away Loss'
                    WHEN results.home_goals < results.away_goals THEN 'Away Win'
                    ELSE 'Draw'
                END AS AwayResult
            FROM 
                results
                JOIN fixtures ON results.fixture_id = fixtures.fixture_id 
                JOIN teams AS ht ON ht.team_id = fixtures.home_teamid
                JOIN teams AS at ON at.team_id = fixtures.away_teamid
        )

        -- Create the actual league table based on actual results
        , actual_league AS (
            SELECT 
                Team,
                team_id,
                ROW_NUMBER() OVER (ORDER BY SUM(Points) DESC, SUM(GoalsFor) - SUM(GoalsAgainst) DESC) AS ActualPosition,
                COUNT(*) AS GamesPlayed,
                SUM(Points) AS Points,
                SUM(GoalsFor) AS GoalsFor,
                SUM(GoalsAgainst) AS GoalsAgainst,
                SUM(GoalsFor) - SUM(GoalsAgainst) AS GoalDifference,
                SUM(Win) AS Wins,
                SUM(Draw) AS Draw,
                SUM(Loss) AS Loss
            FROM (
                SELECT 
                    home_id AS team_id,
                    "Home Team" AS Team,
                    CASE 
                        WHEN HomeResult = 'Home Win' THEN 3
                        WHEN HomeResult = 'Draw' THEN 1
                        ELSE 0
                    END AS Points,
                    home_goals AS GoalsFor,
                    away_goals AS GoalsAgainst,
                    CASE WHEN HomeResult = 'Home Win' THEN 1 ELSE 0 END AS Win,
                    CASE WHEN HomeResult = 'Home Loss' THEN 1 ELSE 0 END AS Loss,
                    CASE WHEN HomeResult = 'Draw' THEN 1 ELSE 0 END AS Draw
                FROM actual_cte
                
                UNION ALL
                
                SELECT 
                    away_id AS team_id,
                    "Away Team" AS Team,
                    CASE 
                        WHEN AwayResult = 'Away Win' THEN 3
                        WHEN AwayResult = 'Draw' THEN 1
                        ELSE 0
                    END AS Points,
                    away_goals AS GoalsFor,
                    home_goals AS GoalsAgainst,
                    CASE WHEN AwayResult = 'Away Win' THEN 1 ELSE 0 END AS Win,
                    CASE WHEN AwayResult = 'Away Loss' THEN 1 ELSE 0 END AS Loss,
                    CASE WHEN AwayResult = 'Draw' THEN 1 ELSE 0 END AS Draw
                FROM actual_cte
            ) AS CombinedResults
            GROUP BY Team
        )

        ,predicted_league AS (
            SELECT 
                players.web_name,
                ht.team_name AS "Home Team",
                ht.team_id AS Home_ID,
                predictions.home_goals,
                predictions.away_goals,
                at.team_id AS Away_ID,
                at.team_name AS "Away Team",
                CASE 
                    WHEN predictions.home_goals > predictions.away_goals THEN 'Home Win'
                    WHEN predictions.home_goals < predictions.away_goals THEN 'Home Loss'
                    ELSE 'Draw'
                END AS HomeResult,
                CASE 
                    WHEN predictions.home_goals > predictions.away_goals THEN 'Away Loss'
                    WHEN predictions.home_goals < predictions.away_goals THEN 'Away Win'
                    ELSE 'Draw'
                END AS AwayResult
            FROM 
                predictions
                JOIN players ON predictions.player_id = players.player_id
                JOIN fixtures ON predictions.fixture_id = fixtures.fixture_id 
                JOIN teams AS ht ON ht.team_id = fixtures.home_teamid
                JOIN teams AS at ON at.team_id = fixtures.away_teamid
            WHERE
                players.player_name = ?
                AND datetime(fixtures.kickoff_dttm) < datetime('now', 'utc')

        )

        , predicted_table AS(

        SELECT 
            Team,
            team_id,
            ROW_NUMBER() OVER (ORDER BY SUM(Points) DESC, SUM(GoalsFor) - SUM(GoalsAgainst) DESC) [Position],
            COUNT(*) AS GamesPlayed,
            SUM(Points) AS Points,
            SUM(GoalsFor) AS GoalsFor,
            SUM(GoalsAgainst) AS GoalsAgainst,
            SUM(GoalsFor) - SUM(GoalsAgainst) AS GoalDifference,
            SUM(Win) AS Wins,
            SUM(Draw) AS Draw,
            SUM(Loss) AS Loss
        FROM (
            SELECT 
                home_id AS team_id,
                "Home Team" AS Team,
                CASE 
                    WHEN HomeResult = 'Home Win' THEN 3
                    WHEN HomeResult = 'Draw' THEN 1
                    ELSE 0
                END AS Points,
                home_goals AS GoalsFor,
                away_goals AS GoalsAgainst,
                CASE WHEN HomeResult = 'Home Win' THEN 1 ELSE 0 END AS [Win],
                CASE WHEN HomeResult = 'Home Loss' THEN 1 ELSE 0 END AS [Loss],
                CASE WHEN HomeResult = 'Draw' THEN 1 ELSE 0 END AS [Draw]
                

            FROM predicted_league
            
            UNION ALL
            
            SELECT 
                away_id AS team_id,
                "Away Team" AS Team,
                CASE 
                    WHEN AwayResult = 'Draw' THEN 1
                    WHEN AwayResult = 'Away Win' THEN 3
                    ELSE 0
                END AS Points,
                away_goals AS GoalsFor,
                home_goals AS GoalsAgainst,
                CASE WHEN AwayResult = 'Away Win' THEN 1 ELSE 0 END AS [Win],
                CASE WHEN AwayResult = 'Away Loss' THEN 1 ELSE 0 END AS [Loss],
                CASE WHEN AwayResult = 'Draw' THEN 1 ELSE 0 END AS [Draw]
            FROM predicted_league
        ) AS CombinedResults
        GROUP BY Team
        ORDER BY Points DESC, GoalDifference DESC, GoalsFor DESC
        )


        SELECT 
            pt.Team
            ,pt.Position
            ,pt.GamesPlayed
            ,pt.Points
            ,pt.GoalsFor
            ,pt.GoalsAgainst
            ,pt.GoalDifference
            ,pt.Wins
            ,pt.Draw
            ,pt.Loss
            ,pt.Position - al.ActualPosition [differences]
        FROM predicted_table AS pt
            JOIN actual_league AS al ON pt.team_id = al.team_id
        ORDER BY pt.Position
    """
    league_table = c.execute(sql_statement, (player_name,)).fetchall()
    db.close()
    league_table_dict = [
        {
            "Team": row[0],
            "Position": row[1],
            "GamesPlayed": row[2],
            "Points": row[3],
            "GoalsFor": row[4],
            "GoalsAgainst": row[5],
            "GoalDifference": row[6],
            "Wins": row[7],
            "Draw": row[8],
            "Loss": row[9],
            "CurrentTable": row[10],
        }
        for row in league_table
    ]
    return render_template(
        "leaguetable.html", league_table=league_table_dict, player_name=player_name
    )


@app.errorhandler(404)
def page_not_found(e):
    # You can render a custom 404 template or return a custom response
    return render_template("404.html"), 404


@app.route("/predictionslist/<gw>")
def predictions_list(gw):
    with sqlite3.connect(db_dir) as db:
        c = db.cursor()

        # Use the database to filter out invalid rows (perform filtering in the SQL query)
        query = """
            WITH CTE AS (
            SELECT 
                f.fixture_id,
                MAX(CASE WHEN home_goals = 9 AND away_goals = 9 THEN 1 ELSE 0 END) AS [Not Provided],
                f.kickoff_dttm,
                CASE 
                    WHEN datetime(f.kickoff_dttm) > datetime('now', 'utc') THEN 1
                    ELSE 0
                END AS is_future_event
            FROM
                predictions AS P
                JOIN fixtures AS F ON F.fixture_id = P.fixture_id
                JOIN players as pl on pl.player_id = p.player_id
            WHERE 
                f.gameweek = ? AND f.season = ?
                AND pl.active = 1
            GROUP BY 
                f.fixture_id, 
                f.kickoff_dttm
            )

            SELECT 
                pl.web_name
                ,p.home_goals
                ,p.away_goals
                ,ht.team_name [home_team]
                ,at.team_name [away_team]
            FROM 
                cte
                JOIN predictions AS P ON P.fixture_id = cte.fixture_id
                JOIN players AS pl ON pl.player_id = p.player_id
                JOIN fixtures AS f ON f.fixture_id = p.fixture_id
                JOIN teams AS ht on ht.team_id = f.home_teamid
                JOIN teams AS at on at.team_id = f.away_teamid
            WHERE 1=1 
                AND (
                (is_future_event = 1 AND [Not Provided] = 0)  
                OR
                is_future_event = 0)
                AND pl.active = 1
            ORDER BY web_name, cte.kickoff_dttm
        """
    # Get a list of players that have 9-9 predictions in the given gameweek
    c.execute(
        """
        SELECT 
            DISTINCT pl.web_name
        FROM predictions AS p
            JOIN players AS pl ON pl.player_id = p.player_id
            JOIN fixtures AS f ON f.fixture_id = p.fixture_id
        WHERE 
            f.gameweek = ? AND p.home_goals = 9 AND p.away_goals = 9 AND p.season = ?
            AND datetime(f.kickoff_dttm) >= datetime('now', 'utc')
            AND pl.active = 1
        ORDER BY 
            pl.web_name;
        """,
        (gw, season),
    )
    players_with_9_9 = c.fetchall()

    # Execute query, passing the current time for filtering
    c.execute(query, (gw, season))

    # Fetch the results
    data = c.fetchall()

    # Process the results into a more efficient format
    predictions = {}
    for row in data:
        player_name, home_goals, away_goals, home_team, away_team = row
        if player_name not in predictions:
            predictions[player_name] = []
        predictions[player_name].append(
            f"{home_team.title()} {home_goals}-{away_goals} {away_team.title()}"
        )

    # Build the predictions string

    predictions_string = ""

    if players_with_9_9:
        predictions_string += "Predictions will appear once all players have submitted or the fixtures has kicked off \n\nMissing Scores\n"

        predictions_string += "\n".join(
            player[0].title() for player in players_with_9_9
        )
        predictions_string += "\n\n--------------------------------\n"

    predictions_string += "\n".join(
        f"\n{player_name.title()}\n" + "\n".join(matches)
        for player_name, matches in predictions.items()
    )

    return Response(predictions_string.strip(), 200, mimetype="text/plain")


@app.route("/stats")
def stats():
    db = sqlite3.connect(db_dir)
    c = db.cursor()

    # Total count of predictions
    c.execute(
        """
                SELECT player_name, count(*)
                FROM predictions as p
                    JOIN players as pl on pl.player_id = p.player_id
                WHERE season = ?
                    AND pl.active = 1
                GROUP BY player_name
                ORDER BY count(*) ASC;
                """,
        (season,),
    )
    total_predictions = c.fetchall()

    # Count of 9-9 predictions per gameweek
    c.execute(
        """
    WITH playerscte AS (
        SELECT player_id, web_name FROM players WHERE active = 1
    ),
    gameweekscte AS (
        SELECT 
            gameweek
        FROM 
            gameweeks
        WHERE 
            finished = 1
            OR current_gameweek = 1 
            OR next_gameweek = 1  

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
        (season,),
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

    db.close()

    stats_data = {
        "total_predictions": total_predictions,
        "predictions_9_9": predictions_9_9_list,
        "last_updated": last_updated,
        "max_gameweek": max_gameweek,
        "players": players,
        "number_of_players": number_of_players,
        "total_submitted": total_submitted,
    }

    return render_template("stats.html", stats_data=stats_data)


@app.route("/secretforchris/<gw>")
def secret(gw):
    db = sqlite3.connect(db_dir)
    c = db.cursor()
    c.execute(
        """
    SELECT 
        pl.web_name
        ,p.home_goals
        ,p.away_goals
        ,ht.team_name [home_team]
        ,at.team_name [away_team]
    FROM 
        predictions AS p
        JOIN fixtures AS f on f.fixture_id = p.fixture_id
        JOIN gameweeks AS gw on gw.gameweek = f.gameweek
        JOIN players as pl ON pl.player_id = p.player_id
        JOIN teams AS ht on ht.team_id = f.home_teamid
        JOIN teams AS at on at.team_id = f.away_teamid
    WHERE 
        p.season = ?
        AND f.gameweek = ?
        AND datetime(deadline_dttm) <= datetime('now', 'utc')
        AND pl.active = 1
    ORDER BY web_name, f.kickoff_dttm""",
        (season, gw),
    )

    # Fetch the results
    data = c.fetchall()

    # Process the results into a more efficient format
    predictions = {}
    for row in data:
        player_name, home_goals, away_goals, home_team, away_team = row
        if player_name not in predictions:
            predictions[player_name] = []
        predictions[player_name].append(
            f"{home_team.title()} {home_goals}-{away_goals} {away_team.title()}"
        )
    predictions_string = ""
    predictions_string += "\n".join(
        f"\n{player_name.title()}\n" + "\n".join(matches)
        for player_name, matches in predictions.items()
    )

    return Response(predictions_string.strip(), 200, mimetype="text/plain")


@app.route("/fixture/<fixture_id>")
def fixture_stats(fixture_id):
    db = sqlite3.connect(db_dir)
    c = db.cursor()

    popular_score_sql = """
        WITH CTE AS (
        SELECT 
            f.fixture_id
            ,ht.team_name
            ,at.team_name
            ,pl.player_name
            ,p.home_goals
            ,p.away_goals
            ,p.home_goals|| '-' || p.away_goals [Score]
        FROM 
            fixtures as f
                JOIN teams AS ht on ht.team_id = f.home_teamid
                JOIN teams AS at ON at.team_id = f.away_teamid
                JOIN predictions AS p on p.fixture_id = f.fixture_id
                JOIN players AS pl ON pl.player_id = p.player_id
        WHERE 1=1
            AND f.fixture_id = ?
            AND pl.active = 1
        )

        SELECT
            score	
            ,COUNT(fixture_id)
        FROM cte
        GROUP BY score
        ORDER BY COUNT(fixture_id) DESC
    """

    # Query to get the count of home win, draw, and away win predictions
    prediction_outcomes_sql = """
        WITH CTE AS (
        SELECT 
            f.fixture_id
            ,ht.team_name
            ,at.team_name
            ,pl.web_name
            ,p.home_goals
            ,p.away_goals
            ,p.home_goals|| '-' || p.away_goals [Score]
            ,CASE WHEN
                home_goals > away_goals THEN 'HW'
                WHEN home_goals < away_goals THEN  'AW'
                ELSE 'D'
            END AS [Result]
        FROM 
            fixtures as f
                JOIN teams AS ht on ht.team_id = f.home_teamid
                JOIN teams AS at ON at.team_id = f.away_teamid
                JOIN predictions AS p on p.fixture_id = f.fixture_id
                JOIN players AS pl ON pl.player_id = p.player_id
        WHERE 1=1
            AND f.fixture_id = ?
            AND pl.active = 1
            )

        SELECT
            * 
        FROM
            cte 
        WHERE 1=1
        ORDER by web_name
    """

    # Execute the queries
    c.execute(popular_score_sql, (fixture_id,))
    popular_score = c.fetchall()

    c.execute(prediction_outcomes_sql, (fixture_id,))
    prediction_outcomes = c.fetchall()
    fixture = f"{prediction_outcomes[0][1]} v {prediction_outcomes[0][2]}"

    # Convert prediction outcomes to a dictionary
    prediction_outcomes_dict = {}
    for outcome in prediction_outcomes:
        result = outcome[-1]
        player_name = outcome[3]
        score = outcome[6]
        if result not in prediction_outcomes_dict:
            prediction_outcomes_dict[result] = []
        prediction_outcomes_dict[result].append(
            {"player_name": player_name, "score": score}
        )

    db.close()

    return render_template(
        "fixture_stats.html",
        fixture=fixture,
        popular_score=popular_score,
        prediction_outcomes=prediction_outcomes_dict,
    )


from flask import Flask, render_template

app = Flask(__name__)


if __name__ == "__main__":
    app.run(debug=True)
