from bot_commands import Result
from helpers.other import permissions as p
permissions = p.Permissions(Result)


async def message_handler(message, bot):
	result = await bot.loop.run_in_executor(None, permissions.check, message, bot)
	if result:
		if result.command:
			if not result.error:
				success = await result.command(result)
				if success:
					return 0
				else:
					return success.error
			else:
				return result.error
		else:
			return "Command not found!"
