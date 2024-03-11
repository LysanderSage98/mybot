import discord
import googleapiclient.discovery
import helpers.other.permissions
import helpers.other.utilities
import importlib
import json
import os
import sys
import types
import typing

api_info = json.loads(open("data/info.json", "r").read())["api_info"]


music_instances = {}
youtube = googleapiclient.discovery.build(api_info[0], api_info[1], developerKey = api_info[2])


class Result:
	__slots__ = ("valid", "bot", "message", "command", "function", "args", "error", "user", "prefix", "ret")

	def __init__(self, bot, message, valid = False):
		from modules.bot import Bot

		self.valid = valid
		self.bot: Bot = bot
		self.message: discord.Message = message
		self.command: str
		self.function: typing.Coroutine
		self.args: list
		self.error: str
		self.user: tuple[discord.User, helpers.other.permissions.PermHierarchy]
		self.prefix: str
		self.ret = False

	def __bool__(self):
		return self.valid

	def __getattr__(self, item):
		sys.stderr.write("-" * 30 + f"'{item}', doesn't exist\n")
		return None

	def __repr__(self):
		return "-" * 20 + f"\n" \
			f"valid = {self.valid}\n" \
			f"bot = {self.bot}\n" \
			f"message = {self.message}\n" \
			f"(found)command = {self.command}\n" \
			f"function = {self.function}\n" \
			f"args = {self.args}\n" \
			f"user = {self.user}\n"\
			f"error = {self.error}\n" + "-" * 20


imported = {}


def import_cmds(cmds: list = None):
	if not cmds:
		commands = list(
			filter(
				None,
				map(
					lambda x: x.rsplit(".", 1)[0] if "__" not in x else None,
					os.listdir("./bot_commands")
				)
			)
		)
	else:
		commands = cmds
	for command in commands:
		if command not in imported:
			module = importlib.import_module("." + command, package = "bot_commands")
			imported[module.__name__.split(".")[-1]] = module
		else:
			module = importlib.reload(imported[command])
			music_commands = module.__dict__.get("MusicCommands")
			if music_commands:
				for key, val in music_commands.__dict__.items():
					# print(key, val)
					if callable(val):
						for instance in music_instances.values():
							setattr(instance, key, types.MethodType(val, instance))
		print("imported command: ", command)
	return commands


import_cmds()
