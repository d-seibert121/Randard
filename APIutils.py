__author__ = "Duncan Seibert"

from typing import List
from mtgsdk import Set

USEFUL_SUPPLEMENTAL_SET_TYPES = ("reprint", "un", "commander", "planechase", "archenemy", "vanguard", "masters")

all_sets: List[Set] = Set.all()
core_sets: List[Set] = [set_ for set_ in all_sets if set_.type == 'core']
expert_sets: List[Set] = [set_ for set_ in all_sets if set_.type == 'expansion']
all_sets: List[Set] = core_sets + expert_sets


def sets_in(card_name: str):
    card = mtgsdk.Card.where(name=card_name).all()
    return card[0].printings.copy()
