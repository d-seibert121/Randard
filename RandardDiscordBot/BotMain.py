from private_info import TOKEN, TEST_GUILDS
from disnake.ext import commands
from disnake import AppCommandInteraction
from private_info import SET_FILE_LOC
from Randard import scryfall_search

bot = commands.Bot(command_prefix="$", test_guilds=TEST_GUILDS)

@bot.event
async def on_ready():
    print(f'I have logged into {[guild.name for guild in bot.guilds]}')


@bot.slash_command(name='format', description="Displays the current legal sets")
async def format_command(inter: AppCommandInteraction):
    with open(SET_FILE_LOC, 'r') as f:
        await inter.response.send_message("The current Randard sets are:\n" + '\n'.join(line.strip().strip('"') for line in f))


@bot.slash_command()
async def generate(inter: AppCommandInteraction):
    if inter.user == bot.owner:
        await inter.response.send_message("Sure thing, boss!")
    else:
        await inter.response.send_message("Um, I don't think you're allowed to do that...")


@bot.slash_command(description="Gives you a search string for scryfall.com to only show currently legal cards")
async def scryfall(inter: AppCommandInteraction):
    await inter.response.send_message(scryfall_search())


bot.run(TOKEN)
