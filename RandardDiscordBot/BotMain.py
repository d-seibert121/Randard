import dataclasses
import Randard
from private_info import TOKEN, TEST_GUILDS, DB_LOC
import disnake
from disnake.ext import commands
import sqlite3
import datetime
from Randard.APIutils import Set_code, Set_name

# TODO add descriptions for all command arguments
bot = commands.Bot(command_prefix="$", test_guilds=TEST_GUILDS)


class UserNotRegisteredError(LookupError):
    pass


async def get_player_role(guild: disnake.Guild):
    for role in guild.roles:
        if role.name.lower() == 'player':
            return role
    return guild.create_role(name="player", colour=disnake.Colour.random(), hoist=True, mentionable=True)


async def get_match_results_channel(guild: disnake.Guild) -> disnake.TextChannel:
    for channel in guild.channels:
        if channel.name.lower() == 'match-results':
            return channel
    permissions = {role: disnake.PermissionOverwrite(send_messages=False) for role in guild.roles}
    permissions[bot.user] = disnake.PermissionOverwrite(send_messages=True)
    return await guild.create_text_channel('match-results', topic='The bot posts verified game results here', overwrites=permissions)


def get_legal_set_names_and_codes(database=DB_LOC) -> tuple[list[Set_name], list[Set_code]]:
    with sqlite3.connect(database) as con:
        cur = con.execute("SELECT set_names, set_codes FROM seasons ORDER BY CAST(season_number AS REAL) DESC")
        legal_set_names_string, legal_sets_string = cur.fetchone()
        legal_sets = legal_sets_string.split(', ')
        legal_set_names = legal_set_names_string.split(', ')
    return legal_set_names, legal_sets


def get_legal_set_names(database=DB_LOC) -> list[Set_name]:
    return get_legal_set_names_and_codes(database)[0]


def get_legal_set_codes(database=DB_LOC) -> list[Set_code]:
    return get_legal_set_names_and_codes(database)[1]


@bot.event
async def on_ready():
    legal_set_names, legal_sets = get_legal_set_names_and_codes()
    print(f'I have logged into {[guild.name for guild in bot.guilds]}')
    print(f'Currently legal sets are:')
    print('\n'.join(set_ for set_ in legal_set_names))
    print(f'And the codes are {legal_sets}')
    print(f'My owner is {bot.owner.id}')


@bot.slash_command(name='format', description="Displays the current legal sets")
async def format_command(inter: disnake.AppCommandInteraction):
    legal_set_names = get_legal_set_names()
    await inter.response.send_message("The current Randard sets are:\n" + '\n'.join(set_ for set_ in legal_set_names))


@bot.slash_command(description="Gives you a search string for scryfall.com to only show currently legal cards")
async def scryfall(inter: disnake.AppCommandInteraction):
    raw_search_string = Randard.APIutils.scryfall_search()
    url = f'https://scryfall.com/search?q={raw_search_string.replace(" ", "+")}'
    await inter.response.send_message(url)


@bot.slash_command(description="Send me a .txt file of your decklist, and I'll verify that it's currently legal for Randard.")
async def verify(inter: disnake.AppCommandInteraction,
                 decklist_file: disnake.Attachment = commands.Param(description="A .txt file containing the decklist. Each line should either be empty, a ")):
    await inter.response.defer(with_message=True)
    f = await decklist_file.read()
    try:
        f = f.decode()
    except UnicodeError:
        await inter.send("Oops, I can't read that. Please send me a .txt file, with utf-8 encoding. Try copying your decklist into Notepad and saving it from there.")
        return
    set_codes = get_legal_set_codes()
    try:
        decklist = Randard.decklist_parser(f, string=True)
    except Randard.DecklistError as err:
        await inter.send(err.args)
        return

    verification = Randard.verify_decklist(*decklist, legal_sets=set_codes)
    if verification is True:
        await inter.send("Verified!")
    else:
        await inter.send("There were some problems with your list:\n" + '\n'.join(verification))


@dataclasses.dataclass
class PendingGame:
    submitter: disnake.Member
    opponent: disnake.Member
    submitter_games_won: int
    opponent_games_won: int
    ties: int = 0
    closed: bool = False

    @property
    def summary_string(self):
        ties_substring = f', {self.ties} tie{"s" * (self.ties > 1)}' if self.ties else ''
        return f"Results: {self.submitter.name} {self.submitter_games_won}, {self.opponent.name} {self.opponent_games_won}{ties_substring}"

    @property
    def total_games(self):
        return self.submitter_games_won + self.opponent_games_won + self.ties


class GameClosedError(ValueError):
    pass


