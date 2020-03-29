import discord
from helpers.other import db_handler as db


def typing_handler(channel, user, when, client):
	try:
		if type(channel) is not discord.DMChannel and user.status == discord.Status.offline:
			print(channel)
			print(f"{user.name.upper()} IS OFFLINE!", when.strftime("%S"))
	except Exception as e:
		print(e)
		

async def voice_state_handler(member, before, after, client):
	if member == client.user:
		return
	print(member, before, end = "")
	coll = db.db.get_collection("Data")
	
	if before.channel is None:
		print(" no channel change")
		coll.update_one({"id": member.id}, {"$set": {"channel": after.channel.id}}, upsert = True)
	
	elif after.channel != before.channel and after.channel is not None:
		# print([log async for log in member.guild.audit_logs()])
		channel = client.get_channel(coll.find_one({"id": member.id})["channel"])
		
		if after.channel == channel:
			print(" pass")
			return
		
		elif not coll.find_one({"id": member.id, "re-move": True}):
			print(" disabled")
			return
		
		else:
			print(" move!")
			print(after)
			try:
				await member.move_to(before.channel)
			except (discord.HTTPException, TypeError):
				pass
	else:
		print(" pass")
