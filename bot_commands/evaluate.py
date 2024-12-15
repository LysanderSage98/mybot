import asyncio
import discord
import pydoc
import re
import typing

from helpers.other.permissions import Permissions, db

from . import Result


@Permissions.register_command("owner")
async def evaluate(data: Result):
	"""execute single line of py code"""
	author = data.message.author
	channel = data.message.channel
	bot = data.bot
	message = data.message
	args = data.args.values()
	r = bot.responder
	
	def python(py_args):
		py_args = (re.search(r"\(.*\)", py_args).group()[1:-1])
		return py_args
	
	args = " ".join(args)
	# print(type(args), args)
	
	if "help" in args:
		try:
			x = python(args)
			y = pydoc.getdoc(eval(x))
			return await channel.send(embed = r.emb_resp(f"Help for {x}", f"```python\n{y}```", "success"))
		except Exception as e:
			return await channel.send(embed = r.emb_resp("Failure", f"```{str(e)}```", "error"))
	
	try:
		x = await eval(args)
	
	except Exception as e:
		print(e)
		
		try:
			y = eval(args)
			
			if asyncio.iscoroutine(y):
				return await channel.send(embed = r.emb_resp("Failure", f"```{str(y)}```", "error"))
			else:
				return await channel.send(embed = r.emb_resp("Success", f"```{str(y)}```", "success"))
		
		except Exception as e:
			print(e)
			return await channel.send(embed = r.emb_resp("Failure", f"```{str(e)}```", "error"))
	
	await channel.send(embed = r.emb_resp("Success", f"```{str(x)}```", "success"))
	
	# to_send = {"content": text}
	# return data, to_send
