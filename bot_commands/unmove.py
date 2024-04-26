from helpers.other.permissions import Permissions, db

from . import Result


@Permissions.register_command("")
async def unmove(data: Result):
	"""Re-moves you to the channel you came from when you have been moved elsewhere.
	``````py
	"""
	author = data.message.author
	# channel = stuff.channel
	coll = db.db.get_collection("User")
	try:
		if coll.find_one({"id": author.id, "re-move": True}):
			coll.update_one({"id": author.id}, {"$set": {"re-move": False}})
			text = "You won't be automatically \"re-moved\" to the channel from where you have been moved out anymore!"
		else:
			coll.update_one({"id": author.id}, {"$set": {"re-move": True}}, upsert = True)
			text = "You will be automatically \"re-moved\" to the channel from where you have been moved out!"
		
		embed = data.bot.responder.emb_resp("Update successful!", text, "success")
	except Exception as e:
		embed = data.bot.responder.emb_resp("Error", str(e) + f"\n{e.__traceback__.tb_lineno}", "error")
	
	to_send = {"embed": embed}
	return data, to_send
