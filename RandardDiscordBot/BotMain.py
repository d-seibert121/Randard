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


def handle_confirmed_game(user: disnake.Member, opponent: disnake.Member, games_won: int, games_lost: int, ties: int = 0):
    k = 40  # ELO constant. Higher k means scores change faster, 40 is rather high

    total_games = games_won + games_lost + ties
    games_won += ties / 2
    games_lost += ties / 2

    with sqlite3.connect(DB_LOC) as con:
        cur = con.execute("SELECT rating FROM players WHERE discord_id=?", [user.id])
        user_rating = cur.fetchone()
        if user_rating is None:
            raise UserNotRegisteredError("User is not registered")
        else:
            user_rating = user_rating[0]
        cur = con.execute("SELECT rating FROM players WHERE discord_id=?", [opponent.id])
        opponent_rating = cur.fetchone()
        if opponent_rating is None:
            raise UserNotRegisteredError("Opponent is not registered")
        else:
            opponent_rating = opponent_rating[0]

        user_expected_score = total_games/(1+10**((opponent_rating-user_rating)/400))
        opponent_expected_score = total_games-user_expected_score

        user_rating_change = k*(games_won - user_expected_score)
        opponent_rating_change = k*(games_lost - opponent_expected_score)

        user_rating += user_rating_change
        opponent_rating += opponent_rating_change

        con.executemany("UPDATE players SET rating=:rating WHERE discord_id=:id",
                        [{'id': user.id, 'rating': user_rating}, {'id': opponent.id, 'rating': opponent_rating}])


class GameCommandView(disnake.ui.View):
    def __init__(self, user: disnake.Member, opponent: disnake.Member, user_score: int, opponent_score: int):
        super().__init__()
        self.user = user
        self.opponent = opponent
        self.user_score = user_score
        self.opponent_score = opponent_score
        self.rejected = False
        self.confirmed = False

    __slots__ = ('user', 'opponent', 'user_score', 'opponent_score', 'rejected', 'confirmed')

    @disnake.ui.button(label="Confirm", style=disnake.ButtonStyle.green)
    async def confirm(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if self.rejected:
            await inter.send("This game was rejected by the opponent. Please resubmit the game")
            return
        if self.confirmed:
            await inter.send("This game was already confirmed and tallied", ephemeral=True)
            return
        if inter.user == self.opponent:
            await inter.send("Registering the game!", ephemeral=True)
            try:
                handle_confirmed_game(self.user, self.opponent, self.user_score, self.opponent_score)
            except UserNotRegisteredError as err:
                await inter.send(err.args[0])
            else:
                self.confirmed = True
                self.stop()
            return
        else:
            await inter.send("Hey, that button wasn't for you. Only the game's listed opponent should click the button", ephemeral=True)

    @disnake.ui.button(label="Cancel", style=disnake.ButtonStyle.red)
    async def cancel(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if self.confirmed or self.rejected:
            await inter.send('This game is already closed', ephemeral=True)
        elif inter.user == self.opponent:
            await inter.send("I'm sorry to hear there's a problem with this submission. \n"
                             "Either you or your opponent should resubmit the game once you agree on the results")
            self.rejected = True
            self.stop()
        elif inter.user == self.user:
            await inter.send("Alright, game cancelled", ephemeral=True)
        else:
            await inter.send("Hey, that button wasn't for you. Only the game's listed opponent should click the button", ephemeral=True)


@bot.slash_command(description="Record a game!")
async def game(inter: disnake.AppCommandInteraction, opponent: disnake.Member, submitter_score: int, opponent_score: int, ties: int = 0):
    # TODO Make the buttons only display to the opponent/ DM the buttons
    # TODO Update the command invocation when the opponent responds
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
    view = GameCommandView(inter.user, opponent, submitter_score, opponent_score)
    await inter.send(f"Results: {inter.user.mention} won {submitter_score} games, {opponent.mention} won {opponent_score} games, and there were {ties} ties.\n"
                     f"Your opponent needs to confirm before I record these results.", view=view)


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
