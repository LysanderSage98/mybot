import bot_commands
import datetime
import discord
import json
import pathlib
import re
import traceback
import typing

import helpers.other.permissions
from bot_commands import Result
from helpers.other.db_stuff import db
from helpers.other.collections import Collection


class ReprBaseType:
	@classmethod
	def __str__(cls):
		return cls.__base__.__name__


class ReprStr(ReprBaseType, str):
	pass


class ReprInt(ReprBaseType, int):
	pass


class ReprDict(dict):
	def __str__(self):
		out = "{"
		for key, val in self.items():
			out += f'"{key}": {val.__str__()}, '
		return out.strip(", ") + "}"


class Markdown(str):

	@classmethod
	def _bold(cls, s):
		return f"**{s}**"

	@classmethod
	def _codeblock(cls, s):
		temp = s
		for _ in range(3):
			temp = cls._snippet(temp)
		return temp  # f"{cls._snippet(cls._snippet(cls._snippet(s)))}"

	@classmethod
	def _header_big(cls, s):
		return f"# {s}"

	@classmethod
	def _header_medium(cls, s):
		return f"## {s}"

	@classmethod
	def _header_small(cls, s):
		return f"### {s}"

	@classmethod
	def _italic(cls, s):
		return f"*{s}*"

	@classmethod
	def _list_1(cls, s):
		return f"- {s}"

	@classmethod
	def _list_2(cls, s):
		return f" - {s}"

	@classmethod
	def _quote(cls, s):
		parts = s.split("\n")
		return "> " + "> ".join(parts)

	@classmethod
	def _snippet(cls, s):
		return f"`{s}`"

	@classmethod
	def _strikethrough(cls, s):
		return f"~~{s}~~"

	@classmethod
	def _underline(cls, s):
		return f"__{s}__"

	bo = _bold
	cb = _codeblock
	hb = _header_big
	hm = _header_medium
	hs = _header_small
	it = _italic
	l1 = _list_1
	l2 = _list_2
	qu = _quote
	st = _strikethrough
	sn = _snippet
	un = _underline

	def __init__(self, s = ""):
		super().__init__()
		self.s = s

	def bold(self):
		self.s = self.bo(self.s)
		return self

	def codeblock(self):
		self.s = self.cb(self.s)
		return self

	def header_big(self):
		self.s = self.hb(self.s)
		return self

	def header_medium(self):
		self.s = self.hm(self.s)
		return self

	def header_small(self):
		self.s = self.hs(self.s)
		return self

	def italic(self):
		self.s = self.it(self.s)
		return self

	def list_1(self):
		self.s = self.l1(self.s)
		return self

	def list_2(self):
		self.s = self.l2(self.s)
		return self

	def quote(self):
		self.s = self.cb(self.qu)
		return self

	def snippet(self):
		self.s = self.sn(self.s)
		return self

	def strikethrough(self):
		self.s = self.st(self.s)
		return self

	def underline(self):
		self.s = self.un(self.s)
		return self

	def __repr__(self):
		return self.s

	def __str__(self):
		return self.s


def to_yt_url(kind, string):
	url = {"v": "watch", "list": "playlist"}
	return f"https://www.youtube.com/{url[kind]}?{kind}={string}"


def reformat(data: dict):
	res: dict = {}
	insert = ["required", "optional"]

	def walk_dict(_data: dict, to_insert = ""):
		for key, val in list(_data.items()):
			if type(val) == dict:
				if key in insert:
					walk_dict(val, key)
				else:
					res[key] = walk_dict(val, to_insert)
			elif type(val) == list:
				if key in insert:
					temp = walk_list(val, key)
					for el in temp:
						for key_inner, val_inner in el.items():
							if not res.get(key_inner):
								res[key_inner] = {
									"type": val_inner,
								}
								res[key_inner].update(el)
								res[key_inner].pop(key_inner)
								break
				elif key == "choice":
					if not to_insert:
						to_insert = "required"
					temp = walk_list(val, to_insert)
					if not res.get(key):
						res[key] = [temp]
					else:
						res[key].append(temp)
				else:
					if not res.get(key):
						res[key] = walk_list(val, to_insert)
					else:
						res[key].extend(walk_list(val, to_insert))
			else:
				if to_insert:
					_data[to_insert] = True
				else:
					res[key] = {
						"type": val,
						"required": True
					}
		return _data

	def walk_list(_data: list, to_insert = ""):
		for el in _data.copy():
			if type(el) == dict:
				walk_dict(el, to_insert)
			elif type(el) == list:
				walk_list(el, to_insert)
			else:
				pass
		return _data

	walk_dict(data)

	if choice := res.get("choice"):
		res.pop("choice")
		for arg_num, choices in reversed(list(enumerate(choice))):
			_temp = {}
			_d = ""
			for _choice in choices:
				_name = ""
				for k, v in _choice.items():
					if ":" in k:
						k, _d = k.split(":")
					if k not in insert:
						_name = k
						_temp[k] = {
							"type": v
						}
					else:
						_temp[_name][k] = v
			_temp["choice"] = True
			temp_res = {f"arg{arg_num}{':' + _d if _d else ''}": _temp}
			temp_res.update(res)
			res = temp_res
	return res


