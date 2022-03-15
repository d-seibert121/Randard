__author__ = "Duncan Seibert"

from Randard.APIutils import ALL_TRUE_SETS, Set_code
from random import sample, randint
from mtgsdk import Set
from private_info import DB_LOC
import sqlite3


def generate_format(format_size=None) -> list[Set]:
    if format_size is None:
        format_size = randint(6, 8)
    randard_format: list[Set] = sample(ALL_TRUE_SETS, format_size)  # chooses a random sample of sets to use for the format
    return randard_format


if __name__ == '__main__':
    new_format = generate_format()

    with sqlite3.connect(DB_LOC) as con:
        con.execute("CREATE TABLE IF NOT EXISTS current_sets (id INTEGER PRIMARY KEY, name TEXT, code TEXT)")
        con.execute("DELETE FROM current_sets")
        con.executemany("INSERT INTO current_sets (name, code) VALUES (?, ?)", ((set_.name, set_.code) for set_ in new_format))
