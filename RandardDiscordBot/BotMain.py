from private_info import TOKEN, TEST_GUILDS, SET_FILE_LOC
import disnake
from disnake.ext import commands
import Randard
import json

bot = commands.Bot(command_prefix="$", test_guilds=TEST_GUILDS)

with open(SET_FILE_LOC, 'r') as f:
    set_info = json.load(f)
legal_sets = set_info["codes"]
legal_set_names = set_info["names"]


@bot.event
async def on_ready():
    print(f'I have logged into {[guild.name for guild in bot.guilds]}')
    print(f'Currently legal sets are:')
    print('\n'.join(set_ for set_ in legal_set_names))
    print(f'And the codes are {legal_sets}')
    bot.clear()


@bot.slash_command(name='format', description="Displays the current legal sets")
async def format_command(inter: disnake.AppCommandInteraction):
    await inter.response.send_message("The current Randard sets are:\n" + '\n'.join(set_ for set_ in legal_set_names))


@bot.slash_command()
async def generate(inter: disnake.AppCommandInteraction):
    if inter.user == bot.owner:
        await inter.response.send_message("Sure thing, boss!")
    else:
        await inter.response.send_message("Um, I don't think you're allowed to do that...")


@bot.slash_command(description="Gives you a search string for scryfall.com to only show currently legal cards")
async def scryfall(inter: disnake.AppCommandInteraction):
    await inter.response.send_message(Randard.scryfall_search())


@bot.slash_command(description="Verifies that your decklist is currently legal for Randard.")
async def verify(inter: disnake.AppCommandInteraction, attachment: disnake.Attachment):
    print(attachment, attachment.description, attachment.ephemeral, attachment.filename)
    f = await attachment.read()
    try:
        f = f.decode()
    except UnicodeError:
        await inter.send("Oops, I can't read that. Please send me a .txt file, with utf-8 encoding. Try copying your decklist into Notepad and saving it from there.")
    print(f, type(f))
    decklist = Randard.decklist_parser(f, string=True)
    verification = Randard.verify_decklist(*decklist)
    if verification is True:
        await inter.send("Verified!")  # stand-in while I get the logic worked out
    else:
        await inter.send("There were some problems with your list:\n" + '\n'.join(verification))
bot.run(TOKEN)
