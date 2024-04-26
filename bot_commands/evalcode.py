import contextlib
import discord
import io
import re

from helpers.other.permissions import Permissions

from . import Result


@Permissions.register_command("owner")
async def evalcode(data: Result):
	"""Testing"""
	
	from helpers.other.utilities import Markdown as Md

	bot = data.bot
	content = " ".join(data.args.values())[3:-3].strip("python")
	# print(content)
	x = io.StringIO()
	try:
		with contextlib.redirect_stdout(x):
			exec(content, globals(), locals())
		if x.getvalue():
			mapping = enumerate(x.getvalue().split("\n"))
			mapping = list(mapping)[:-1]
			mult = len(str(len(mapping))) + 1
			# print(mul)
			res = "\n".join(map(lambda y: f"{y[0]}.{' ' * (mult - len(str(y[0])))}|{y[1]}", mapping))
			# print(res)
			
			text = Md.cb_(f"python\n{re.sub(r'```', '', res)}")
		else:
			text = Md.sn_("Something went wrong")
	except Exception as e:
		# print(e)
		data.error = bot.responder.emb_resp("Error", str(e), "error")
		return data

	to_send = {"content": text}
	return data, to_send
