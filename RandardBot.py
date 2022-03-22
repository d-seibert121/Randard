import configparser
import datetime
import os
from urllib.parse import urlparse

import disnake
import mtgsdk
import psycopg2
import psycopg2.extras
import psycopg2.extensions
import psycopg2.sql
from disnake.ext import commands

from APIutils import Set_name, Set_code
from format_chooser import generate_format


class UserNotRegisteredError(psycopg2.DatabaseError):
    pass


class RandardBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__database_url = os.environ.get("DATABASE_URL", None)
        if self.__database_url:
            result = urlparse(self.__database_url)
            parsed_config = {'host': result.hostname, 'database': result.path[1:], 'user': result.username, 'password': result.password, 'port': result.port}
            self.config = {'bot': {'token': os.environ["RANDARD_BOT_TOKEN"]}, 'postgresql': parsed_config}
        else:
            self.config = configparser.ConfigParser()
            self.config.read('database.ini')
        print(dict(self.config))

    async def on_ready(self):
        today = datetime.date.today()
        for guild in self.guilds:
            await self._setup(guild, date=today)
        print("All guilds set up and good to go!")

    async def on_guild_join(self, guild: disnake.Guild):
        print(f"joined {guild.name} with id {guild.id}")
        await self._setup(guild, date=datetime.date.today())

    async def _setup(self, guild: disnake.Guild, date: datetime.date):
        """Ensures that all necessary database tables exist. If they don't exist, create them with the correct fields.
        Also populates seasons with an initial, 0th season if necessary, and posts that to the announcements channel.
        Also ensures that the Players role and announcements channel exist, bot will create the match-results channel when the first game is completed.
        """
        schema_name = f"server_{guild.id}"
        player_role = await self.get_player_role(guild)
        announcements_channel = await self.get_announcements_channel(guild)
        with self._database_for(guild) as con:
            cur = con.cursor()

            # Makes sure the server has a schema
            create_server_schema_sql = psycopg2.sql.SQL("CREATE SCHEMA IF NOT EXISTS {}")
            cur.execute(create_server_schema_sql.format(psycopg2.sql.Identifier(schema_name)))

            # find what tables the schema has, so we can create players and seasons if necessary
            cur.execute(f"SELECT * FROM pg_tables WHERE schemaname=%s", [f"server_{guild.id}"])
            tables: list[psycopg2.extras.DictRow] = cur.fetchall()
            table_names: list[str] = [table['name'] for table in tables]

            if 'players' not in table_names:
                # only creates the table, it must be populated by players using the /register command
                table_name = psycopg2.sql.Identifier(schema_name, "players")
                players_create_sql = psycopg2.sql.SQL("CREATE TABLE {}(discord_id TEXT UNIQUE, name TEXT, discriminator TEXT, registration_date TEXT, rating INT DEFAULT 1000, last_game TEXT DEFAULT null)")
                cur.execute(players_create_sql.format(table_name))

            if 'seasons' not in table_names:
                # creates the table, and populates it with an initial season
                table_name = psycopg2.sql.Identifier(schema_name, "seasons")
                season_create_sql = psycopg2.sql.SQL("CREATE TABLE {}(season_number INTEGER PRIMARY KEY, month TEXT, year INT, set_names TEXT, set_codes TEXT, winner TEXT DEFAULT null)")
                cur.execute(season_create_sql.format(table_name))
                new_format = generate_format()
                set_codes = self.codes_string(new_format)
                set_names = self.names_string(new_format)
                # this INSERT INTO can't just defer to self.store_format because it sets the season_number to 0
                insert_zeroth_season_sql = psycopg2.sql.SQL("INSERT INTO {}(season_number, month, year, set_names, set_codes) VALUES (0, %s, %s, %s, %s)")
                cur.execute(insert_zeroth_season_sql.format(table_name), [f'{date:%B}', date.year, set_names, set_codes])

                # announces the initial season, telling players what sets are legal
                announcement_header = f"Attention {player_role.mention}s! Welcome to the preliminary season of Randard! Your legal sets for this season are:\n"
                format_message = '\n'.join(f'    {set_.name}' for set_ in new_format)
                signoff = '\nHappy Deckbuilding!'
                full_message = announcement_header + format_message + signoff
                print(guild.name)  # debug
                print(full_message)  # debug
                await announcements_channel.send(full_message)

    def _database_for(self, guild: disnake.Guild) -> psycopg2.extensions.cursor:
        """Returns the filepath to the server-specific database for the given server.
        """
        db_info = self.config['postgresql']
        con = psycopg2.connect(dbname=db_info['database'], user=db_info['user'], password=db_info['password'],
                               host=db_info['host'], port=db_info['port'], cursor_factory=psycopg2.extras.DictCursor)
        cur = con.cursor()
        cur.execute("SET SCHEMA %s", [f"server_{guild.id}"])
        return con

    @staticmethod
    async def get_player_role(guild: disnake.Guild) -> disnake.Role:
        for role in guild.roles:
            if role.name.lower() == 'player':
                return role
        return await guild.create_role(name="Player", colour=disnake.Colour.random(), hoist=True, mentionable=True)

    async def get_bot_role(self, guild: disnake.Guild) -> disnake.Role:
        if guild.self_role:
            return guild.self_role
        member_me = await guild.getch_member(self.user.id)
        for role in member_me.roles:
            if role.name == "Randard":
                return role
        return guild.default_role

    async def get_match_results_channel(self, guild: disnake.Guild) -> disnake.TextChannel:
        bot_role = await self.get_bot_role(guild)
        for channel in guild.channels:
            if channel.name.lower() == 'match-results':
                return channel
        permissions = {role: disnake.PermissionOverwrite(send_messages=False) for role in guild.roles}
        permissions[bot_role] = disnake.PermissionOverwrite(send_messages=True)
        return await guild.create_text_channel('match-results', topic='The bot posts verified game results here',
                                               overwrites=permissions)

    async def get_announcements_channel(self, guild: disnake.Guild) -> disnake.TextChannel:
        bot_role = await self.get_bot_role(guild)
        for channel in guild.channels:
            if channel.name.lower() == 'announcements':
                return channel
        permissions = {role: disnake.PermissionOverwrite(send_messages=False) for role in guild.roles}
        permissions[bot_role] = disnake.PermissionOverwrite(send_messages=True)
        return await guild.create_text_channel('Announcements',
                                               topic='Season standings and new season announcements are posted here by the bot.',
                                               overwrites=permissions)

    def register_player(self, member: disnake.Member) -> bool | psycopg2.extras.DictRow:
        with self._database_for(member.guild) as con:
            cur = con.cursor()
            try:
                cur.execute(
                    "INSERT INTO players(discord_id, name, discriminator, registration_date) VALUES (%s, %s, %s, %s)",
                    [member.id, member.name, member.discriminator, str(datetime.date.today())])
            except psycopg2.IntegrityError:
                cur.execute("SELECT * FROM players WHERE discord_id = %s", [member.id])
                return cur.fetchone()
        return True

    def store_format(self, mtg_format: list[mtgsdk.Set], guild: disnake.Guild):
        """Stores the given format as the new season of the given guild's database"""
        today = datetime.date.today()
        names = self.names_string(mtg_format)
        codes = self.codes_string(mtg_format)
        with self._database_for(guild) as con:
            cur = con.cursor()
            cur.execute("INSERT INTO seasons(month, year, set_names, set_codes) VALUES (%s, %s, %s, %s)", [f"{today:%B}", today.year, names, codes])

    def update_player_rating(self, player: disnake.Member, new_rating: int):
        """Update's a player's entry in the database with a new rating"""
        with self._database_for(player.guild) as con:
            cur = con.cursor()
            cur.execute("UPDATE players SET rating=%s WHERE discord_id=%s", [new_rating, player.id])
            if cur.rowcount == 0:
                raise UserNotRegisteredError(f"The player {player.name} with id {player.id} is not registered in the database.")

    def _get_player(self, player: disnake.Member) -> psycopg2.extras.DictRow:
        """Fetches a player row from the bots database"""
        with self._database_for(player.guild) as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM players WHERE discord_id=%s", [player.id])
            player_row = cur.fetchone()
            if player_row:
                return player_row
            raise UserNotRegisteredError(f"The player {player.name} with id {player.id} is not registered in the database.")

    def get_player_rating(self, player):
        return self._get_player(player)['rating']

    def get_leaderboard(self, guild: disnake.Guild) -> list[psycopg2.extras.DictRow]:
        """Gets the top 10 players from the current season.
        Each element of the returned list is a sqlite3.Row object representing a player, with discord_id and rating keys.
        Players are returned in standing order, with the champion at index 0, runner-up at index 1, etc.
        """
        with self._database_for(guild) as con:
            cur = con.cursor()
            cur.execute("SELECT discord_id, rating FROM players ORDER BY rating DESC")
            leaderboard = cur.fetchmany(10)
        return leaderboard

    def store_leaderboard(self, guild: disnake.Guild) -> list[psycopg2.extras.DictRow]:
        """Creates a new table in the database storing the leaderboard for a particular season, storing the discord id and rating of the top 10 players
        Returns a list of the 10 players, as they exist in the players table, in order from 1st place to 10th"""
        with self._database_for(guild) as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM seasons ORDER BY CAST(season_number AS REAL) DESC")
            completed_season = cur.fetchone()
            leaderboard_table_name = f"leaderboard_{completed_season['month']}_{completed_season['year']}"
            cur.execute(f"CREATE TABLE IF NOT EXISTS {leaderboard_table_name}(discord_id, rating, name) ")
            cur.execute(f"DELETE FROM {leaderboard_table_name}")
            cur.execute("SELECT discord_id, rating, name FROM players ORDER BY rating DESC")
            leaderboard = cur.fetchmany(10)
            cur.executemany(f"INSERT INTO {leaderboard_table_name}(discord_id, rating, name) VALUES (%s, %s, %s)",
                            [(row['discord_id'], row['rating'], row['name']) for row in leaderboard])
            return leaderboard

    def clear_ratings(self, guild: disnake.Guild):
        with self._database_for(guild) as con:
            cur = con.cursor()
            cur.execute("UPDATE players SET rating=1000")

    def get_current_season(self, guild: disnake.Guild) -> psycopg2.extras.DictRow:
        with self._database_for(guild) as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM seasons ORDER BY CAST(season_number AS REAL) DESC")
            return cur.fetchone()

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
            sets = self.get_legal_set_codes(guild)
        return f'(s:{ " or s:".join(set_ for set_ in sets)})'
