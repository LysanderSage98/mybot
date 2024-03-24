import discord
import traceback

import helpers.other.utilities as u

from bot_commands import Result
from helpers.other import permissions as p
permissions = p.Permissions(Result)


async def message_handler(message: discord.Message, bot):
	result = await bot.loop.run_in_executor(None, permissions.validate_msg, message, bot)
	print("message handler result\n", result)
	if result:
		temp = await do_stuff(result)
		if isinstance(temp, tuple):
			res, info = temp
			await message.channel.send(**info)
		else:
			res = temp
		if not isinstance(res, Result) or result.error:
			return res


async def interaction_handler(interaction: discord.Interaction, **params):
	print(params)
	bot = interaction.client
	result = await bot.loop.run_in_executor(None, permissions.validate_interaction, interaction, bot)
	print("interaction handler input\n", result)
	if result:
		await interaction.response.defer()
		try:
			temp = await do_stuff(result)
			print("after command execution\n", result)
			if isinstance(temp, tuple):
				res, info = temp
				await interaction.followup.send(**info)
			else:
				res = temp
			if not isinstance(res, Result) or result.error:
				await interaction.followup.send(res)
		except Exception as e:
			txt = f"{repr(e)}\n{traceback.format_tb(e.__traceback__)[-1]}"
			await interaction.followup.send(embed = bot.responder.emb_resp2(txt))

	return interaction


async def do_stuff(data):
	if data.function:
		if not data.error:
			return await data.function(data)
		return data.error
	else:
		try:
			return await u.cmd_adder_ui(data)
		except Exception as e:
			return "".join(traceback.format_tb(e.__traceback__)) + repr(e)
