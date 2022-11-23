import datetime
import typing

import discord

from . import db_stuff as db


def normalize_types(func):
	def wrapper(*args):
		res = []
		for arg in args:
			if arg.__class__ != type:
				# print("not type", arg.__class__)
				res.append(arg.__class__)
			else:
				# print("type", arg.__class__)
				res.append(arg)
		return func(*res)
	return wrapper


class PermHierarchy(str):
	perms = {}
	classes = {}

	def __new__(cls, *args, **kwargs):
		if not cls.perms:
			temp = cls.__subclasses__()
			cls.perms = dict(map(lambda x: x[::-1], enumerate(temp)))
			print(cls.perms)
		else:
			return super().__new__(cls)

	@classmethod
	def update_classes(cls, data):
		cls.classes.update(data)

	def __init__(self):
		self.me = ...

	@normalize_types
	def __eq__(self, other):
		# print(self, other)
		return self.perms[self] == self.perms[other]

	@normalize_types
	def __gt__(self, other):
		# print(self, other)
		return self.perms[self] > self.perms[other]

	@normalize_types
	def __ge__(self, other):
		# print(self, other)
		return self.perms[self] >= self.perms[other]

	@normalize_types
	def __lt__(self, other):
		# print(self, other)
		return self.perms[self] < self.perms[other]

	@normalize_types
	def __le__(self, other):
		# print(self, other)
		return self.perms[self] <= self.perms[other]

	def __bool__(self):
		return bool(self.me)

	def __repr__(self):
		return str(self.me)


class All(PermHierarchy):
	_instance = None

	def __new__(cls, *args, **kwargs):
		if not cls._instance:
			cls._instance = super().__new__(cls)
		return cls._instance

	def __init__(self):
		super().__init__()
		self.me = None


class Admin(PermHierarchy):
	_instance = None

	def __new__(cls, *args, **kwargs):
		if not cls._instance:
			cls._instance = super().__new__(cls)
		return cls._instance

	def __init__(self):
		super().__init__()
		self.me = "admin"


class Owner(PermHierarchy):
	_instance = None

	def __new__(cls, *args, **kwargs):
		if not cls._instance:
			cls._instance = super().__new__(cls)
		return cls._instance

	def __init__(self):
		super().__init__()
		self.me = "owner"


PermHierarchy()
PermHierarchy.update_classes(
	{
		None: All,
		"admin": Admin,
		"owner": Owner
	}
)


class Permissions:
	commands: dict[str, tuple[typing.Coroutine, PermHierarchy]] = {}
	settings: db.database.Collection = db.db.get_collection(name = "Settings")
	command_list: db.database.Collection = db.db.get_collection(name = "Commands")
	
	def __init__(self, result_object = None):
		self.prefix = ""
		if result_object:
			self.__class__.result_object = result_object
		else:
			self.result_object = None

	@classmethod
	def register_command(cls, perm):
		def res(coroutine: typing.Coroutine):
			cls.command_list.update_one(
				{
					"name": coroutine.__name__
				}, {
					"$set": {
						"permission": perm,
						"name": coroutine.__name__,
					},
					"$setOnInsert": {
						"aliases": [],
						"desc": coroutine.__doc__,
						"usage": "{prefix}" + coroutine.__name__,
						"usage_ex": "",
						"added_by": {
							"id": 435104102599360522,
							"name": "LysanderSage98"
						},
						"added_on": datetime.datetime.utcnow().timestamp(),
					}
				}, upsert = True
			)
			cl = PermHierarchy.classes[perm]
			cls.commands.update({coroutine.__name__: (coroutine, cl())})
			print("="*100 + "\n", cls.commands, "\n" + "="*100)
			return coroutine
		return res
	
	# def update_settings(self):
	# 	self.settings = db.db.get_collection(name = "Settings")
	
	def check(self, message: discord.Message, bot):
		guild = message.guild
		guild_settings = None
		if guild:
			setting = self.__class__.settings.find_one({"guild": guild.id})
			guild_settings = setting.get("guild_settings") if setting else None
			if guild_settings:
				# print(guild_settings)
				prefix = guild_settings.get("prefix")
				if prefix:
					# print(prefix)
					self.prefix = prefix
				else:
					self.prefix = bot.prefix
			else:
				raise RuntimeError("No guild settings found for guild", guild.name)

		if message.content.startswith(self.prefix):
			# print(message)
			content = message.content.strip(self.prefix)
			command_args = content.split(" ", 1)
			func = self.__class__.commands.get(command_args[0])
			result = self.__class__.result_object(bot, message, True)
			result.command = command_args[0]
			result.args = command_args[1:]
			result.prefix = self.prefix
			if func:
				print(func)
				result.function = func[0]
				req_perm = func[1]
				if guild_settings:
					overwrites = guild_settings.get(command_args[0])
					if overwrites:
						print(overwrites)
				if message.author == bot.owner:
					perm = Owner()
				elif message.channel.permissions_for(message.author).administrator:
					perm = Admin()
				elif not req_perm:
					perm = All()
				else:
					perm = All()  # todo might need update
				result.user = (message.author, perm)
				if perm < req_perm:
					result.error = "Missing permission " + str(req_perm)
			return result
