import re
import csv
from collections import Counter
import sys
import sqlite3
from shutil import copyfile

copyfile('data/predictions.db', 'data/predictions.backup')
db = sqlite3.connect('data/predictions.db')
c = db.cursor()

gw = sys.argv[1]


teams_names = {
    'united':'utd',
    'spurs':'tottenham',
    'wolves':'wolverhampton'
}

c.execute('SELECT name FROM teams') 
teams = [team[0] for team in c.fetchall()]
c.execute('SELECT name FROM players') 
players = [player[0] for player in c.fetchall()]
predictions_file = '/home/levo/Dropbox/Predictions/2021_22/gameweek{}.txt'.format(gw)
header = ['gameweek', 'player', 'home_team', 'away_team', 'home_goals', 'away_goals']


def find_scores(line):
    goals = []
    for char in line:
        if char.isdigit():
            goals.append(char)

    return goals


def rename_team(string):
    string = string.replace(" ' ", "")
    for key, value in teams_names.items():
        # string = re.sub(r'\b{}\b'.format(key), value, string)
        string = re.sub(key, value, string)
        string = ' '.join(string.split())
    return string


def get_predictions(text_msg_file):
    with open(text_msg_file, 'r', encoding='utf-8-sig') as f:
        return f.read()


def clean_teams(string):
    predictions_list = []
    string = string.lower()
    lines = string.splitlines()
    for line in lines:
        line = rename_team(line)
        predictions_list.append(line)
    return predictions_list


def re_extract_teams(line):
    sides = []
    found = re.findall(r'\s?[v]?\s?[a-z]+\s?[a-z]+\s?', line, re.IGNORECASE)
    for i in found:
        for j in teams:
            team = re.findall(r'\b{}\b'.format(j), i)
            if len(team) > 0:
                sides.append(team[0])
    return sides


def get_counts():
    with open('data/predictions/predictions{}.csv'.format(gw), 'r') as f:
        names = []
        prediction_reader = csv.reader(f)
        next(prediction_reader)
        for row in prediction_reader:
            names.append(row[1])
        counts = Counter(names)
        for k, i in counts.items():
            if i != 10:
                print('{} has {} entries'.format(k.title(), i))


if __name__ == '__main__':
    predictions = []
    string = get_predictions(predictions_file)
    formatted_teams = clean_teams(string)
    for line in formatted_teams:
        if line.strip() in players:
            player = line.strip()
            print(player)
        sides = re_extract_teams(line)
        goals = find_scores(line)
        if len(sides) == 2:
            print(player + ' ' + line)
            predict_line = [gw, player, sides[0], sides[1], goals[0], goals[1]]
            predictions.append(predict_line)
    with open('data/predictions/predictions{}.csv'.format(gw), 'w') as f:
        csvwriter = csv.writer(f)
        csvwriter.writerow(header)
        for line in predictions:
            csvwriter.writerow(line)
    get_counts()
    print('Done!')
