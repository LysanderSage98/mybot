import discord

from helpers.other.permissions import Permissions, db
from helpers.other.bot_collections import Collection
from . import Result


@Permissions.register_command(
	"",
	slash_args = {
		"command": Collection['commands'],
		"new_desc": str
	}
)
async def changedescription(data: Result):
	"""Suggest description change of a command to owner.
	``````py
	command: str
		command to update
	new_desc: str
		new description
	"""
	print(data)
	raise RuntimeError("Not implemented yet!")  # TODO implement command 'changedescription'