def handle_confirmed_game(game: PendingGame):
    if game.closed:
        raise GameClosedError("That game is closed")

    k = 40  # ELO constant. Higher k means scores change faster, 40 is rather high

    total_games = game.total_games
    games_won = game.submitter_games_won + (game.ties / 2)
    games_lost = game.opponent_games_won + (game.ties / 2)

    with sqlite3.connect(DB_LOC) as con:
        cur = con.execute("SELECT rating FROM players WHERE discord_id=?", [game.submitter.id])
        submitter_rating = cur.fetchone()
        if submitter_rating is None:
            raise UserNotRegisteredError("User is not registered")
        else:
            submitter_rating = submitter_rating[0]
        cur = con.execute("SELECT rating FROM players WHERE discord_id=?", [game.opponent.id])
        opponent_rating = cur.fetchone()
        if opponent_rating is None:
            raise UserNotRegisteredError("Opponent is not registered")
        else:
            opponent_rating = opponent_rating[0]

        submitter_expected_score = total_games/(1+10**((opponent_rating-submitter_rating)/400))
        opponent_expected_score = total_games-submitter_expected_score

        submitter_rating_change = k*(games_won - submitter_expected_score)
        opponent_rating_change = k*(games_lost - opponent_expected_score)

        submitter_rating += submitter_rating_change
        opponent_rating += opponent_rating_change

        con.executemany("UPDATE players SET rating=:rating WHERE discord_id=:id",
                        [{'id': game.submitter.id, 'rating': submitter_rating}, {'id': game.opponent.id, 'rating': opponent_rating}])


class GameCommandViewOpponent(disnake.ui.View):
    def __init__(self, game_submission: PendingGame):
        super().__init__()
        self.game = game_submission

    __slots__ = ('confirm', 'cancel', 'game')

    @disnake.ui.button(label="Confirm", style=disnake.ButtonStyle.green)
    async def confirm(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        try:
            handle_confirmed_game(self.game)
        except GameClosedError:
            await inter.send("That game is closed, either because you already accepted it, or it was canceled by the submitter.")
            return
        results_channel = await get_match_results_channel(self.game.submitter.guild)
        await results_channel.send(f'A game has been completed!\n {self.game.summary_string}')
        self.game.closed = True
        self.stop()

    @disnake.ui.button(label="Cancel", style=disnake.ButtonStyle.red)
    async def cancel(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        self.game.closed = True
        self.stop()
        await inter.send("This game is now closed, without being recorded.")


class GameCommandViewSubmitter(disnake.ui.View):
    def __init__(self, game_submission: PendingGame):
        super().__init__()
        self.game = game_submission

    __slots__ = ('cancel', 'game')

    @disnake.ui.button(label="cancel", style=disnake.ButtonStyle.red)
    async def cancel(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        self.game.closed = True
        self.stop()
        await inter.send("This game is now closed, without being recorded.")


@bot.slash_command(name='game', description="Record a game!")
async def game_command(inter: disnake.AppCommandInteraction, opponent: disnake.Member, submitter_score: int, opponent_score: int, ties: int = 0):
    # TODO Make the buttons only display to the opponent/ DM the buttons
    # TODO Update the command invocation when the opponent responds

    # check roles as a quick catch for unregistered players
    player_role = await get_player_role(inter.guild)
    if player_role not in inter.user.roles:
        await inter.send("You must /register before submitting a game.", ephemeral=True)
        return
    if player_role not in opponent.roles:
        await inter.send("Your opponent must /register before submitting this game.", ephemeral=True)
        return
    if opponent == inter.user:
        await inter.send("Despite the meme, you can't play yourself", ephemeral=True)
        return

    game_submission = PendingGame(inter.user, opponent, submitter_score, opponent_score, ties)

    submitter_view = GameCommandViewSubmitter(game_submission)
    opponent_view = GameCommandViewOpponent(game_submission)

    await opponent.send(f"A game has been submitted listing you as the opponent. {game_submission.summary_string}", view=opponent_view)
    await inter.send("Your opponent has been messaged to verify this game. If you would like to cancel, click this button.", view=submitter_view, ephemeral=True)


@bot.slash_command(description="Registers you to the Randard league")
async def register(inter: disnake.AppCommandInteraction):
    with sqlite3.connect(DB_LOC) as con:
        try:
            con.execute("INSERT INTO players(discord_id, name, discriminator, registration_date) VALUES (?, ?, ?, ?)",
                        [inter.user.id, inter.user.name, inter.user.discriminator, str(datetime.date.today())])
        except sqlite3.IntegrityError:
            print(inter.user.id, type(inter.user.id))
            cur = con.execute("SELECT registration_date FROM players WHERE discord_id = ?", [inter.user.id])
            date = cur.fetchone()[0]
            datetime_date = datetime.date.fromisoformat(date)
            await inter.send(f"Looks like you registered back on {datetime_date:%x}")
    player_role = await get_player_role(inter.guild)
    await inter.user.add_roles(player_role)
    await inter.send("You're all registered!", ephemeral=True)


@bot.slash_command(description="Lets you check your current rating. A rating of 1000 is average")
async def rating(inter: disnake.AppCommandInteraction):
    with sqlite3.connect(DB_LOC) as con:
        try:
            cur = con.execute("SELECT rating FROM players WHERE discord_id = ?", [inter.user.id])
            player_rating = cur.fetchall()[0][0]
        except IndexError:
            await inter.send("Looks like you haven't registered yet. Use the /register command to register")
            return
    await inter.send(f"Your current rating is {player_rating}")


def quarterly_update():
    """This function will run every 3 months as a task attached to the bot.
    It performs monthly update tasks, mostly associated with logging the preceding season, posting results, and launching the new season."""
    current_date = datetime.date.today()
    with sqlite3.connect(DB_LOC) as con:
        # TODO backup player database and old sets
        # TODO reset all player ratings
        # TODO generate new format
        # TODO publish new format and leaderboard from the ending season
        pass


bot.run(TOKEN)
