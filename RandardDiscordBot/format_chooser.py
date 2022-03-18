__author__ = "Duncan Seibert"

from random import sample, randint

import mtgsdk

from RandardDiscordBot.APIutils import ALL_TRUE_SETS


def generate_format(format_size=None) -> list[mtgsdk.Set]:
    if format_size is None:
        format_size = randint(6, 8)
    randard_format: list[mtgsdk.Set] = sample(ALL_TRUE_SETS, format_size)  # chooses a random sample of sets to use for the format
    return randard_format
