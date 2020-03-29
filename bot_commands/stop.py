from helpers.other import permissions as p

permissions = p.Permissions()


@permissions.register_command("owner")
async def stop(data):
	"""Stops the bot"""
	if data.client.gui:
		data.client.gui.fill_queue("STOP")
	data.client.status_changer.stop()
	await data.client.logout()
	return data
