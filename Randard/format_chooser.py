__author__ = "Duncan Seibert"

from Randard.APIutils import ALL_TRUE_SETS
from random import sample, randint
from mtgsdk import Set
from private_info import SET_FILE_LOC




def generate_format(format_size = None) -> list[str]:
    if format_size is None:
        format_size = randint(6, 8)
    randard_format: list[Set] = sample(list(ALL_TRUE_SETS), format_size)  # chooses a random sample of sets to use for the format
    return list(map(lambda x: f'"{x.name}"', randard_format))  # quoted names of chosen sets
    # print(*randard_format_names, sep=', ')  # prints human-readable format
    # print('(s:', ' or s:'.join(randard_format_names), ')', sep='')  # prints Scryfall copyable search string


def scryfall_search():
    with open(SET_FILE_LOC, 'r') as f:
        return f"(s:{ ' or s:'.join(line.strip() for line in f) })"


if __name__ == '__main__':
    with open(SET_FILE_LOC, 'w') as f:
        f.write('\n'.join(generate_format()))
