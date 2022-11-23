import typing

import discord
import importlib
import os
import sys

import helpers.other.permissions


class Result:
	__slots__ = ("valid", "client", "message", "command", "function", "args", "error", "user", "prefix")

	def __init__(self, client, message, valid = False):
		from modules.bot import Bot

		self.valid = valid
		self.client: Bot = client
		self.message: discord.Message = message
		self.command: str
		self.function: typing.Coroutine
		self.args: list
		self.error: str
		self.user: tuple[discord.User, helpers.other.permissions.PermHierarchy]
		self.prefix: str

	def __bool__(self):
		if not self.error:
			return self.valid
		else:
			return False

	def __getattr__(self, item):
		sys.stderr.write("-" * 30 + f"{item}, doesn't exist\n")
		return None

	def __repr__(self):
		return "-" * 20 + f"\n" \
			f"valid = {self.valid}\n" \
			f"client = {self.client}\n" \
			f"message = {self.message}\n" \
			f"(found)command = {self.command}\n" \
			f"function = {self.function}\n" \
			f"args = {self.args}\n" \
			f"user = {self.user}\n"\
			f"error = {self.error}\n" + "-" * 20


imported = {}


def import_cmds(cmds: list = None):
	if not cmds:
		commands = list(filter(None, map(lambda x: x.rsplit(".", 1)[0] if "__" not in x else None, os.listdir("./bot_commands"))))
	else:
		commands = cmds
	for command in commands:
		if command not in imported:
			module = importlib.import_module("." + command, package = "bot_commands")
			imported[module.__name__.split(".")[-1]] = module
		else:
			importlib.reload(imported[command])
		print("imported command: ", command)
	return commands


import_cmds()
