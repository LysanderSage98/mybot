import discord
import json
import traceback

import helpers.events as events
from helpers.other import responder


class Bot(discord.Client):

	def __init__(self, func, gui = None, music = None, **options):
		super().__init__(**options)
		self.restarter = func
		self.started = 0
		self.gui = gui
		self.music_player = music
		self.responder = responder.Responder()
		self.status_changer = None
		self.owner = None

		@self.event
		async def on_connect():
			print("Connected!")
			info = await self.application_info()
			self.owner = info.owner

		@self.event
		async def on_guild_join(guild):
			events.onGuildCUD.guild_handler(guild)

		@self.event
		async def on_message(message):
			if message.author == self.user:
				return
			else:
				try:
					error = await events.onMessage.message_handler(message, self)
					if not error:
						return
					else:
						await message.channel.send(embed = self.responder.emb_resp2(error))
				except Exception as e:
					print(e, e.__traceback__)

		@self.event
		async def on_private_channel_create(channel):
			await events.onChannelCUD.private_channel_handler(channel, "create")

		@self.event
		async def on_ready():
			print("BOT Ready!")
			if not self.started:
				self.started = 1
				print(self.started)
				self.status_changer = await events.onReady.ready_handler(self)

		@self.event
		async def on_resumed():
			self.restarter()

		@self.event
		async def on_typing(channel, user, when):
			events.smallStuff.typing_handler(channel, user, when, self)

		@self.event
		async def on_user_update(before, after):
	
			dm_c = self.owner.dm_channel
			
			if not dm_c:
				dm_c = await self.owner.create_dm()
			x = before.name
			y = after.name
			if x != y:
				await dm_c.send(f"{x}\n\n{(y, after.id)}")
			else:
				print("Other changes at", x, "'s profile.")

		@self.event
		async def on_voice_state_update(member, before, after):
			await events.smallStuff.voice_state_handler(member, before, after, self)

	def run(self, *args, **kwargs):
		token = json.load(open("data/info.json", "r"))["token"]
		print("bot started")
		super().run(token, *args, **kwargs)
