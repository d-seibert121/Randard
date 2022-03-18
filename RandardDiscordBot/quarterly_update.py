import dataclasses
import datetime

import disnake
from disnake.ext import commands, tasks

from RandardBot import RandardBot
from format_chooser import generate_format


@dataclasses.dataclass
class LeaderboardEntry:
    user: disnake.Member
    rating: int


class RandardMaintenanceCog(commands.Cog):
    def __init__(self, bot):
        self.bot: RandardBot = bot
        self.update_loop.start()

    def cog_unload(self):
        self.update_loop.cancel()

    @tasks.loop(time=datetime.time(hour=10))
    async def update_loop(self):
        today = datetime.date.today()
        if today.day == 1 and today.month % 3 == 1:
            for guild in self.bot.guilds:
                await self.quarterly_update(guild)

    async def quarterly_update(self: RandardBot, guild: disnake.Guild):
        ORDINALS = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th", "10th"]
        old_season_number = self.get_season_number(guild)
        leaderboard = self.store_leaderboard(guild)
        leaderboard = [LeaderboardEntry(await guild.getch_member(player['discord_id']), player['rating']) for player in leaderboard]
        self.clear_ratings(guild)
        new_format = generate_format()
        self.store_format(new_format, guild)
        new_season_number = self.get_season_number(guild)
        player_role = await self.get_player_role(guild)
        announcements_channel = await self.get_announcements_channel(guild)
        header = f"Attention {player_role.mention}s!\nSeason {old_season_number} has ended, and season {new_season_number} is upon us.\nFirst, our leaderboard: \n"
        leaderboard_announcement = '\n'.join(f"{ORDINALS[i]} Place: {player.user.mention:}" for i, player in enumerate(leaderboard))
        new_format_header = '\n\nAnd now, our new format:\n'
        new_format_announcement = '\n'.join(set_.name for set_ in new_format)
        signoff = '\n\nGood luck and happy deckbuilding!'
        compiled_message = header+leaderboard_announcement+new_format_header+new_format_announcement+signoff
        await announcements_channel.send(compiled_message)
