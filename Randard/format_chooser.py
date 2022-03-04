__author__ = "Duncan Seibert"

from Randard.APIutils import ALL_TRUE_SETS
from random import sample, randint
from mtgsdk import Set
from private_info import SET_FILE_LOC
from typing import NewType
import json

Set_code = NewType('Set_code', str)

try:
    with open(SET_FILE_LOC, 'r') as f:
        info = json.load(f)
except FileNotFoundError:
    info = {'names': [], 'codes': []}


def generate_format(format_size=None) -> list[Set]:
    if format_size is None:
        format_size = randint(6, 8)
    randard_format: list[Set] = sample(ALL_TRUE_SETS, format_size)  # chooses a random sample of sets to use for the format
    return randard_format


def scryfall_search(sets=None):
    if sets is None:
        sets = info["codes"]
    return f'(s:{ " or s:".join(repr(set_) for set_ in sets)})'


if __name__ == '__main__':
    new_format = generate_format()
    set_names = [set_.name for set_ in new_format]
    set_codes = [set_.code for set_ in new_format]
    with open(SET_FILE_LOC, 'w') as f:
        json.dump({"names": set_names, "codes": set_codes}, f)
