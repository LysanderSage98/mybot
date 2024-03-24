import discord
import re

from helpers.other import status_rotation, utilities as u


async def try_set_nickname(bot, guild: discord.Guild, prefix):
	try:
		print(guild, guild.me)
		match = re.search(r"\((.)\)$", guild.me.nick or "")
		if not match:
			pass
		elif match and match.group(1) != prefix:
			pass
		else:
			return
		await guild.me.edit(nick = f"{bot.user.name} ({prefix})")
	except discord.Forbidden:
		pass


async def ready_handler(bot):
	guild: discord.Guild

	for guild in bot.guilds:
		prefix = u.guild_update(bot, guild)
		await try_set_nickname(bot, guild, prefix)
	changer = status_rotation.StatusRotation(bot)
	return changer
