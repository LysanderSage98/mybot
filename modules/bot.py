import ast
import asyncio
import discord
import inspect
import json
import sys
import traceback

import helpers.events as events
import helpers.other.permissions as perms
import helpers.other.responder as r

from discord.app_commands import CommandTree, Command
from types import FunctionType
from typing import Coroutine, Any


class Bot(discord.Client):

	def __init__(self, func, responder, gui = None, music = None, **options):
		super().__init__(**options)
		self.restarter = func
		self.started = 0
		self.gui = gui
		self.music_player = music
		self.responder: r.Responder = responder
		self.status_changer = None
		self.owner = None
		self.perms = perms.Permissions
		self.cmd_tree = CommandTree(self)
		func_orig = events.onMessage.interaction_handler
		temp = inspect.getsource(func_orig)
		tree = ast.parse(temp)
		del tree.body[0].args.kwarg
		func_template = compile(tree, func_orig.__module__, "exec").co_consts[1]
		self._interaction_handler = (func_orig, func_template)
		self.prefix = json.load(open("data/info.json", "r"))["prefix"]
		asyncio.run(self.grow_app_commands())

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
			if message.author != self.user:
				try:
					error = await events.onMessage.message_handler(message, self)
					if error:
						await message.channel.send(embed = self.responder.emb_resp2(error))
				except Exception as e:  # TODO change to show details only in owner DM
					print("".join(traceback.format_tb(e.__traceback__)), repr(e), file = sys.stderr)
					txt = f"{repr(e)}\n{traceback.format_tb(e.__traceback__)[-1]}"
					await message.channel.send(embed = self.responder.emb_resp2(txt))

		@self.event
		async def on_interaction(interaction: discord.Interaction):
			print("in event on interaction", interaction.data.get("options"))

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
			pass  # todo
			# self.restarter()

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
				await dm_c.send(f"old: {x}\n\nnew: {(y, after.id)}")
			else:
				print("Other changes at", x, "'s profile.")

		@self.event
		async def on_voice_state_update(member, before, after):
			await events.smallStuff.voice_state_handler(member, before, after, self)

	async def sync_app_commands(self, guild: discord.Guild = None):
		# await self.cmd_tree.sync(guild = self.get_guild(465572225173684225))
		await self.cmd_tree.sync(guild = guild)

	async def grow_app_commands(self, guild: discord.Guild = None):
		for name, data in perms.commands.items():
			if not data[1]:
				await self.add_app_command(name, data, guild)

	async def add_app_command(
		self,
		name: str,
		data: tuple[Coroutine, perms.PermHierarchy, dict[str, Any]],
		guild: discord.Guild = None):
		new = self._interaction_handler[1].replace(
			co_name = name,
			co_argcount = 1,
			co_kwonlyargcount = len(data[2]),
			co_varnames = ("interaction", *data[2].keys()),
		)
		f = FunctionType(
			new,
			self._interaction_handler[0].__globals__,
			name
		)
		data[2]["interaction"] = discord.Interaction
		f.__annotations__ = data[2]  # kwargs getting added here
		try:
			f.__doc__ = data[0].__doc__.split("``````py", 1)[1]
		except IndexError:
			pass

		if data[1] == perms.Admin():
			f.__discord_app_commands_default_permissions__ = discord.Permissions()

		cmd = Command(
			name = name,
			description = data[0].__doc__.splitlines()[0],
			callback = f
		)
		cmd._callback = self._interaction_handler[0]
		self.cmd_tree.add_command(cmd, override = True, guild = guild)

	def run(self, *args, **kwargs):
		token = json.load(open("data/info.json", "r"))["token2"]
		print("bot started")
		super().run(token, *args, **kwargs)
