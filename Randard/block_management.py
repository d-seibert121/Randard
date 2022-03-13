__author__ = "Duncan Seibert"

from mtgsdk import Set
from collections import defaultdict
from typing import NewType


Set_code = NewType('Set_code', str)
Block = NewType('Block', str)

# creates a dict mapping block names to the sets that block contains
_sets = [set_ for set_ in Set.all() if set_.block and set_.type == 'expansion']
block_names = set(set_.block for set_ in _sets)
blocks: defaultdict[Block, list[Set]] = defaultdict(list)
for set_ in _sets:
    blocks[set_.block].append(set_)
