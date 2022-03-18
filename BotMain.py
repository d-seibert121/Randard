import dataclasses
import datetime

import disnake
from disnake.ext import commands

import quarterly_update
from RandardBot import RandardBot, UserNotRegisteredError
from private_info import TOKEN
import decklist_verification


bot = RandardBot()
bot.add_cog(quarterly_update.RandardMaintenanceCog(bot))


@bot.slash_command(name='format', description="Displays the current legal sets")
async def format_command(inter: disnake.AppCommandInteraction):
    legal_set_names = bot.get_legal_set_names(inter.guild)
    await inter.response.send_message("The current Randard sets are:\n" + '\n'.join(set_ for set_ in legal_set_names))


@bot.slash_command(description="Gives you a search url for scryfall.com that only shows currently legal cards")
async def scryfall(inter: disnake.AppCommandInteraction):
    raw_search_string = bot.scryfall_search(inter.guild)
    url = f'https://scryfall.com/search?q={raw_search_string.replace(" ", "+")}'
    await inter.response.send_message(url)


@bot.slash_command(name="decklist", description="Explains the format to use for decklists for the /verify command")
async def decklist_command(inter: disnake.AppCommandInteraction):
    await inter.send("The decklist format I use is just like the one used by MTGO or Arena.\n"
                     "Each line of the file should be one of three things:\n"
                     "    1. A header that reads either 'Deck', 'Maindeck', 'Side', or 'Sideboard', case insensitive.\n"
                     "    2. A blank line\n"
                     "    3. A number followed by the name of a card (e.g. '4 Llanowar Elves')\n"
                     "If your decklist follows that format, but the /verify command still isn't working, double check your spelling.\n"
                     "All card names must be spelled exactly as they appear on Gatherer, with correct punctuation.\n"
                     "For DFCs, only name the front side.\n"
                     "For Split cards, name both sides separated by // (e.g. '3 Alive // Well')")


@bot.slash_command(description="Send me a .txt file of your decklist, and I'll verify that it's currently legal for Randard.")
async def verify(inter: disnake.AppCommandInteraction,
                 decklist_file: disnake.Attachment = commands.Param(description="A .txt file containing the decklist. Use /decklist for more info on the format to use.")):
    await inter.response.defer(with_message=True)
    f = await decklist_file.read()
    try:
        f = f.decode()
    except UnicodeError:
        await inter.send("Oops, I can't read that. Please send me a .txt file, with utf-8 encoding. Try copying your decklist into Notepad and saving it from there.")
        return
    set_codes = bot.get_legal_set_codes(inter.guild)
    try:
        decklist = decklist_verification.decklist_parser(f, string=True)
    except decklist_verification.DecklistError as err:
        await inter.send(err.args)
        return

    verification = decklist_verification.verify_decklist(*decklist, legal_sets=set_codes)
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
    id: int = 0
    closed: bool = False

    def __post_init__(self):
        self.submitter_interaction: disnake.AppCommandInteraction | None = None
        self.opponent_message: disnake.Message | None = None

    @property
    def summary_string(self):
        ties_substring = f', {self.ties} tie{"s" * (self.ties > 1)}' if self.ties else ''
        return f"Results: {self.submitter.mention} {self.submitter_games_won}, {self.opponent.mention} {self.opponent_games_won}{ties_substring}"

    @property
    def total_games(self):
        return self.submitter_games_won + self.opponent_games_won + self.ties

    def __repr__(self):
        return f"{self.__class__.__name__}(id={self.id}, submitter='{self.submitter.name}', opponent='{self.opponent.name}', submitter_games_won={self.submitter_games_won}, " \
               f"opponent_games_won={self.opponent_games_won}, ties={self.ties}, closed={self.closed})"

    async def cancel(self):
        self.closed = True
        await self.opponent_message.edit(content=f"{self.opponent_message.content}\nThis game has been canceled.", view=None)
        await self.submitter_interaction.edit_original_message(content=f"{self.opponent_message.content}\nThis game has been canceled.", view=None)

    async def submit(self):
        if self.closed:
            raise GameClosedError("That game is closed")

        k = 40  # ELO constant. Higher k means scores change faster, 40 is rather high

        total_games = self.total_games
        games_won = self.submitter_games_won + (self.ties / 2)
        games_lost = self.opponent_games_won + (self.ties / 2)

        submitter_rating = bot.get_player_rating(self.submitter)
        opponent_rating = bot.get_player_rating(self.opponent)

        submitter_expected_score = total_games/(1+10**((opponent_rating-submitter_rating)/400))
        opponent_expected_score = total_games-submitter_expected_score

        submitter_rating_change = k*(games_won - submitter_expected_score)
        opponent_rating_change = k*(games_lost - opponent_expected_score)

        submitter_rating += submitter_rating_change
        opponent_rating += opponent_rating_change

        bot.update_player_rating(self.submitter, submitter_rating)
        bot.update_player_rating(self.opponent, opponent_rating)

        self.closed = True
        await self.opponent_message.edit(content=f"{self.opponent_message.content}\nThis game has been tallied.", view=None)
        await self.submitter_interaction.edit_original_message(content=f"{self.opponent_message.content}\nThis game has been tallied.", view=None)


