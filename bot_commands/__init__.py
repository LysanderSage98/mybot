import importlib
import os


commands = list(filter(None, map(lambda x: x[:-3] if "__" not in x else None, os.listdir("./bot_commands"))))
for command in commands:
	print(command)
	importlib.import_module("." + command, package = "bot_commands")


class Result:
	__slots__ = ("valid", "client", "message", "command", "args", "error")
	
	def __init__(self, client, message, valid = False):
		self.valid = valid
		self.client = client
		self.message = message
	
	def __bool__(self):
		return self.valid
	
	def __getattr__(self, item):
		print(item, "doesn't exist")
		return None
