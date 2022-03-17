__author__ = "Duncan Seibert"

import argparse
from collections import Counter, defaultdict
from typing import Collection, TextIO

import mtgsdk

from Randard.APIutils import ALL_TRUE_SETS, Cardname, Decklist, Set_code

MAX_CARDS_EXCEPTIONS = ('Relentless Rats', 'Rat Colony', 'Persistent Petitioners', 'Shadowborn Apostle',
                        'Plains', 'Island', 'Swamp', 'Mountain', 'Forest')


class DecklistError(SyntaxError):
    pass


def decklist_parser(decklist_file: str | TextIO, string=False) -> tuple[Decklist, Decklist]:
    """Parses a decklist string where each line is "Nx CARDNAME"
    returns a tuple of two Decklist objects (i.e. collections.Counters) that map card names to the number of that
    card in the deck. The first Decklist is the maindeck, the second is the sideboard"""
    if string:
        lines = decklist_file.splitlines()
    else:
        with open(decklist_file, 'r') as f:
            lines = f.readlines()
    maindeck = Decklist()
    sideboard = Decklist()
    working_decklist = maindeck
    for (idx, line) in enumerate(lines):
        if not line.strip():
            continue  # skips blank lines
        num, *card_words = line.split()
        card_name = Cardname(' '.join(word.strip() for word in card_words))
        num = num.strip('xX')
        if idx == 0 and 'deck' in str(num).lower():
            continue
        elif 'side' in str(num).lower():
            working_decklist = sideboard
            continue
        try:
            num = int(num)
        except ValueError:
            raise DecklistError(f'Each line in the file, except for maindeck and sideboard headings, must start with an integer; line {idx+1} does not')
        working_decklist[card_name] += num
    return maindeck, sideboard


def verify_decklist(decklist: Decklist, sideboard: Decklist | None = None, *, legal_sets: Collection[Set_code] | None = None,
                    max_cards=4, min_deck_size=60, max_deck_size=None, min_sideboard_size=0, max_sideboard_size=15) -> list[str] | bool:
    """takes a decklist or pair of decklists representing maindeck and sideboard, as returned by decklist_parser
    returns True if that deck is valid for the given maximum number of cards and legal sets, or a list of errors otherwise"""

    errors = []

    match (decklist, sideboard):
        case (Counter(), None):
            deck_size = decklist.total()
            if deck_size < min_deck_size:
                errors.append(f"Deck has less than {min_deck_size} cards")
            elif max_deck_size and deck_size > max_deck_size:
                errors.append(f"Deck has more than {max_deck_size} cards")
        case (Counter(), Counter()):
            deck_size = decklist.total()
            sideboard_size = sideboard.total()
            if deck_size < min_deck_size:
                errors.append(f"Deck has less than {min_deck_size} cards")
            elif max_deck_size and deck_size > max_deck_size:
                errors.append(f"Deck has more than {max_deck_size} cards")
            if sideboard_size < min_sideboard_size:
                errors.append(f"Sideboard has less than {min_sideboard_size} cards")
            elif sideboard_size > max_sideboard_size:
                errors.append(f"Sideboard has more than {max_sideboard_size} cards")
            decklist = decklist + sideboard
        case _:
            raise TypeError(f"verify_decklist positional arguments must be of type collections.Counter, had type {[type(decklist), type(sideboard)]}")

    for card, num in decklist.most_common():
        if num <= max_cards:
            break
        if card not in MAX_CARDS_EXCEPTIONS:
            errors.append(f'{card} has more than {max_cards} {"copies" if max_cards > 1 else "copy"}')

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
    return verify_decklist(*decklist, legal_sets=sets)


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
    # main()
    pass
