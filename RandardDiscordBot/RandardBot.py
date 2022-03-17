import disnake
from disnake.ext import commands


class RandardBot(commands.Bot):
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
