from helpers.other.permissions import Permissions


@Permissions.register_command("owner")
async def stop(data):
	"""Stops the bot"""
	if data.bot.gui:
		data.bot.gui.fill_queue("STOP")
	if data.bot.music_player:
		data.bot.music_player.queue.put(None)
	data.bot.status_changer.stop()
	await data.bot.close()
	return data
