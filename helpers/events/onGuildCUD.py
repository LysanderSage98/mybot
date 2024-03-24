import discord

# from helpers.other import db_stuff as db
from helpers.other import utilities as u


def guild_join_handler(bot, guild: discord.Guild):
	u.guild_update(bot, guild)
