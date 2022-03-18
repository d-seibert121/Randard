import datetime
import sqlite3

import disnake
import mtgsdk
from disnake.ext import commands

from RandardDiscordBot.APIutils import Set_name, Set_code
from RandardDiscordBot.private_info import DB_PATH
from format_chooser import generate_format


class UserNotRegisteredError(sqlite3.DatabaseError):
    pass


class RandardBot(commands.Bot):
    def on_ready(self):
        today = datetime.date.today()
        for guild in self.guilds:
            await self._setup(guild, date=today)
        print("All guild set up and good to go!")

    async def _setup(self, guild: disnake.Guild, date: datetime.date):
        """Ensures that all necessary database tables exist. If they don't exist, create them with the correct fields.
        Also populates seasons with an initial, 0th season if necessary, and posts that to the announcements channel.
        Also ensures that the Players role and announcements channel exist, bot will create the match-results channel when the first game is completed.
        """
        db_path = self._database_for(guild)
        with sqlite3.connect(db_path) as con:
            con.row_factory = sqlite3.Row
            cur = con.execute("SELECT * FROM sqlite_schema WHERE type='table'")
            tables: list[sqlite3.Row] = cur.fetchall()
            table_names: list[str] = [table['name'] for table in tables]
            if 'players' not in table_names:
                # only creates the table, it must be populated by players using the /register command
                con.execute("CREATE TABLE players(discord_id TEXT UNIQUE, name TEXT, discriminator TEXT, registration_date TEXT, rating INT DEFAULT 1000, last_game TEXT DEFAULT null)")
            if 'seasons' not in table_names:
                # creates the table, and populates it with an initial season
                con.execute("CREATE TABLE seasons(season_number INTEGER PRIMARY KEY, month TEXT, year INT, set_names TEXT, set_codes TEXT, winner TEXT DEFAULT null)")
                new_format = generate_format()
                set_codes = self.codes_string(new_format)
                set_names = self.names_string(new_format)
                # this INSERT INTO can't just defer to self.store_format because it sets the season_number to 0
                con.execute("INSERT INTO seasons(season_number, month, year, set_names, set_codes) VALUES (0, ?, ?, ?, ?)", [f'{date:%B}', date.year, set_codes, set_names])
                player_role = await self.get_player_role(guild)
                announcements_channel = await self.get_announcements_channel(guild)
                announcement_header = f"Attention {player_role.mention}s! Welcome to the preliminary season of Randard! Your legal sets for this season are:\n"
                format_message = '\n'.join(f'    {set_.name}' for set_ in new_format)
                signoff = '\nHappy Deckbuilding!'
                await announcements_channel.send(announcement_header + format_message + signoff)

    @staticmethod
    def _database_for(guild: disnake.Guild) -> str:
        """Returns the filepath to the server-specific database for the given server.
        """
        return f"{DB_PATH}Randard_{guild.id}.db"

    @staticmethod
    async def get_player_role(guild: disnake.Guild) -> disnake.Role:
        for role in guild.roles:
            if role.name.lower() == 'player':
                return role
        return await guild.create_role(name="Player", colour=disnake.Colour.random(), hoist=True, mentionable=True)

    async def get_match_results_channel(self, guild: disnake.Guild) -> disnake.TextChannel:
        for channel in guild.channels:
            if channel.name.lower() == 'match-results':
                return channel
        permissions = {role: disnake.PermissionOverwrite(send_messages=False) for role in guild.roles}
        permissions[self.user] = disnake.PermissionOverwrite(send_messages=True)
        return await guild.create_text_channel('match-results', topic='The bot posts verified game results here',
                                               overwrites=permissions)

    async def get_announcements_channel(self, guild: disnake.Guild) -> disnake.TextChannel:
        for channel in guild.channels:
            if channel.name.lower() == 'announcements':
                return channel
        permissions = {role: disnake.PermissionOverwrite(send_messages=False) for role in guild.roles}
        permissions[self.user] = disnake.PermissionOverwrite(send_messages=True)
        return await guild.create_text_channel('Announcements',
                                               topic='Season standings and new season announcements are posted here by the bot.',
                                               overwrites=permissions)

    def register_player(self, member: disnake.Member) -> bool | sqlite3.Row:
        datetime_date: datetime.date | None = None
        with sqlite3.connect(self._database_for(member.guild)) as con:
            con.row_factory = sqlite3.Row
            try:
                con.execute(
                    "INSERT INTO players(discord_id, name, discriminator, registration_date) VALUES (?, ?, ?, ?)",
                    [member.id, member.name, member.discriminator, str(datetime.date.today())])
            except sqlite3.IntegrityError:
                cur = con.execute("SELECT * FROM players WHERE discord_id = ?", [member.id])
                return cur.fetchone()
        return True



    def store_format(self, mtg_format: list[mtgsdk.Set], guild: disnake.Guild):
        """Stores the given format as the new season of the given guild's database"""
        today = datetime.date.today()
        names = self.names_string(mtg_format)
        codes = self.codes_string(mtg_format)
        with sqlite3.connect(self._database_for(guild)) as con:
            con.execute("INSERT INTO seasons(month, year, set_names, set_codes) VALUES (?, ?, ?, ?)", [f"{today:%B}", today.year, names, codes])

    def update_player_rating(self, player: disnake.Member, new_rating: int):
        """Update's a player's entry in the database with a new rating"""
        with sqlite3.connect(self._database_for(player.guild)) as con:
            cur = con.execute("UPDATE players SET rating=? WHERE discord_id=?", [player.id])
            if cur.rowcount == 0:
                raise UserNotRegisteredError(f"The player {player.name} with id {player.id} is not registered in the database.")

    def _get_player(self, player: disnake.Member) -> sqlite3.Row:
        """Fetches a player row from the bots database"""
        with sqlite3.connect(self._database_for(player.guild)) as con:
            con.row_factory = sqlite3.Row
            player_row = con.execute("SELECT * FROM players WHERE discord_id=?", [player.id]).fetchone()
            if player_row:
                return player_row
            raise UserNotRegisteredError(f"The player {player.name} with id {player.id} is not registered in the database.")

    def get_player_rating(self, player):
        return self._get_player(player)['rating']

    def get_leaderboard(self, guild: disnake.Guild) -> list[sqlite3.Row]:
        """Gets the top 10 players from the current season.
        Each element of the returned list is a sqlite3.Row object representing a player, with discord_id and rating keys.
        Players are returned in standing order, with the champion at index 0, runner-up at index 1, etc.
        """
        with sqlite3.connect(self._database_for(guild)) as con:
            con.row_factory = sqlite3.Row
            cur = con.execute("SELECT discord_id, rating FROM players ORDER BY rating DESC")
            leaderboard = cur.fetchmany(10)
        return leaderboard

    def store_leaderboard(self, guild: disnake.Guild) -> list[sqlite3.Row]:
        """Creates a new table in the database storing the leaderboard for a particular season, storing the discord id and rating of the top 10 players
        Returns a list of the 10 players, as they exist in the players table, in order from 1st place to 10th"""
        with sqlite3.connect(self._database_for(guild)) as con:
            con.row_factory = sqlite3.Row
            completed_season = con.execute("SELECT * FROM seasons ORDER BY CAST(season_number AS REAL) DESC").fetchone()
            leaderboard_table_name = f"leaderboard_{completed_season['month']}_{completed_season['year']}"
            con.execute(f"CREATE TABLE IF NOT EXISTS {leaderboard_table_name}(discord_id, rating, name) ")
            con.execute(f"DELETE FROM {leaderboard_table_name}")
            leaderboard = con.execute("SELECT discord_id, rating, name FROM players ORDER BY rating DESC").fetchmany(10)
            con.executemany(f"INSERT INTO {leaderboard_table_name}(discord_id, rating, name) VALUES (?, ?, ?)",
                            [(row['discord_id'], row['rating'], row['name']) for row in leaderboard])
            return leaderboard

    def clear_ratings(self, guild: disnake.Guild):
        with sqlite3.connect(self._database_for(guild)) as con:
            con.execute("UPDATE players SET rating=1000")

    def get_current_season(self, guild: disnake.Guild) -> sqlite3.Row:
        with sqlite3.connect(self._database_for(guild)) as con:
            con.row_factory = sqlite3.Row
            return con.execute("SELECT * FROM seasons ORDER BY CAST(season_number AS REAL) DESC").fetchone()

    def get_legal_set_names(self, guild: disnake.Guild) -> list[Set_name]:
        return self.get_current_season(guild)['set_names'].split(', ')

    def get_legal_set_codes(self, guild: disnake.Guild) -> list[Set_code]:
        return self.get_current_season(guild)['set_codes'].split(', ')

    def get_season_number(self, guild: disnake.Guild) -> int | str:
        return self.get_current_season(guild)['season_number']

    @staticmethod
    def codes_string(mtg_format: list[mtgsdk.Set]) -> str:
        """Returns a string of comma delimited set codes for the given list of Sets"""
        return ', '.join(set_.code for set_ in mtg_format)

    @staticmethod
    def names_string(mtg_format: list[mtgsdk.Set]) -> str:
        """Returns a string of comma delimited set names for the given list of Sets"""
        return ', '.join(set_.name for set_ in mtg_format)

    def scryfall_search(self, guild: disnake.Guild, sets=None):
        if sets is None:
            sets = self.get_current_season(guild)
        return f'(s:{ " or s:".join(set_ for set_ in sets)})'