def parse(string, data, open_stack, ret = False, source = ""):
	literal = ""
	new_data = []
	it = iter(string)
	while (char := next(it, None)) is not None:
		if char in "%'{}|[]()<>:":
			if char == "'":
				if open_stack and ((has_desc := source == "details") or open_stack[-1] == char):
					open_stack.pop()
					if has_desc:
						open_stack.pop()
					if literal:
						return literal
					else:
						raise RuntimeError("Empty literal value received!")
				else:
					open_stack.append(char)
					temp = parse(it, {}, open_stack, source = "literal")
					if type(temp) == tuple:
						temp = ":".join(temp)
					data[temp] = typing.Literal

			elif char == "%":
				if open_stack and ((has_desc := source == "details") or open_stack[-1] == char):
					open_stack.pop()
					if has_desc:
						open_stack.pop()
					if literal:
						return literal
					else:
						raise RuntimeError("Empty literal value received!")
				else:
					open_stack.append(char)
					temp = parse(it, {}, open_stack, source = "numeral")
					if type(temp) == tuple:
						temp = ":".join(temp)
					data[temp] = ReprInt

			elif char == "{":
				if source == "optional":
					raise RuntimeError(
						f"Can't convert to slash!\nRequired value(s) inside optional!\nat '{char}' before \n{''.join(it)}")
				open_stack.append("{")
				res: dict = parse(it, {}, open_stack, source = "required")
				if res:
					if not data.get("required"):
						if len(res) >= 2:
							data["required"] = [{key: val} for key, val in res.items()]
						else:
							data["required"] = [res]
					else:
						if len(res) >= 2:
							data["required"].extend({key: val} for key, val in res.items())
						else:
							data["required"].append(res)

			elif char == "}":
				if open_stack and open_stack[-1] == "{":
					open_stack.pop()
				elif open_stack and source == "details":
					open_stack.pop()
					open_stack.pop()
					return literal
				else:
					raise RuntimeError(f"Invalid format, can't close '{open_stack[-1]}' with '{char}'")
				return data

			elif char == "|":
				if not ret and source == "choice":
					raise RuntimeError(
						f"Can't convert to slash!\nChoice inside choice!\nat '{char}' before \n{''.join(it)}")
				if not data.get("choice"):
					if literal:
						new_data.append(literal)
					else:
						new_data = data.copy()
						new_data = new_data.get("group") or new_data
						data.clear()
					data["choice"] = [new_data]
				res = parse(it, {}, open_stack, True, source = "choice")
				if type(res) == list:
					data["choice"].extend(map(lambda x: x.get("group", x), res))
				else:
					data["choice"].append(res.get("group") or res)
				if ret:
					return data["choice"]
				else:
					return data

			elif char == "[":
				if source == "required":
					raise RuntimeError(
						f"Can't convert to slash!\Optional value(s) inside required!\nat '{char}' before \n{''.join(it)}")
				open_stack.append("[")
				res = parse(it, {}, open_stack, source = "optional")
				if res:
					if not data.get("optional"):
						if len(res) >= 2:
							data["optional"] = [{key: val} for key, val in res.items()]
						else:
							data["optional"] = [res]
					else:
						if len(res) >= 2:
							data["optional"].extend({key: val} for key, val in res.items())
						else:
							data["optional"].append(res)

			elif char == "]":
				if open_stack and open_stack[-1] == "[":
					open_stack.pop()
				elif open_stack and source == "details":
					open_stack.pop()
					open_stack.pop()
					return literal
				else:
					raise RuntimeError(f"Invalid format, can't close '{open_stack[-1]}' with '{char}'")
				return data

			elif char == "(":
				open_stack.append("(")
				data["group"] = parse(it, {}, open_stack, source = source)

			elif char == ")":
				if open_stack[-1] == "(":
					open_stack.pop()
				elif open_stack and source == "details":
					open_stack.pop()
					open_stack.pop()
					return literal
				else:
					raise RuntimeError(f"Invalid format, can't close '{open_stack[-1]}' with '{char}'")
				return data

			elif char == "<":
				if open_stack and open_stack[-1] == "<":
					raise RuntimeError("Invalid format, placeholder inside placeholder")
				open_stack.append("<")
				res: str= parse(it, {}, open_stack, source = "placeholder")
				if type(res) == tuple:
					res, details = res
				else:
					details = ""
				new_key = f"{res}:{details}" if details else res
				if not Collection[res]:
					data[new_key] = ReprStr
				else:
					data[new_key] = Collection

			elif char == ">":
				if open_stack and open_stack[-1] == "<":
					open_stack.pop()
				elif open_stack and source == "details":
					open_stack.pop()
					open_stack.pop()
				else:
					raise RuntimeError(f"Invalid format, can't close '{open_stack[-1]}' with '{char}'")
				if literal:
					return literal
				else:
					raise RuntimeError("Received empty placeholder!")
			elif char == ":":
				open_stack.append(":")
				res:str = parse(it, {}, open_stack, source = "details")
				if data:
					temp = data.copy()
					data.clear()
					for key, val in temp.items():
						if ":" in key:
							temp_str = " - " + res.strip()
						else:
							temp_str = ':' + res.strip()
						data[f"{key}{temp_str}"] = val
					return data
				return literal, res
		elif char == " " and ":" not in open_stack:
			literal = ""
		else:
			literal += char
	if source == "details":
		return literal
	return data


