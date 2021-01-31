import random

from itertools import zip_longest

players = [
'Andy Hudson or Dean Charles',
'Dave Melia',
'Gary Regan',
'Chris Hart',
'Sean Burns',
'James Forshaw',
'Jonny Parker',
'Ryan Todd',
'Adam Pitt',
'Scott Frazer',
'Ste Harrison',
'Colin Croft',
'Andy Mckenna', 
'Chris Johnson',
'Josh Jones',
'Amy Fenna',
'Kate Daley',
'Joe Daley',
'Graham Handley', 
'Graham Kay'
]


def grouper(i, n, fillvalue=None):
    args = [iter(i)] * 2
    return zip_longest(fillvalue=fillvalue, *args)


random.shuffle(players)

for home, away in grouper(players, 2):
    print(f'{home} v {away}')