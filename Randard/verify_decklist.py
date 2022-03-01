__author__ = "Duncan Seibert"

import mtgsdk
import argparse
from collections import Counter, defaultdict
from Randard.APIutils import ALL_TRUE_SETS
from typing import Collection, NewType, TextIO

Cardname = NewType('Cardname', str)
Set_code = NewType('Set_code', str)
Decklist = Counter[Cardname]


MAX_CARDS_EXCEPTIONS = ('Relentless Rats', 'Rat Colony', 'Persistent Petitioners', 'Shadowborn Apostle',
                        'Plains', 'Island', 'Swamp', 'Mountain', 'Forest')


def decklist_parser(decklist_file: str | TextIO, string=False) -> Decklist:
    """Parses a decklist string where each line is "Nx CARDNAME" converting that to Counter
    where each key is the name of the card, and the values are the number of that card in the decklist"""
    if string:
        lines = decklist_file.splitlines()
    else:
        with open(decklist_file, 'r') as f:
            lines = f.readlines()
    decklist = Decklist()
    for line in lines:
        num, *card_words = line.split()
        card_name = Cardname(' '.join(word.strip() for word in card_words))
        num.strip('xX')
        try:
            num = int(num)
        except ValueError:
            raise SyntaxError('Each line in the file must start with an integer')
        decklist[card_name] += 1
    return decklist


def verify_decklist(decklist: Decklist, legal_sets: Collection[Set_code] | None = None, max_cards=4, min_deck_size=60) -> list[str] | bool:
    """takes a decklist, as returned by decklist_parser, and returns True if that deck is valid for the
    given maximum number of cards and legal sets, or a list of errors otherwise"""

    errors = []

    for card, num in decklist.most_common():
        if num <= max_cards:
            break
        if card not in MAX_CARDS_EXCEPTIONS:
            errors.append(f'{card} has more than {max_cards} {"copies" if max_cards > 1 else "copy"}')
    if sum(decklist.values()) < min_deck_size:
        errors.append(f"Deck has less than {min_deck_size} cards")
    if legal_sets is not None:
        legal_sets = set(legal_sets)  # this is where I'll revise to allow for special formats
    else:
        legal_sets = ALL_TRUE_SETS
    decklist_cards: list[mtgsdk.Card] = mtgsdk.Card.where(name="|".join(card for card in decklist)).all()
    card_sets: defaultdict[Cardname: set[Set_code]] = \
        {card.name: (set(card.printings) & legal_sets) for card in decklist_cards}
    for card in decklist:
        if not card_sets[card]:
            errors.append(f'{card} is not legal')

    return errors or True


def main():
    parser = argparse.ArgumentParser(description='Verifies that a given .txt decklist is a valid decklist for a format'
                                                 ' consisting of the sets in the other arguments')
    parser.add_argument('decklist_file', type=str, nargs=1)
    parser.add_argument('sets', type=str, nargs='*')
    args = parser.parse_args()
    argument_file = args.decklist_file
    sets = args.sets

    with open(argument_file, 'r') as decklist_file:
        decklist = decklist_parser(decklist_file)
    return verify_decklist(decklist, sets)


def test_unique_sets(cards: dict[str, set[Set_code]]) -> dict[Cardname, Set_code] | None:
    """decklist tester for a unique format variant. Returns None if decklist is not valid for the format, otherwise
    returns a dict mapping each card to the unique set it is paired with.
    In this special format, for each set in Magic's history, you may have up to one representative card,
    but you may choose any of the sets that a card is printed in for it to be the representative of.
    For instance, since the only (non-masters) set that "Jace, the Mind Sculptor" has been printed in is Worldwake,
    if you include a copy of him in your deck, it can contain no other cards that were only printed in Worldwake.
    But, cards like "Dispel", which were printed in other sets, may be included, locking you out of other cards
    from one of the card's other sets.
    Note: Very slow
    """
    # if the set of cards are a legal deck for the 1 card per set format, will return one possible choice of sets for each card
    # otherwise will return None
    cards = {cardname: cards[cardname] for cardname in sorted(cards, key=lambda x: len(cards[x]))}  # this line does double duty:
    # it makes a copy of cards, so you don't end up mutating the object you pass in, and sorts the copy such that cards
    # that are only in a few sets come first, significantly improving the worst-case performance
    card_name: Cardname
    set_names: set[Set_code]
    card_name, set_names = cards.popitem()
    if len(cards) == 0:
        # base case, when we're down to the single card named card_name
        try:
            return {card_name: set_names.pop()}  # just picks an arbitrary set, since you only have one card left
        except (KeyError, IndexError):  # this will happen if there are no sets left in set_names, because all of card_name's sets have been chosen earlier in the process
            return None
    for chosen_set in set_names:
        # this is the recursive case, and we iterate over each set in set_names to see if we can make it work with any of them
        trimmed_cards = {card: sets-{chosen_set} for card, sets in cards.items()}  # card_name got popped, so just have to remove chosen_set from any other card that has it
        rest_of_the_cards = test_unique_sets(trimmed_cards)
        if rest_of_the_cards:  # the function was able to find a legal choice for all the rest of the cards
            return {card_name: chosen_set, **rest_of_the_cards}
    return None  # will only get here if each of card_name's sets fail to lead to a valid solution, or it card_name has no sets left


if __name__ == '__main__':
    #main()
    pass