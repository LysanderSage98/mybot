import discord
import json

from helpers.other.permissions import Permissions

from . import Result


@Permissions.register_command("")
async def info(data: Result):
	"""shows information about the bot
	``````py
	"""
	guild = data.message.guild
	bot = data.bot
	# uptime = u.get_bot_uptime()
	embed = bot.responder.emb_resp(
		f"Bot-info",  # \n\nRunning since\n`{uptime}`",
		"```\"No purpose\"-bot\nSuggest new commands just by using them!```",
		"std_info"
	)
	user = bot.user
	embed.set_image(url = user.avatar.url)
	embed.add_field(name = "Github repository", value = "https://github.com/LysanderSage98/mybot", inline = False)
	embed.add_field(name = "Is ~~in~~active in", value = f"```{len(bot.guilds)} guilds```", inline = True)
	embed.add_field(name = "with", value = f"```{len(bot.users)} Users in total```")
	embed.add_field(name = "ID", value = f"```{user.id}```", inline = False)
	embed.add_field(name = "Created at", value = f"```{user.created_at.strftime('%D - %T')}```", inline = True)
	date = guild.get_member(user.id).joined_at.strftime("%D - %T")
	embed.add_field(name = "Joined this guild at", value = f"```{date}```")
	owner: discord.User = bot.owner
	url = owner.avatar.url
	embed.set_author(name = f"Created by {owner}", icon_url = url)
	embed.set_footer(text = f"Image source: {json.loads(open('data/info.json').read())['profile']}")
	to_send = {"embed": embed}
	return data, to_send
