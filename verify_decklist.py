__author__ = "Duncan Seibert"

from typing import List, Set, Dict, Tuple, NewType, Optional, Collection
from typing import Counter as Counter_type
Cardname = NewType('Cardname', str)
Set_code = NewType('Set_code', str)
Decklist = Counter_type[Cardname]
from collections import Counter
import mtgsdk
import argparse
from APIutils import ALL_TRUE_SETS

MAX_CARDS_EXCEPTIONS = ('Relentless Rats', 'Rat Colony', 'Persistent Petitioners', 'Shadowborn Apostle',
                        'Plains', 'Island', 'Swamp', 'Mountain', 'Forest')


def decklist_parser(decklist_file_arg: str) -> Decklist:
    """Parses a text decklist (.txt file) where each line is "Nx CARDNAME" converting that to Counter
    where each key is the name of the card, and the values are the number of that card in the decklist"""
    decklist = Counter()
    with open(decklist_file_arg, 'r') as decklist_file:
        for line in decklist_file:
            num, *card = line.split()
            try:
                num = int(num)
            except ValueError:
                raise SyntaxError('Each line in the file must start with an integer')
            card = Cardname(' '.join(card))
            decklist[card] += 1
    return decklist


def verify_decklist(decklist: Decklist, legal_sets: Optional[Collection[Set_code]] = None, max_cards=4):
    """takes a decklist, as returned by decklist_parser, and returns a bool indicating if that deck is valid for the
    given maximum number of cards and legal sets"""

    errors = []

    for card, num in decklist.most_common():
        if num <= max_cards:
            break
        if card not in MAX_CARDS_EXCEPTIONS:
            errors.append(f'{card} has more than {max_cards} {"copies" if max_cards > 1 else "copy"}')

    if legal_sets is None:
        legal_sets = set(set_.code for set_ in ALL_TRUE_SETS)  # default to all sets being legal
    else:
        legal_sets = set(legal_sets)  # this is where I'll revise to allow for special formats
    sets_where_lookup_string = '|'.join(legal_sets)

    for card in decklist:
        if mtgsdk.Card.where(name=card).where(set=sets_where_lookup_string).all():
            continue
        else:
            errors.append(f'{card} is not legal')

    return errors or True


def main():
    parser = argparse.ArgumentParser(description='Verifies that a given .txt decklist is a valid decklist for a format'
                                                 ' consisting of the sets in the other arguments')
    parser.add_argument('decklist_file', type=str, nargs=1)
    parser.add_argument('sets', type=str, nargs='*')
    parser.parse_args()
    argument_file = parser.decklist_file
    sets = parser.sets

    with open(argument_file, 'r') as decklist_file:
        decklist = decklist_parser(decklist_file)
    return verify_decklist(decklist, sets)


def test_unique_sets(cards: Dict[str, Set[Set_code]]) -> Optional[List[Tuple[Cardname, Set_code]]]:
    # if the set of cards are a legal deck for the 1 card per set format, will return one possible choice of sets for each card
    # otherwise will return None
    cards = {cardname: cards[cardname] for cardname in sorted(cards, key=lambda x: len(cards[x]))}  # this line does double duty:
    # it makes a copy of cards, so you don't end up mutating the object you pass in, and sorts the copy such that cards that are only in a few sets come first, significantly improving the worst-case performance
    cardname: Cardname
    setnames: Set[Set_code]
    cardname, setnames = cards.popitem()
    if len(cards) == 0:
        # base case, when we're down to the single card named cardname
        try:
            return [(cardname, setnames.pop())]  # just picks an arbitrary set, since you only have one card left
        except IndexError:  # this will happen if there are no sets left in setnames, because all of cardname's sets have been chosen earlier in the process
            return None
    for chosen_set in setnames:
        # this is the recursive case, and we iterate over each set in setnames to see if we can make it work with any of them
        trimmed_cards = {card: sets-{chosen_set} for card, sets in cards.items()} #cardname got popped, so just have to remove chosen_set from any other card that has it
        rest_of_the_cards = test_unique_sets(trimmed_cards)
        if rest_of_the_cards:  # the function was able to find a legal choice for all the rest of the cards
            return [(cardname, chosen_set), *rest_of_the_cards]
    return None  # will only get here if each of cardname's sets fail to lead to a valid solution, or it cardname has no sets left