async def add_cmd(channel, resp, data, perm, to_add):

	def is_optional(x):
		return x.get("optional") or not x.get("required")

	path = pathlib.Path(f"bot_commands/{data.command}.py")
	cmd_template = open("data/cmd_template.txt", "r").read()

	desc = to_add["desc"]
	usage = to_add["usage"]
	_to_send = '{"embed": ...}'
	_coll = "from helpers.other.collections import Collection\n"
	use_coll = False

	_typing = "import typing\n"

	if not perm:
		# try:
		usage_data = {}
		stack = []
		parse(usage, usage_data, stack)
		print(json.dumps(usage_data, indent = 2, default = lambda x: x.__name__))
		_data = reformat(usage_data)
		print(json.dumps(_data, indent = 2, default = lambda x: x.__name__))

		desc += f"\n\t{Markdown.cb('')}" + "py\n\t"
		slash_data = ReprDict()
		val: dict[str, typing.Any]
		for key, val in _data.items():
			if ":" in key:
				key, key_desc = key.split(":")
				if " - " in key_desc:
					key_desc_main, key_desc_rest = key_desc.split(' - ')
					match = re.search(f": ?{key_desc_rest}", usage)
					if match:
						print(match)
						usage = re.sub(match.group(), "", usage)
				else:
					key_desc_main = key_desc
				match = re.search(f"{key if not 'arg' in key else ''}.?( ?: ?{key_desc_main.strip()})", usage)
				if match:
					print(match)
					usage = re.sub(match.group(1), "", usage)
			else:
				key_desc = ""
			if not val.get("choice"):
				_type = val["type"]
				if _type == typing.Literal:
					if is_optional(val):
						to_put = typing.Optional[val["type"][key]]
					else:
						to_put = val["type"][key]
				elif _type.__base__ == str:
					if is_optional(val):
						to_put = typing.Optional[str]
					else:
						to_put = ReprStr
				elif _type.__base__ == int:
					if is_optional(val):
						to_put = typing.Optional[int]
					else:
						to_put = ReprInt
				elif _type == Collection:
					use_coll = True
					if is_optional(val):
						to_put = val["type"][key, None]
					else:
						to_put = val["type"][key]
				else:
					raise RuntimeError("received unsupported type; shouldn't even happen")
			else:
				val.pop("choice")
				temp = {}
				if all(map(is_optional, val.values())):
					optional = True
				elif all(map(lambda x: not is_optional(x), val.values())):
					optional = False
				else:
					raise RuntimeError("Invalid choices that shouldn't have appeared")
				_type = "str"
				for _name, _data in val.items():
					_type = _data.get("type")
					if not temp.get(_type):
						temp[_type] = [_name]
					else:
						temp[_type].append(_name)
				new_data: list = temp.pop(typing.Literal, [])
				if coll := temp.pop(Collection, None):
					use_coll = True
					if optional:
						new_data.append(None)
					new_data.extend([Collection[(x, *new_data)] for x in coll[1:]])
					new_data.append(coll[0])
					to_put = Collection[tuple(reversed(new_data))]
				else:
					to_put = typing.Literal[tuple(new_data)]
					if optional:
						to_put = typing.Optional[to_put]
				if temp:
					for _type_temp, _elements in temp.items():
						for _el in _elements:
							desc += f"{_el}: {_type_temp.__str__()}\n\t"
							match = re.search(f"{_el}( ?: ?(.*?))[>%]", usage)
							if match:
								print(match)
								desc += f"\t{match.group(2)}\n\t"
								usage = re.sub(match.group(1), "", usage)
							_to_put = _type_temp.__str__()
							if optional:
								_to_put = typing.Optional[_type_temp.__base__]
							slash_data[_el] = _to_put
			desc += f"{key}: {_type.__str__()}\n\t"
			if key_desc:
				desc += f"\t{key_desc.strip()}\n\t"
			slash_data[key] = to_put
		slash_data = f"slash_args = {slash_data.__str__()}" if slash_data else ""
		if "typing" not in slash_data:
			_typing = ""
	# except RuntimeError as e:
	# 	print(e)
	# 	slash_data = 'slash_args = {"data": typing.Optional[str]}'
	else:
		slash_data = ""

	to_add["usage"] = usage

	# print(cmd_template)
	try:
		if slash_data:
			insert = f'"{perm}", '
		else:
			insert = f'"{perm}"'
		cmd_template = cmd_template.format(
			coll = _coll if use_coll else "",
			typing = _typing,
			perm = insert,
			slash = slash_data,
			to_send = _to_send,
			cmd = data.command,
			desc = desc,
		)
		print(cmd_template)
	except KeyError as e:
		err = f'{Markdown.cb(e.__repr__())}\n{Markdown.cb("".join(traceback.format_tb(e.__traceback__)))}'
		return err
	if await approve_cmd(data.bot, data.command, cmd_template):
		open(path, "w").write(cmd_template)
		coll = db.db.get_collection(name = "Commands")
		coll.insert_one(to_add)
		bot_commands.import_cmds([data.command])
		await channel.send(embed = resp.emb_resp("New command added!"))
	else:
		await channel.send(embed = resp.emb_resp("Command wasn't approved by owner!"))


