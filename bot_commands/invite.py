import discord
from helpers.other.permissions import Permissions


@Permissions.register_command(None)
async def invite(data):
	"""Sends an invitation link for the bot"""
	channel = data.message.channel
	client = data.client
	
	url = discord.utils.oauth_url(client_id = client.user.id, permissions = discord.Permissions.all())
	title = f"Invite {client.user.name}!"
	embed = data.client.responder.emb_resp(title, "", "std_info", url)
	await channel.send(embed = embed)
	return data
