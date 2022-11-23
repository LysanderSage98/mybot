import discord
from helpers.other.permissions import Permissions, PermHierarchy
from . import Result


@Permissions.register_command(None)
async def help(data: Result):
	"""Shows command overview or help for individual commands"""
	channel = data.message.channel
	cmds = Permissions.command_list

	if data.args:
		single = data.args[0]
		title = f"Help for **`{single}`**"
	else:
		title = "Command overview"
		single = False
	embed = data.client.responder.emb_resp(title, color = "info")

	found = cmds.find({"name": single} if single else None)

	if single:
		from helpers.other.utilities import Markdown as Md
		cmd = found[0]
		embed.add_field(name = "Aliases", value = Md.sn(", ".join(cmd["aliases"])))
		embed.add_field(name = "Description", value = Md.cb("py\n" + cmd["desc"]))
		embed.add_field(name = "Usage", value = Md.cb(cmd["usage"].format(prefix = data.prefix)))
		embed.add_field(name = "Usage example", value = Md.cb(cmd["usage_ex"].format(prefix = data.prefix)))

	else:
		out = "```"
		for cmd in found:
			if PermHierarchy.classes[cmd["permission"]] <= data.user[1]:
				out += f"- {cmd['name']}\n"
		out += "```"
		embed.description = out

	embed.set_footer(text = "You might want to do ^help help to get a better understanding of the command usage")

	await channel.send(embed = embed)

	return data
