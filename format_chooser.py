__author__ = "Duncan Seibert"

from typing import List
from APIutils import core_sets, expert_sets
from random import sample, randint
from mtgsdk import Set


num_expert_sets = randint(6, 7)
randard_format: List[Set] = list(sample(expert_sets, num_expert_sets) + sample(core_sets, 1))  # chooses 6 or 7 expert expansions, followed by 1 core set for the format
randard_format_names: List[str] = list(map(lambda x: "'" + x.name + "'", randard_format))  # quoted names of chosen sets
print(*randard_format_names, sep=', ')  # prints human-readable format
print('(s:', ' or s: '.join(randard_format_names), ')', sep='')  # prints Scryfall copyable search string
