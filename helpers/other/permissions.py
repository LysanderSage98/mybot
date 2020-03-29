from . import db_handler as db


class Permissions:
	commands = {}
	settings = db.db.get_collection(name = "Settings")
	
	def __init__(self, result_object = None):
		self.prefix = "^"
		if result_object:
			self.__class__.result_object = result_object
		else:
			self.result_object = None

	def register_command(self, perm = None):
		def res(coroutine):
			self.__class__.commands.update({coroutine.__name__: (coroutine, perm)})
			print(self.__class__.commands)
			return coroutine
		return res
	
	def update_settings(self):
		self.__class__.settings = db.db.get_collection(name = "Settings")
	
	def check(self, message, bot):
		guild = message.guild
		channel = message.channel
		guild_settings = None
		if guild:
			guild_settings = self.__class__.settings.find_one({"name": guild.id})
			if guild_settings:
				prefix = guild_settings.get("prefix")
				if prefix:
					self.prefix = prefix

		if message.content.startswith(self.prefix):
			# print(message)
			content = message.content.strip(self.prefix)
			command_args = content.split(" ", 1)
			func = self.__class__.commands.get(command_args[0])
			result = self.__class__.result_object(bot, message, True)
			if func:
				# print(func)
				result.command = func[0]
				req_perm = func[1]
				if guild_settings:
					overwrites = guild_settings.get(command_args[0])
					if overwrites:
						print(overwrites)
				if req_perm == "owner" and message.author == bot.owner:
					pass
				elif req_perm == "admin" and message.author.permissions_in(channel).administrator:
					pass
				elif not req_perm:
					pass
				else:
					result.error = "Missing permission " + req_perm

			return result