class GameClosedError(ValueError):
    pass


class GameCommandViewOpponent(disnake.ui.View):
    def __init__(self, game_submission: PendingGame):
        super().__init__()
        self.game = game_submission

    @disnake.ui.button(label="Confirm", style=disnake.ButtonStyle.green)
    async def confirm(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        print(f"game {self.game.id} confirmed by opponent")
        try:
            await self.game.submit()
        except GameClosedError:
            await inter.send("That game is closed, either because you already accepted it or canceled it, or it was canceled by the submitter.")
            return
        except UserNotRegisteredError as err:
            await inter.send(err.args[0])
        await self.game.submitter_interaction.edit_original_message(content=f"{inter.message.content}\nThis game has been submitted.", view=None)
        results_channel = await bot.get_match_results_channel(self.game.submitter.guild)
        await results_channel.send(f'A game has been completed!\n {self.game.summary_string}')

    @disnake.ui.button(label="Cancel", style=disnake.ButtonStyle.red)
    async def cancel(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        print(f"game {self.game.id} canceled by opponent")
        await self.game.cancel()


class GameCommandViewSubmitter(disnake.ui.View):
    def __init__(self, game_submission: PendingGame):
        super().__init__()
        self.game = game_submission

    @disnake.ui.button(label="Cancel", style=disnake.ButtonStyle.red)
    async def cancel(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        print(f"game {self.game.id} canceled by submitter")
        await self.game.cancel()


@bot.slash_command(name='game', description="Record a game!")
async def game_command(inter: disnake.AppCommandInteraction,
                       opponent: disnake.Member = commands.Param(description="The player you played against."),
                       submitter_score: int = commands.Param(description="How many games you won."),
                       opponent_score: int = commands.Param(description="How many games your opponent won."),
                       ties: int = commands.Param(0, description="How many games ended in a tie.")):
    print(f"New game created with id: {inter.id}")
    # check roles as a quick catch for unregistered players
    player_role = await bot.get_player_role(inter.guild)
    if player_role not in inter.user.roles:
        await inter.send("You must /register before submitting a game.", ephemeral=True)
        return
    if player_role not in opponent.roles:
        await inter.send("Your opponent must /register before submitting this game.", ephemeral=True)
        return
    if opponent == inter.user:
        await inter.send("Despite the meme, you can't play yourself", ephemeral=True)
        return

    game_submission = PendingGame(inter.user, opponent, submitter_score, opponent_score, ties, inter.id)
    print(f"the game looks like {game_submission}")
    submitter_view = GameCommandViewSubmitter(game_submission)
    opponent_view = GameCommandViewOpponent(game_submission)

    opponent_message = await opponent.send(f"A game has been submitted listing you as the opponent. {game_submission.summary_string}", view=opponent_view)
    await inter.send("Your opponent has been messaged to verify this game. If you would like to cancel, click this button.", view=submitter_view, ephemeral=True)

    game_submission.submitter_interaction = inter
    game_submission.opponent_message = opponent_message


@bot.slash_command(description="Registers you to the Randard league")
async def register(inter: disnake.AppCommandInteraction):
    registration = bot.register_player(inter.user)
    player_role = await bot.get_player_role(inter.guild)
    await inter.user.add_roles(player_role)
    if registration is True:
        await inter.send("You're all registered!", ephemeral=True)
        return
    registration_date = datetime.date.fromisoformat(registration['registration_date'])
    await inter.send(f"Looks like you registered back on {registration_date:%x}", ephemeral=True)


@bot.slash_command(description="Lets you check your current rating. A rating of 1000 is average")
async def rating(inter: disnake.AppCommandInteraction):
    try:
        rating = bot.get_player_rating(inter.user)
    except UserNotRegisteredError:
        await inter.send("Looks like you haven't registered yet. Use the /register command to register")
        return
    await inter.send(f"{inter.user.mention}, your current rating is {rating}")


# @bot.slash_command()
# async def test_update(inter: disnake.AppCommandInteraction):
#     if inter.user != bot.owner:
#         await inter.send("This is only for testing, and only my owner can use it.", ephemeral=True)
#         return
#     guild = bot.guilds[0]
#     # noinspection PyTypeChecker
#     cog: quarterly_update.RandardMaintenanceCog = bot.get_cog("RandardMaintenanceCog")
#     await cog.quarterly_update(guild)

bot.run(TOKEN)
