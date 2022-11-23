from helpers.other.permissions import Permissions


@Permissions.register_command("owner")
async def stop(data):
	"""Stops the bot"""
	if data.client.gui:
		data.client.gui.fill_queue("STOP")
	if data.client.music_player:
		data.client.music_player.queue.put(None)
	data.client.status_changer.stop()
	await data.client.close()
	return data
