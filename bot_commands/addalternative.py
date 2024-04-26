from helpers.other.permissions import Permissions, db
from helpers.other.bot_collections import Collection
from . import Result


@Permissions.register_command(
	"",
	slash_args = {
		"command": Collection["commands"],
		"alt_name": str
	}
)
async def addalternative(data: Result):
	"""Suggest an alternative name for a command
	``````py
	command: str
		command to add an alternative name to
	alt_name: str
		alternative name"""

	from helpers.other.utilities import Markdown as Md
	from helpers.other.utilities import approve_alt

	if not len(data.args) == 2:
		embed = data.bot.responder.emb_resp(
			"Error",
			"Invalid amount of arguments",
			"error"
		)
		return data, {"embed": embed}

	cmd_name = data.args.get("0", data.args.get("command"))
	alt_name = data.args.get("1", data.args.get("alt_name"))

	coll = db.db.get_collection(name = "Commands")
	if (
		cmd := coll.find_one({"$or": [{"name": cmd_name}, {"aliases": cmd_name}]}))\
		and Permissions.check_perms_for(cmd.get("name"), data.user[1]):
		if await approve_alt(data.bot, cmd_name, alt_name):
			coll.update_one({"name": cmd_name}, {"$addToSet": {"aliases": alt_name}})
			embed = data.bot.responder.emb_resp(
				"Done!",
				f"Added {Md.sn_(alt_name)} as alternative name to {Md.sn_(cmd_name)}",
				"ok"
			)
		else:
			embed = data.bot.responder.emb_resp(
				"Request wasn't approved by the bot owner",
				color = "std_info"
			)
	elif cmd:
		embed = data.bot.responder.emb_resp(
			"Failed to Complete!",
			f"Not allowed to modify {Md.sn_(cmd_name)}!",
			"error"
		)
	else:
		embed = data.bot.responder.emb_resp(
			"Failed to Complete!",
			f"{Md.sn_(cmd_name)} couldn't be found",
			"error"
		)

	to_send = {"embed": embed}
	return data, to_send
