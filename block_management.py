__author__ = "Duncan Seibert"

from mtgsdk import Set
from collections import defaultdict

_sets = [set_ for set_ in Set.all() if set_.block and set_.type=='expansion']
block_names = set(set_.block for set_ in _sets)
blocks = defaultdict(list)
for set_ in _sets:
    blocks[set_.block].append(set_)
