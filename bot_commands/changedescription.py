import discord

from helpers.other.permissions import Permissions, db
from helpers.other.collections import Collection


@Permissions.register_command(
	"",
	slash_args = {
		"command": Collection['commands'],
		"new_desc": str
	}
)
async def changedescription(data):
	"""Suggest description change of a command to owner.
	``````py
	command: str
		command to update
	new_desc: str
		new description
	"""
	raise RuntimeError("Not implemented yet!")  # TODO implement command 'changedescription'

