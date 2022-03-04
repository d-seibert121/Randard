__author__ = "Duncan Seibert"

from mtgsdk import Set
import mtgsdk

USEFUL_SUPPLEMENTAL_SET_TYPES = ("reprint", "un", "commander", "planechase", "archenemy", "vanguard", "masters")

ALL_SETS: list[Set] = Set.all()
CORE_SETS: list[Set] = [set_ for set_ in ALL_SETS if set_.type == 'core']
EXPERT_SETS: list[Set] = [set_ for set_ in ALL_SETS if set_.type == 'expansion']
ALL_TRUE_SETS: list[Set] = CORE_SETS + EXPERT_SETS


def sets_in(card_name: str):
    card = mtgsdk.Card.where(name=card_name).all()
    return card[0].printings.copy()
