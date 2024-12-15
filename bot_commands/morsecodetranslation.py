import discord
import re
import typing

from helpers.other.permissions import Permissions, db

from . import Result


@Permissions.register_command("", slash_args = {"arg0": typing.Literal['translate', 'replacements'], "text": typing.Optional[str]})
async def morsecodetranslation(data: Result):
	"""Encrypts a message into morsecode or decrypts a message given in morsecode
	``````py
	arg0: typing.Literal
	text: str
		only used with translate option
	"""
	channel: discord.TextChannel = data.message.channel
	bot = data.bot
	args = data.args
	arg = args.pop("arg0", args.pop("0", ""))
	
	coll = db.db.get_collection("MorseConversions")
	encrypt = coll.find_one({"name": "encrypt"})["data"]
	decrypt = coll.find_one({"name": "decrypt"})["data"]
	
	if arg == "replacements":
		embed = bot.responder.emb_resp("Replacable characters", "", "std_info")
		embed.add_field(name = "Encryption", value = "```python\n\"" + "\"; \"".join(encrypt.keys()) + "\"```")
		embed.add_field(name = "Decryption", value = "```python\n\"" + "\"; \"".join(decrypt.keys()) + "\"```")
	elif arg == "translate":
		text = args.get(
			"text",
			" ".join(args.values()) if not args.get("arg0") else ""
		).replace("/", " /").split()
		
		if text and any(filter(lambda part: part in decrypt, text)):
			sub = "(" + " )|(".join(decrypt.keys()) + " )"
			sub = sub.replace(".", "\.")
			enc = False
		else:
			keys = list(encrypt.keys())
			special = keys.pop(keys.index("-"))
			sub = "[" + "".join(keys) + special + "]"
			enc = True
		
		if enc:
			replace = encrypt
		else:
			replace = decrypt
		
		embed = bot.responder.emb_resp(f"Result of {'Encryption' if enc else 'Decryption'}", "", "success")
		
		text = " ".join(text).upper()
		desc = re.sub(sub, lambda x: replace[x.group()] if enc else replace[x.group().strip()], text + " ")
		desc = re.sub("/ *", " ", desc) if not enc else desc
		embed.description = f'```{desc}```'
		
		if enc:
			txt = f"Not the expected result? Take a look at the replacement-table with: {bot.prefix}morse replacements!"
			embed.set_footer(text = txt)
	else:
		data.error = bot.responder.emb_resp("Error", "No valid argument given!", bot.responder.error)
		return data

	to_send = {"embed": embed}
	return data, to_send
