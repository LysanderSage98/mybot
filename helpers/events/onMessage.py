import discord
import helpers.other.utilities as u

from bot_commands import Result
from helpers.other import permissions as p
permissions = p.Permissions(Result)


async def message_handler(message: discord.Message, bot):
	result = await bot.loop.run_in_executor(None, permissions.check, message, bot)
	print(result)
	if result:
		if result.function:
			if not result.error:
				result = await result.function(result)
				print("after command execution\n", result)
				if result:
					return 0
				else:
					return result.error
			else:
				return result.error
		else:
			try:
				return await u.cmd_adder(result)
			except Exception as e:
				return e.with_traceback(e.__traceback__)
