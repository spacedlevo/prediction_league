import re
import csv
from collections import Counter
import sys
import sqlite3
from shutil import copyfile

copyfile("data/database.db", "data/database.backup")
db = sqlite3.connect("data/database.db")
c = db.cursor()

gw = sys.argv[1]


teams_names = {}

c.execute("SELECT team_name FROM teams")
teams = [team[0].lower() for team in c.fetchall()]
c.execute("SELECT player_name FROM players WHERE active = 1")
players = [player[0] for player in c.fetchall()]
fixtures_ids = fixtures_ids = c.execute(
    "SELECT fixture_id FROM fixtures WHERE gameweek = ?", (gw,)
).fetchall()
fixture_len = len(fixtures_ids)
predictions_file = "/home/levo/Dropbox/Predictions/2024_25/gameweek{}.txt".format(gw)
header = ["gameweek", "player", "home_team", "away_team", "home_goals", "away_goals"]


def find_scores(line):
    goals = []
    current_score = ""
    for char in line:
        if char.isdigit():
            current_score += char
        elif current_score:
            goals.append(int(current_score))
            current_score = ""
    if current_score:  # Add the last score if any
        goals.append(int(current_score))
    return goals


def rename_team(string):
    string = string.replace(" ' ", "")
    for key, value in teams_names.items():
        # string = re.sub(r'\b{}\b'.format(key), value, string)
        string = re.sub(key, value, string)
        string = " ".join(string.split())
    return string


def get_predictions(text_msg_file):
    with open(text_msg_file, "r", encoding="utf-8-sig") as f:
        return f.read()


def clean_teams(string):
    predictions_list = []
    string = string.lower()
    lines = string.splitlines()
    for line in lines:
        line = rename_team(line)
        predictions_list.append(line)
    return predictions_list


def extract_teams(line):
    sides = []
    for team in teams:
        if team.lower() in line.lower():
            sides.append(team)
    return sides


def re_extract_teams(line):
    sides = []
    found = re.findall(r"\s?[v]?\s?[a-z']+\s?[a-z']+\s?", line, re.IGNORECASE)
    for i in found:
        for j in teams:
            team = re.findall(r"\b{}\b".format(j), i)
            if len(team) > 0:
                sides.append(team[0])
    return sides


def get_counts():
    with open("data/predictions/predictions{}.csv".format(gw), "r") as f:
        names = []
        prediction_reader = csv.reader(f)
        next(prediction_reader)
        for row in prediction_reader:
            names.append(row[1])
        counts = Counter(names)
        for k, i in counts.items():
            if i != fixture_len:
                print("{} has {} entries".format(k.title(), i))


def check_for_players(prediction):
    submitted_players = set([player[1] for player in predictions])
    not_submitted = [person for person in players if person not in submitted_players]
    return not_submitted


def add_missing_players(not_submitted):
    predictions_list = []
    c.execute(
        """
        SELECT 
            gameweek
            ,ht.team_name
            ,at.team_name
        FROM fixtures
            JOIN teams AS ht ON ht.team_id = fixtures.home_teamid
            JOIN teams AS at ON at.team_id = fixtures.away_teamid
        WHERE 
            gameweek = ?

        """,
        (gw,),
    )
    fixtures = c.fetchall()
    for player in not_submitted:
        for fixture in fixtures:
            add_in_nines = [gw, player, fixture[1], fixture[2], 9, 9]
            predictions_list.append(add_in_nines)
    print(predictions_list)
    return predictions_list


if __name__ == "__main__":
    predictions = []
    string = get_predictions(predictions_file)
    formatted_teams = clean_teams(string)
    for line in formatted_teams:
        if line.strip() in players:
            player = line.strip()
        sides = re_extract_teams(line)
        goals = find_scores(line)
        if len(sides) == 2:
            try:
                predict_line = [gw, player, sides[0], sides[1], goals[0], goals[1]]
            except IndexError:
                predict_line = [gw, player, sides[0], sides[1], 9, 9]
            predictions.append(predict_line)
    not_submitted = check_for_players(predictions)
    predictions.extend(add_missing_players(not_submitted))
    with open("data/predictions/predictions{}.csv".format(gw), "w") as f:
        csvwriter = csv.writer(f)
        csvwriter.writerow(header)
        for line in predictions:
            print(line)
            csvwriter.writerow(line)
    get_counts()
    print(f'Missing: {len(not_submitted)} {", ".join(not_submitted)}')
    print("Done!")
    c.close()