async def reaction(msg: discord.Message, target: discord.Member, bot):
	await msg.add_reaction("✅")
	await msg.add_reaction("❌")

	def check(check_reaction, check_user):
		return check_user == target and msg.id == check_reaction.message.id

	resp_reaction, user = await bot.wait_for('reaction_add', check = check)
	try:
		await msg.clear_reactions()
	except discord.Forbidden:
		pass
	return resp_reaction.emoji


async def approve(bot, embed: discord.Embed):
	owner: discord.User = bot.owner
	dm_c = owner.dm_channel

	if not dm_c:
		dm_c = await owner.create_dm()

	user = dm_c.recipient

	dm = await dm_c.send(embed = embed)
	return await reaction(dm, user, bot)


async def approve_alt(bot, cmd_name, cmd_alt):
	embed = bot.responder.emb_resp(
		f"Request to add {cmd_alt} as alias to {cmd_name}",
		color = bot.responder.info
	)
	res = await approve(bot, embed)
	return res == "✅"


async def approve_cmd(bot, new_cmd, template):
	embed = bot.responder.emb_resp(
		f"Request to add the new command {new_cmd}",
		desc = Markdown.cb("py\n" + template),
		color = bot.responder.info
	)
	res = await approve(bot, embed)
	return res == "✅"


