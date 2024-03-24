from helpers.other.permissions import Permissions
from . import Result


@Permissions.register_command("owner")
async def sync(data: Result):
	"""sync commands"""
	await data.bot.grow_app_commands()
	await data.message.channel.send("TEST")
	await data.bot.sync_app_commands()
	await data.message.channel.send("TEST")
	return data
