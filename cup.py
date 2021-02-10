import random

from itertools import zip_longest

with open("cupguesses.txt") as f:
    players = f.readlines()


def grouper(i, n, fillvalue=None):
    args = [iter(i)] * 2
    return zip_longest(fillvalue=fillvalue, *args)


random.shuffle(players)

for home, away in grouper(players, 2):
    print(f'{home.strip()} v {away.strip()}')