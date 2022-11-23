import bot_commands
import datetime
import discord
import pathlib

from bot_commands import Result
from helpers.other.db_stuff import db


class Markdown(str):

	@classmethod
	def bold(cls, s):
		return f"**{s}**"

	@classmethod
	def italic(cls, s):
		return f"*{s}*"

	@classmethod
	def strikethrough(cls, s):
		return f"~~{s}~~"

	@classmethod
	def underline(cls, s):
		return f"__{s}__"

	@classmethod
	def snippet(cls, s):
		return f"`{s}`"

	@classmethod
	def codeblock(cls, s):
		return f"{cls.snippet(cls.snippet(cls.snippet(s)))}"

	@classmethod
	def quote(cls, s):
		parts = s.split("\n")
		return "> " + "> ".join(parts)

	bo = bold
	it = italic
	st = strikethrough
	un = underline
	sn = snippet
	cb = codeblock
	qu = quote


def concat(string):
	if string:
		return "https://www.youtube.com/watch?v=" + string


async def cmd_adder(data: Result):
	reactions = ["✅", "❌"]
	message = data.message
	channel = data.message.channel
	client = data.client
	resp = client.responder
	if message.author.id == data.client.owner.id:
		perm = "owner"
	elif message.author.id == message.channel.guild.owner.id:
		perm = "admin"
	else:
		perm = None
	msg = await channel.send(embed = resp.emb_resp(f"Command '{data.command}' not found!", "Do you want to add it?"))
	for reaction in reactions:
		await msg.add_reaction(reaction)

	def check_react(r: discord.Reaction, user: discord.User):
		return r.emoji in reactions and user == data.message.author and r.message.channel == data.message.channel

	try:
		reaction_user = await client.wait_for("reaction_add", check = check_react, timeout = 30)
		res = reaction_user[0].emoji
	except TimeoutError:
		res = reactions[1]
	if res == reactions[1]:
		await channel.send(embed = resp.emb_resp("Command not added!"))
		return 0

	def check_msg(message: discord.Message):
		return message.author == data.message.author and message.channel == data.message.channel

	async def continue_or_fail(string):
		await channel.send(string)
		try:
			message: discord.Message = await client.wait_for("message", check = check_msg, timeout = 120)
		except TimeoutError:
			await channel.send(embed = resp.emb_resp("Timeout exceeded", "Command not added"))
			return 0
		return message.content

	if not (desc := await continue_or_fail(
		"Send a description of the new command within the next 2 minutes"
	)):
		return 0
	print(desc)

	if not (usage := await continue_or_fail(
		"Next, send the syntax of the new command within the next 2 minutes"
	)):
		return 0
	print(usage)

	if not (usage_ex := await continue_or_fail(
		"As last step, send a usage example of the new command within the next 2 minutes"
	)):
		return 0
	print(usage_ex)

	coll = db.db.get_collection(name = "Commands")
	coll.insert_one(
		{
			"$set": {
				"name": data.command,
				"aliases": [],
				"desc": desc,
				"usage": "{prefix}" + usage,
				"usage_ex": "{prefix}" + usage_ex,
				"added_by": {
					"id": data.message.author.id,
					"name": data.message.author.name
				},
				"added_on": datetime.datetime.utcnow().timestamp(),
				"permission": perm
			}
		}
	)
	await channel.send(embed = resp.emb_resp("New command added!"))

	path = pathlib.Path(f"bot_commands/{data.command}.py")
	cmd_template = open("data/cmd_template.txt", "r").read()
	print(cmd_template)
	try:
		cmd_template = cmd_template.format(perm = repr(perm), cmd = data.command, desc = desc)
		print(cmd_template)
	except KeyError as e:
		e.with_traceback(e.__traceback__)
		data.error = e
		return data
	open(path, "w").write(cmd_template)
	bot_commands.import_cmds([data.command])
