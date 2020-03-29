import discord
from helpers.other import permissions as p

permissions = p.Permissions()


@permissions.register_command()
async def invite(data):
	channel = data.message.channel
	client = data.client
	
	url = discord.utils.oauth_url(client_id = client.user.id, permissions = discord.Permissions.all())
	title = f"Invite {client.user.name}!"
	embed = data.client.responder.emb_resp(title, "", "std_info", url)
	await channel.send(embed = embed)
	return data
