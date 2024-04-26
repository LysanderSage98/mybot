import discord

from helpers.other.permissions import Permissions, db
from helpers.other.bot_collections import Collection
from . import Result

from helpers.other import utilities as u


@Permissions.register_command("", slash_args = {"command": Collection["commands"], "new_text": str})
async def changeusageexample(data: Result):
	"""Suggest a new usage example text for the command
	``````py
	command: str,
	new_text: str
	"""
	from helpers.other.utilities import Markdown as Md
	cmds = Permissions.command_list

	channel = data.message.channel
	bot = data.bot
	author = data.message.author
	args = data.args
	
	coll = db.db.get_collection(name = "Commands")
	title = "Info"
	
	try:
		cmd = args.pop("command", args.pop("0", None))
		# cmd = args[0]
		usage = " ".join(args)
		found = cmds.find({"$or": [{"name": cmd}, {"aliases": cmd}]})
		
		if not found:
			response = f"Command {Md.sn_(cmd)} not found!"
			color = data.bot.responder.colors["error"]
		
		else:
			response = f"✅ New usage example for {cmd} added!"
			color = "success"
			text = f" ```{usage}``` for cmd ```{cmd}```"
			embed = bot.responder.emb_resp("New usage example requested!", text, "info").set_author(name = author.name)
			emoji, dm_c = await u.approve(bot, embed)
			
			if str(emoji) == "✅":
				coll.update_one({"name": cmd}, {"$set": {"usage_example": "{}" + usage}})
			else:
				def check(check_message):
					return check_message.channel == dm_c
				
				message = await bot.wait_for('message', check = check)
				response = f"❌ Usage example \"{usage}\" wasn't approved\n```Reason: {message.content}```"
				color = "error_2"
		embed = bot.responder.emb_resp(title, response, color)
	
	except Exception as e:
		print(e)
		embed = bot.responder.emb_resp("Error", str(e), "error_2")
		# return await msg.delete(delay = 120)  # todo allow later deletion with
	to_send = {"embed": embed}
	return data, to_send
