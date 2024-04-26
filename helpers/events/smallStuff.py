import datetime

import discord

from helpers.other import db_stuff as db


def typing_handler(channel, user, when, client):
	try:
		if type(channel) is not discord.DMChannel and user.status == discord.Status.offline:
			print(channel)
			print(f"{user.name.upper()} IS OFFLINE!", when.strftime("%S"))
	except Exception as e:
		print(e)
		

async def voice_state_handler(member, before, after, bot):
	if member == bot.user:
		return
	coll = db.db.get_collection("User")
	user = coll.find_one({"id": member.id})
	print(user)
	
	if before.channel is None:
		coll.update_one({"id": member.id}, {"$set": {"channel": after.channel.id}}, upsert = True)
	
	elif after.channel != before.channel and after.channel is not None:
		channel = bot.get_channel(user["channel"])
		
		if not channel:
			coll.update_one({"id": member.id}, {"$set": {"channel": after.channel.id}})
			return
		
		if after.channel == channel:
			return
		
		elif not user.get("re-move"):
			coll.update_one({"id": member.id}, {"$set": {"channel": after.channel.id}}, upsert = True)
			return
		
		else:
			try:
				await member.move_to(before.channel)
			except (discord.HTTPException, TypeError):
				pass
	else:
		members = before.channel.members
		members = list(filter(lambda x: not x.bot, members))
		v_c = before.channel.guild.voice_client
		if (
			not members or len(list(filter(lambda x: x.voice.self_deaf or x.voice.deaf, members))) == len(members)
		) and v_c and v_c.is_playing():
			v_c.pause()
