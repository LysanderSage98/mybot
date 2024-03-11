import discord
import re

from helpers.other import status_rotation, db_stuff as db
from helpers.other.permissions import Permissions


async def try_set_nickname(bot, guild: discord.Guild, prefix):
	try:
		match = re.search("\((.)\)$", guild.me.nick)
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
	coll1 = db.db.get_collection("Guilds")
	coll2 = db.db.get_collection("Settings")
	guild: discord.Guild

	for guild in bot.guilds:
		coll1.update_one({
			"id": guild.id
		}, {
			"$set": {
				"id": guild.id,
				"name": guild.name,
				"owner": {
					"id": guild.owner_id,
					"name": guild.owner.name
				}
			}
		}, upsert = True)
		setting = coll2.find_one({"guild": guild.id})
		prefix = bot.prefix

		if setting:
			guild_settings = setting.get("guild_settings")
			if guild_settings:
				prefix = guild_settings.get("prefix")
				if not prefix:
					coll2.update_one(
						{
							"guild": guild.id
						}, {
							"$set": {
								"guild_settings.prefix": bot.prefix
							}
						}
					)
					prefix = bot.prefix
			else:
				coll2.update_one(
					{
						"guild": guild.id
					}, {
						"$set": {
							"guild_settings.prefix": bot.prefix
						}
					}
				)
		else:
			coll2.insert_one(
				{
					"guild": guild.id,
					"guild_settings": {
						"prefix": bot.prefix
					}
				}
			)
		await try_set_nickname(bot, guild, prefix)
	changer = status_rotation.StatusRotation(bot)
	return changer
