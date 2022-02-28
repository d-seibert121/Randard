__author__ = "Duncan Seibert"

from typing import List
from APIutils import ALL_TRUE_SETS
from random import sample, randint
from mtgsdk import Set


num_expert_sets = randint(6, 8)
randard_format: List[Set] = sample(ALL_TRUE_SETS, num_expert_sets)  # chooses a random sample of sets to use for the format
randard_format_names: List[str] = list(map(lambda x: f'"{x.name}"', randard_format))  # quoted names of chosen sets
print(*randard_format_names, sep=', ')  # prints human-readable format
print('(s:', ' or s: '.join(randard_format_names), ')', sep='')  # prints Scryfall copyable search string
with open('current_sets.txt', 'w') as f:
    f.write('\n'.join(randard_format_names))
