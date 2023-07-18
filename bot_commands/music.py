import discord
import typing

from helpers.other.permissions import Permissions, db
from . import Result


@Permissions.register_command("admin", slash_args = {"arg0": typing.Optional[typing.Literal['play', 'pause', 'skip', 'shuffle', 'loop', 'move', 'stop', 'join']], "skip": typing.Optional[int], "loop": typing.Optional[int], "from": typing.Optional[int], "to": typing.Optional[int], "stored": typing.Optional[typing.Literal['stored']], "search": typing.Optional[str]})
async def music(data: Result):
	"""music functionalities
	``````py
	arg0: typing.Literal
		functionality
	skip: int
		amount of songs to skip - only used with skip functionality
	loop: int
		loop count, any negative number for infinite loop - only used with loop functionality
	from: int
		current song position - only used with move functionality
	to: int
		target song position - only used with move functionality
	stored: typing.Literal
		do not search for playlist name on youtube, use a saved one in the bot - only used with play functionality
	search: str
		song-link or playlist-link / -name only used with play functionality
	"""
	print(data)
	raise RuntimeError("Not implemented yet!")  # TODO implement command 'music'
