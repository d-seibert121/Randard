import datetime
import sqlite3

import mtgsdk

from Randard.APIutils import Set_name, Set_code
from private_info import DB_LOC


def store_format(mtg_format: list[mtgsdk.Set], database=DB_LOC):
    today = datetime.date.today()
    names = names_string(mtg_format)
    codes = codes_string(mtg_format)
    with sqlite3.connect(database) as con:
        con.execute("INSERT INTO seasons(month, year, set_names, set_codes) VALUES (?, ?, ?, ?)", [f"{today:%B}", today.year, names, codes])


def get_leaderboard(database=DB_LOC) -> list[sqlite3.Row]:
    """Gets the top 10 players from the current season.
    Each element of the returned list is a sqlite3.Row object representing a player, with discord_id and rating keys.
    Players are returned in standing order, with the champion at index 0, runner-up at index 1, etc.
    """
    with sqlite3.connect(database) as con:
        con.row_factory = sqlite3.Row
        cur = con.execute("SELECT discord_id, rating FROM players ORDER BY rating DESC")
        leaderboard = cur.fetchmany(10)
    return leaderboard


def store_leaderboard(database=DB_LOC) -> list[sqlite3.Row]:
    """Creates a new table in the database storing the leaderboard for a particular season, storing the discord id and rating of the top 10 players
    Returns a list of the 10 players, as they exist in the players table, in order from 1st place to 10th"""
    with sqlite3.connect(database) as con:
        con.row_factory = sqlite3.Row
        completed_season = con.execute("SELECT * FROM seasons ORDER BY CAST(season_number AS REAL) DESC").fetchone()
        leaderboard_table_name = f"leaderboard_{completed_season['month']}_{completed_season['year']}"
        con.execute(f"CREATE TABLE IF NOT EXISTS {leaderboard_table_name}(discord_id, rating, name) ")
        con.execute(f"DELETE FROM {leaderboard_table_name}")
        leaderboard = con.execute("SELECT discord_id, rating, name FROM players ORDER BY rating DESC").fetchmany(10)
        con.executemany(f"INSERT INTO {leaderboard_table_name}(discord_id, rating, name) VALUES (?, ?, ?)",
                        [(row['discord_id'], row['rating'], row['name']) for row in leaderboard])
        return leaderboard


def clear_ratings(database=DB_LOC):
    with sqlite3.connect(database) as con:
        con.execute("UPDATE players SET rating=1000")


def get_current_season(database=DB_LOC) -> sqlite3.Row:
    with sqlite3.connect(database) as con:
        con.row_factory = sqlite3.Row
        return con.execute("SELECT * FROM seasons ORDER BY CAST(season_number AS REAL) DESC").fetchone()


def get_legal_set_names(database=DB_LOC) -> list[Set_name]:
    return get_current_season(database)['set_names'].split(', ')


def get_legal_set_codes(database=DB_LOC) -> list[Set_code]:
    return get_current_season(database)['set_codes'].split(', ')


def get_season_number(database=DB_LOC) -> int | str:
    return get_current_season(database)['season_number']


def codes_string(mtg_format: list[mtgsdk.Set]) -> str:
    """Returns a string of comma delimited set codes for the given list of Sets"""
    return ', '.join(set_.code for set_ in mtg_format)


def names_string(mtg_format: list[mtgsdk.Set]) -> str:
    """Returns a string of comma delimited set names for the given list of Sets"""
    return ', '.join(set_.name for set_ in mtg_format)


def scryfall_search(sets=None):
    if sets is None:
        with sqlite3.connect(DB_LOC) as con:
            cur = con.execute("SELECT set_codes FROM seasons ORDER BY CAST(season_number AS REAL) DESC")
            sets = cur.fetchone()[0].split(', ')
    return f'(s:{ " or s:".join(set_ for set_ in sets)})'