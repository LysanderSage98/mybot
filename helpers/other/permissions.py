import datetime
import discord
import typing

from . import db_stuff as db
from .bot_collections import Collection


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
		return self.me == "owner"

	def __repr__(self):
		return str(self.me)

	def __str__(self):
		return str(self.me)


class All(PermHierarchy):
	_instance = None

	def __new__(cls, *args, **kwargs):
		if not cls._instance:
			cls._instance = super().__new__(cls)
		return cls._instance

	def __init__(self):
		super().__init__()
		self.me = ""


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
		"": All,
		"admin": Admin,
		"owner": Owner
	}
)

commands: dict[str, tuple[typing.Coroutine, PermHierarchy, dict[str, typing.Any]]] = {}
Collection("commands", commands)


class Permissions:
	settings: db.pymongo.database.Collection = db.db.get_collection(name = "Settings")
	command_list: db.pymongo.database.Collection = db.db.get_collection(name = "Commands")
	
	def __init__(self, result_object = None):
		if result_object:
			self.__class__.result_object = result_object
		else:
			self.result_object = None

	@classmethod
	def register_command(cls, perm, slash_args: dict[str, typing.Any] = None):
		def res(coroutine: typing.Coroutine):
			cls.command_list.update_one(
				{
					"name": coroutine.__name__
				}, {
					"$set": {
						"permission": perm,
						"name": coroutine.__name__,
						"desc": coroutine.__doc__.split("``````py", 1)[0].strip(),
					},
					"$setOnInsert": {
						"aliases": [],
						"usage": "{prefix}" + coroutine.__name__,
						"usage_ex": "",
						"added_by": {
							"id": 435104102599360522,
							"name": "lysandersage98"
						},
						"added_on": datetime.datetime.now(datetime.UTC).timestamp(),
					}
				}, upsert = True
			)
			cl = PermHierarchy.classes[perm]
			commands.update(
				{
					coroutine.__name__: (
						coroutine,
						cl(),
						slash_args or {}
					)
				}
			)
			print("="*100 + "\n", commands, "\n" + "="*100)
			return coroutine
		return res

	@classmethod
	def get_perms(cls, bot, req_perm, src: typing.Union[discord.Interaction, discord.Message]):
		user = getattr(src, "user", getattr(src, "author", None))
		if user == bot.owner:
			has_perm = Owner()
		elif src.channel.permissions_for(user).administrator:
			has_perm = Admin()
		elif not req_perm:
			has_perm = All()
		else:
			has_perm = All()  # todo might need update

		return has_perm

	@classmethod
	def check_perms_for(cls, cmd: str, perm: PermHierarchy):
		req_perm = commands.get(cmd)[1]
		print(f"Comparing {perm} with {req_perm}")
		return perm >= req_perm

	def validate_interaction(self, interaction: discord.Interaction, bot):
		guild = interaction.guild
		guild_settings = None
		prefix = bot.prefix
		if guild:
			setting = self.__class__.settings.find_one({"guild": guild.id})
			guild_settings = setting.get("guild_settings") if setting else None
			if guild_settings:
				# print(guild_settings)
				prefix = guild_settings.get("prefix")
			else:
				raise RuntimeError("No guild settings found for guild", guild.name)
		func = commands.get(interaction.data["name"])
		result = self.__class__.result_object(bot, interaction)
		result.command = interaction.data["name"]
		result.args = {el["name"]: el["value"] for el in (interaction.data.get("options") or [])}
		result.prefix = prefix
		if func:
			print("func data in permissions.check:", func)
			result.function = func[0]
			req_perm = func[1]
			if guild_settings:
				overwrites_for_cmd = guild_settings.get(interaction.data["name"])
				if overwrites_for_cmd:
					print("perm overwrites_for_cmd", overwrites_for_cmd)

			has_perm = self.get_perms(bot, req_perm, interaction)
			result.user = (interaction.user, has_perm)
			if has_perm < req_perm:
				result.error = "Missing permission " + str(req_perm)
		result.valid = True
		return result

	def validate_msg(self, message: discord.Message, bot):
		guild = message.guild
		guild_settings = None
		prefix = bot.prefix
		if guild:
			setting = self.__class__.settings.find_one({"guild": guild.id})
			guild_settings = setting.get("guild_settings") if setting else None
			if guild_settings:
				# print(guild_settings)
				prefix = guild_settings.get("prefix")
			else:
				raise RuntimeError("No guild settings found for guild", guild.name)

		if message.content.startswith(prefix):
			# print(message)
			content = message.content.strip(prefix)
			command_args = content.split(" ")
			func = commands.get(command_args[0])
			if not func:
				cmd = self.command_list.find_one({"aliases": command_args[0]})
				func = commands.get(cmd.get("name")) if cmd else None
			result = self.__class__.result_object(bot, message)
			result.command = command_args[0]
			result.args = {str(x): y for x, y in enumerate(command_args[1:])}
			result.prefix = prefix
			if func:
				print("func data in permissions.check:", func)
				result.function = func[0]
				req_perm = func[1]
				if guild_settings:
					overwrites_for_cmd = guild_settings.get(command_args[0])
					if overwrites_for_cmd:
						print("perm overwrites_for_cmd", overwrites_for_cmd)

				has_perm = self.get_perms(bot, req_perm, message)
				result.user = (message.author, has_perm)
				if has_perm < req_perm:
					result.error = "Missing permission " + str(req_perm)
			result.valid = True
			return result
