import Randard.APIutils
from private_info import TOKEN, TEST_GUILDS, DB_LOC
import disnake
from disnake.ext import commands
import Randard
import sqlite3
import datetime

bot = commands.Bot(command_prefix="$", test_guilds=TEST_GUILDS)


class UserNotRegisteredError(LookupError):
    pass


def handle_confirmed_game(user: disnake.User, opponent: disnake.User, user_score: int, opponent_score: int, ties: int = 0):
    k = 40  # ELO constant. Higher k means scores change faster, 40 is rather high

    total_games = user_score + opponent_score + ties
    user_score += ties/2
    opponent_score += ties/2

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

        user_rating_change = k*(user_score-user_expected_score)
        opponent_rating_change = k*(opponent_score-opponent_expected_score)

        user_rating += user_rating_change
        opponent_rating += opponent_rating_change

        con.executemany("UPDATE TABLE players SET rating=:rating WHERE discord_id=:id",
                        [{'id': user.id, 'rating': user_rating}, {'id': opponent.id, 'rating': opponent_rating}])


@bot.event
async def on_ready():
    with sqlite3.connect(DB_LOC) as con:
        cur = con.execute("SELECT name, code FROM current_sets")
        legal_set_names, legal_sets = zip(*cur.fetchall())
    print(f'I have logged into {[guild.name for guild in bot.guilds]}')
    print(f'Currently legal sets are:')
    print('\n'.join(set_ for set_ in legal_set_names))
    print(f'And the codes are {legal_sets}')
    print(f'My owner is {bot.owner.id}')


@bot.slash_command(name='format', description="Displays the current legal sets")
async def format_command(inter: disnake.AppCommandInteraction):
    with sqlite3.connect(DB_LOC) as con:
        cur = con.execute("SELECT name FROM current_sets")
        legal_set_names = [item[0] for item in cur.fetchall()]
    await inter.response.send_message("The current Randard sets are:\n" + '\n'.join(set_ for set_ in legal_set_names))


# @bot.slash_command()
# async def generate(inter: disnake.AppCommandInteraction):
#     if inter.user == bot.owner:
#         await inter.response.send_message("Sure thing, boss!")
#     else:
#         await inter.response.send_message("Um, I don't think you're allowed to do that...")

@bot.slash_command(description="Gives you a search string for scryfall.com to only show currently legal cards")
async def scryfall(inter: disnake.AppCommandInteraction):
    await inter.response.send_message(Randard.APIutils.scryfall_search())  # just defers to APIutils


@bot.slash_command(description="Verifies that your decklist is currently legal for Randard.")
async def verify(inter: disnake.AppCommandInteraction, attachment: disnake.Attachment):
    f = await attachment.read()
    try:
        f = f.decode()
    except UnicodeError:
        await inter.send("Oops, I can't read that. Please send me a .txt file, with utf-8 encoding. Try copying your decklist into Notepad and saving it from there.")
        return
    with sqlite3.connect(DB_LOC) as con:
        cur = con.execute("SELECT code FROM current_sets")
        set_codes = [item[0] for item in cur.fetchall()]  # flattening list of 1-tuples to just a list

    decklist = Randard.decklist_parser(f, string=True)
    verification = Randard.verify_decklist(*decklist, legal_sets=set_codes)

    if verification is True:
        await inter.send("Verified!")
    else:
        await inter.send("There were some problems with your list:\n" + '\n'.join(verification))


class GameCommandView(disnake.ui.View):
    def __init__(self, user: disnake.User, opponent: disnake.User, user_score: int, opponent_score: int):
        super().__init__()
        self.user = user
        self.opponent = opponent
        self.user_score = user_score
        self.opponent_score = opponent_score
        self.rejected = False
        self.confirmed = False

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
            await inter.send("I'm sorry to hear there's a problem with this submission. "
                             "Either you or your opponent should resubmit the game once you agree on the results")
            self.rejected = True
            self.stop()
        else:
            await inter.send("Hey, that button wasn't for you. Only the game's listed opponent should click the button", ephemeral=True)


@bot.slash_command(description="Record a game!")
async def game(inter: disnake.AppCommandInteraction, opponent: disnake.User, submitter_score: int, opponent_score: int, ties: int = 0):
    view = GameCommandView(inter.user, opponent, submitter_score, opponent_score)
    await inter.send(f"Results: {inter.user.name} won {submitter_score} games, {opponent.name} won {opponent_score} games, and there were {ties} ties.\n"
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
            date = cur.fetchall()[0][0]  # collapse the list of 1-tuples returned by execute to just the one item I need
            datetime_date = datetime.date.fromisoformat(date)
            await inter.send(f"Looks like you registered back on {datetime_date:%x}")


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

bot.run(TOKEN)
