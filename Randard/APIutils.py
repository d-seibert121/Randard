__author__ = "Duncan Seibert"

from collections import Counter
from typing import NewType
from mtgsdk import Set
import mtgsdk
import sqlite3
from private_info import DB_LOC


Set_code = NewType('Set_code', str)
Set_name = NewType('Set_Name', str)
Block = NewType('Block', str)
Cardname = NewType('Cardname', str)
Decklist = Counter[Cardname]


USEFUL_SUPPLEMENTAL_SET_TYPES = ("reprint", "un", "commander", "planechase", "archenemy", "vanguard", "masters")

ALL_SETS: list[Set] = Set.all()
CORE_SETS: list[Set] = [set_ for set_ in ALL_SETS if set_.type == 'core']
EXPERT_SETS: list[Set] = [set_ for set_ in ALL_SETS if set_.type == 'expansion']
ALL_TRUE_SETS: list[Set] = CORE_SETS + EXPERT_SETS


def sets_in(card_name: str):
    card = mtgsdk.Card.where(name=card_name).all()
    return card[0].printings.copy()


def scryfall_search(sets=None):
    if sets is None:
        with sqlite3.connect(DB_LOC) as con:
            cur = con.execute("SELECT set_codes FROM seasons ORDER BY CAST(season_number AS REAL) DESC")
            sets = cur.fetchone()[0].split(', ')
    return f'(s:{ " or s:".join(set_ for set_ in sets)})'


