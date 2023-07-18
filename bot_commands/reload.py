import discord
from helpers.other.permissions import Permissions, db
from . import import_cmds, Result


@Permissions.register_command('owner')
async def reload(data: Result):
	"""reload commands"""
	if args := data.args:
		reloaded = import_cmds(args.values())
	else:
		reloaded = import_cmds()
	await data.message.channel.send(
		embed = data.bot.responder.emb_resp(
			desc = f"Reloaded ```{', '.join(reloaded)}```",
			color = "success"
		)
	)
	return data
