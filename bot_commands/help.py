import datetime
import discord


from helpers.other.permissions import Permissions, PermHierarchy
from helpers.other.collections import Collection
from . import Result


@Permissions.register_command(
	"",
	slash_args = {
		"command": Collection["commands", None]
	}
)
async def help(data: Result):
	"""Shows command overview or help for individual commands.
	"<>" = placeholder
	"{}" = required by previous literal
	"[]" = optional
	"()" = group
	"|"  = only one of the separated options
	"''" = literal value
	"%%" = numeric value
	``````py
	command: str
		the command to get help for"""
	from helpers.other.utilities import Markdown as Md
	cmds = Permissions.command_list

	if data.args:
		single = data.args.get(0, data.args.get("command"))
		title = f"Help for {Md(single).snippet().bold()}"
	else:
		title = "Command overview"
		single = False
	embed = data.bot.responder.emb_resp(title, color = "info")

	found = cmds.find({"$or": [{"name": single}, {"aliases": single}]} if single else None)

	if not found:
		embed.title = f"Command {Md.sn(single)} not found!"
		embed.color = data.bot.responder.colors["error"]

	elif single:
		cmd = found[0]
		desc = cmd["desc"]
		usage = cmd["usage"]

		embed.add_field(
			name = "Aliases (only relevant for non-slash usage)",
			value = Md.sn(", ".join(cmd["aliases"])) if cmd["aliases"] else "None",
			inline = False)
		embed.add_field(
			name = "Description",
			value = Md.cb("py\n" + desc),
			inline = False)
		embed.add_field(
			name = "Usage",
			value = Md.cb(usage.format(prefix = data.prefix)),
			inline = False)
		embed.add_field(
			name = "Usage example",
			value = Md.cb(cmd["usage_ex"].format(prefix = data.prefix)) if cmd["usage_ex"] else "None",
			inline = False)
		embed.set_author(
			name = f'added by {cmd["added_by"]["name"]} on {datetime.datetime.fromtimestamp(cmd["added_on"])} UTC',
			icon_url = (await data.bot.fetch_user(cmd["added_by"]["id"])).display_avatar.url)

	else:
		out = "```"
		for cmd in found:
			if PermHierarchy.classes[cmd["permission"]] <= data.user[1]:
				out += f"- {cmd['name']}\n"
		out += "```"
		embed.description = out

	embed.set_footer(text = f"You might want to do {data.prefix}help help to get a better understanding of the command usage")

	to_send = {
		"embed": embed
	}

	return data, to_send
