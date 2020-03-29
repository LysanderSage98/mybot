import discord
from helpers.other import db_handler as db


async def private_channel_handler(*args, cud = None):
	if cud:
		if cud == "create":
			channel = args[0]
			print(channel, " created")
			try:
				user: discord.User = channel.recipient
				try:
					coll = db.db.get_collection(name = "Data")
					if not coll.find_one({"id": user.id}):
						doc = {"name": user.name, "id": user.id, "log": True, "messages": []}
						coll.insert_one(doc)
				except db.errors.DuplicateKeyError:
					return
			except Exception as e:
				print(e)
	else:
		return 1, args
