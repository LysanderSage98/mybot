import discord
import json
import typing

from helpers.other.permissions import Permissions, db
from . import Result


@Permissions.register_command("admin", slash_args = {"prefix": typing.Optional[str], "arg0": typing.Optional[typing.Literal['reset']]})
async def setprefix(data: Result):
	"""set new prefix for server
	``````py
	prefix: str
		new prefix
	arg0: typing.Literal
		reset prefix to bot default
	"""
	coll = db.db.get_collection("Settings")
	if not (args := data.args):
		settings = coll.find_one({"guild": data.message.guild.id})
		if settings:
			embed = data.bot.responder.emb_resp("Currently used prefix", settings["guild_settings"]["prefix"], color = "info")
		else:
			embed = data.bot.responder.emb_resp2("No guild settings found!")
	else:
		if args.get("arg0", args.get("0", None)) == "reset":
			prefix = json.loads(open("data/info.json", "r").read())["prefix"]
			coll.find_one_and_update(
				{"guild": data.message.guild.id},
				{
					"$set": {
						"guild_settings.prefix": prefix
					}
				}
			)
			embed = data.bot.responder.emb_resp("Reset prefix!", color = "ok")
		else:
			prefix = args.get("prefix", args.get("0"))
			coll.find_one_and_update(
				{"guild": data.message.guild.id},
				{
					"$set": {
						"guild_settings.prefix": prefix
					}
				}
			)
			embed = data.bot.responder.emb_resp("New prefix set!", color = "success")
		await data.message.guild.me.edit(
			nick = data.bot.user.name + f" ({prefix})"
		)

	# raise RuntimeError("Not implemented yet!")  # TODO implement command 'setprefix'

	to_send = {
		"embed": embed
	}
	return data, to_send