async def cmd_adder(data: Result):
	reactions = ["✅", "❌"]
	message = data.message
	channel = data.message.channel
	client = data.bot
	resp = client.responder
	if message.author.id == data.bot.owner.id:
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

	def check_msg(message_check: discord.Message):
		return message_check.author == data.message.author and message_check.channel == data.message.channel

	async def continue_or_fail(string):
		await channel.send(string)
		try:
			_message: discord.Message = await client.wait_for("message", check = check_msg, timeout = 120)
		except TimeoutError:
			await channel.send(embed = resp.emb_resp("Timeout exceeded", "Command not added"))
			return 0
		return _message.content

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

	to_add = {
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
	return await add_cmd(channel, resp, data, perm, to_add)


async def cmd_adder_ui(data: Result):
	reactions = ["✅", "❌"]
	message = data.message
	channel = data.message.channel
	client = data.bot
	resp = client.responder

	if message.author.id == data.bot.owner.id:
		perm = helpers.other.permissions.Owner()
	# elif message.author.id == message.channel.guild.owner.id:
	# 	perm = helpers.other.permissions.Admin()
	else:
		perm = helpers.other.permissions.All()

	view = discord.ui.View(timeout = 30)
	view.add_item(discord.ui.Button(emoji = reactions[0]))
	view.add_item(discord.ui.Button(emoji = reactions[1]))

	async def timeout():
		view.stop()
		await channel.send(embed = resp.emb_resp("TIMEOUT", "COMMAND NOT ADDED", "error"), delete_after = 10)

	async def check(interaction: discord.Interaction):
		return interaction.user.id == message.author.id

	async def no(interaction: discord.Interaction):
		view.stop()
		await interaction.response.send_message(
			embed = resp.emb_resp("Command not added!", color = "info"),
			delete_after = 10
		)
		await interaction.message.delete()

	async def yes(interaction: discord.Interaction):
		view.stop()
		await interaction.message.delete()

		async def submission_handler(details: discord.Interaction):
			await details.response.send_message(embed = resp.emb_resp("Adding command!", color = "ok"))
			to_add = {
				el["components"][0]["custom_id"]: el["components"][0]["value"] for el in details.data["components"]
			}
			to_add["name"] = data.command
			to_add["aliases"] = list(filter(None, re.findall("(\w+|\d+)+", to_add["aliases"])))
			to_add["usage"] = "{prefix}" + to_add["usage"]
			to_add["usage_ex"] = "{prefix}" + (to_add["usage_ex"] or data.command)
			to_add["added_by"] = {
				"id": details.user.id,
				"name": details.user.name
			}
			to_add["added_on"] = datetime.datetime.utcnow().timestamp()
			new_perm = to_add.get("permission") or helpers.other.permissions.All()
			if new_perm:
				new_perm = getattr(
					helpers.other.permissions,
					new_perm.capitalize(),
					helpers.other.permissions.Owner
				)()
			to_add["permission"] = new_perm
			print(to_add)

			try:
				res = await add_cmd(channel, resp, data, new_perm, to_add)
			except Exception as e:
				coll = db.db.get_collection(name = "Commands")
				coll.delete_one({"name": data.command})
				await details.followup.send(
					embed = client.responder.emb_resp2(
						Markdown.cb("".join(traceback.format_tb(e.__traceback__)) + repr(e))
					)
				)
			else:
				await details.followup.send(embed = client.responder.emb_resp2(res)) if res else None

		modal = discord.ui.Modal(title = f"Info for new command\n{data.command}")
		modal.on_submit = submission_handler
		modal.add_item(discord.ui.TextInput(
			label = "Alternative Names",
			required = False,
			custom_id = "aliases"))
		modal.add_item(discord.ui.TextInput(
			label = "Description",
			required = True,
			custom_id = "desc",
			style = discord.TextStyle.long))
		modal.add_item(discord.ui.TextInput(
			label = "Usage",
			required = True,
			custom_id = "usage"))
		modal.add_item(discord.ui.TextInput(
			label = "Usage Example",
			required = False,
			custom_id = "usage_ex"))
		if perm == helpers.other.permissions.Owner:
			modal.add_item(discord.ui.TextInput(
				label = "Permissions",
				required = False,
				custom_id = "permission"))
		try:
			await interaction.response.send_modal(modal)
		except Exception as e:
			txt = f"{repr(e)}\n{''.join(traceback.format_tb(e.__traceback__))}"
			await interaction.channel.send(embed = client.responder.emb_resp2(txt))

	view.interaction_check = check
	view.on_timeout = timeout
	view.children[-2].callback = yes
	view.children[-1].callback = no
	await channel.send(
		embed = resp.emb_resp(
			f"Command {Markdown.sn(data.command)} not found!",
			"Do you want to add it?",
			color = "error"),
		view = view,
		delete_after = 40
	)
