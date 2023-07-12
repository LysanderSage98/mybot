import discord
from helpers.other.permissions import Permissions


@Permissions.register_command("")
async def invite(data):
	"""Sends an invitation link for the bot"""
	client = data.bot
	
	url = discord.utils.oauth_url(client_id = client.user.id, permissions = discord.Permissions.all())
	title = f"Invite {client.user.name}!"
	embed = data.bot.responder.emb_resp(title, "", "std_info", url)
	to_send = {"embed": embed}
	return data, to_send
