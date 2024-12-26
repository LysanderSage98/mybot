import asyncio.exceptions
import inspect
import math
import sys
import traceback

import discord
import typing
import re

import helpers.other.utilities as u

from . import Result, music_instances, youtube
from datetime import timedelta
from helpers.other.permissions import Permissions, db
from modules import music as m


def get_instance(channel, bot, vc, author):
	if not vc:
		return None
	_id = vc.id
	if not (instance := music_instances.get(_id)):
		instance = MusicCommands(channel, bot, vc, author)
		music_instances[_id] = instance
	else:
		instance.author = author
	return instance


def get_arg(i: int, val: str, d: dict):
	idx = str(i)
	temp = d.pop(
		val,
		d.pop(idx) if d.get(idx) == val else "")
	if temp:
		i += 1
	return i, temp


class MusicCommands:
	def __init__(self, channel, bot, vc, author):
		self.md = u.Markdown
		self.author = author
		self.channel: discord.TextChannel = channel
		self.bot = bot
		self.vc: discord.VoiceChannel = vc
		self.voice_client: discord.VoiceClient = ...

	async def _try_join(self):
		if self.voice_client == Ellipsis or self.voice_client.channel != self.vc:
			print("Connecting")
			self.voice_client = await self.vc.connect(cls = m.VoiceClientCopy)
			print("Connected as", self.voice_client)
			embed = self.bot.responder.emb_resp("Joining", self.vc.mention, "info")
			return embed

	async def call_func(self, func: str, msg = None, **kwargs):
		try:
			to_call = self.__getattribute__(func)
		except AttributeError:
			return self.bot.responder.emb_resp2(f"**'{func}' is not implemented!**")
		args = inspect.getfullargspec(to_call)
		print(args)
		if args.varkw:
			print(to_call, kwargs)
			if args.kwonlyargs:
				kwargs.update({"msg": msg})
			return await to_call(**kwargs)
		else:
			print(to_call)
			return await to_call()

	async def deletesong(self, **kwargs):
		player = m.Player.get_player(self.channel.guild.id)
		# noinspection PyTypeChecker
		search = kwargs.get(
			"search",
			" ".join(list(kwargs.values())[1:]) if not kwargs.get("arg0") else ""
		)
		playlist_arg = re.search("--(.*)", search)
		if playlist_arg:
			playlist_name = playlist_arg.group(1)
			search = re.sub(playlist_arg.group(), "", search)
		else:
			playlist_name = ""

		numbers = re.findall(r"\d+", search)
		if len(numbers) in (2, 3):
			number = slice(*[int(x) for x in numbers])
		elif numbers:
			number = int(numbers[0])
		else:
			res = player.find_by_name(search, multi = True)
			print(res)
			if res and len(res) > 1:
				number = res
			elif res:
				number = res[0]
			else:
				number = None

		if number:
			response = player.edit_queue(self.channel.guild.id, number, keep = False, playlist = playlist_name)

		else:
			res = player.del_current(playlist = playlist_name)
			response = ["Removed", f"{self.md.cb_(res['data']['title'])}", "success"]
		embed: discord.Embed = self.bot.responder.emb_resp(*response)
		desc = embed.description

		if len(desc) > 2048:
			embed.description = desc[:re.search("-", desc, 2000).start()] + "\n..."

		return embed

	async def join(self):
		if not (embed := await self._try_join()):
			embed = self.bot.responder.emb_resp("Already in the same channel!", color = "info")
		return embed

	async def loop(self, **kwargs):
		loop = kwargs.get(
			"loop",
			kwargs.get("1", "all")
		)
		res = m.Player.set_loop(self.channel.guild.id, loop)
		if loop == "stop":
			embed = self.bot.responder.emb_resp("Loop disabled!", color = "success")
		elif not res:
			embed = self.bot.responder.emb_resp("Loop enabled!", color = "success")
		else:
			embed = self.bot.responder.emb_resp2(res)
		return embed

	async def move(self, **kwargs):
		pass  # todo

	async def _merge_queues(self, source: int, dest: int):
		res = m.Player.merge_queues(self.channel.guild.id, source, dest)
		if not res:
			return self.bot.responder.emb_resp("No player found")
		elif res == -1:
			return self.bot.responder.emb_resp("No matching queues found")
		return self.bot.responder.emb_resp(f"Merged queues {source} and {dest}!", "Finishing to play the current track", color = self.bot.responder.success)
	
	async def nowplaying(self):
		coll = db.db.get_collection("Playlists")
		data = m.Player.get_current(self.channel.guild.id)
		if not data:
			return self.bot.responder.emb_resp("Error", "No info found!", "error_2")

		time_passed_info = data.get("passed")
		time_passed = timedelta(seconds = time_passed_info)
		final = f"[{data['title']}]({data['link']})"
		thumbnail = data['thumbnail']

		passed = {
			"name": "Time passed since start",
			"value": self.md.cb_(time_passed),
			"inline": False
		}
		dur = {
			"name": "Duration",
			"value": self.md.cb_(data['duration']),
			"inline": False
		}
		ffmpeg_info = data["ffmpeg_options"]
		embed: discord.Embed = self.bot.responder.emb_resp("Currently playing", final, "success")
		embed.add_field(**passed).add_field(**dur)
		if ffmpeg_info and list(filter(lambda x: x[1], ffmpeg_info)):
			times = ffmpeg_info[1][1]
			starting_point = re.search(r"-ss (\S*)", times).group(1)
			ending_point = re.search(r"-to (\S*)", times).group(1)
			start = {
				"name": "Starting point in the track",
				"value": self.md.cb_(starting_point)
			}
			end = {
				"name": "Ending point in the track",
				"value": self.md.cb_(ending_point)
			}
			embed.add_field(**start).add_field(**end)
		if thumbnail:
			embed.set_thumbnail(url = thumbnail)

		embed.add_field(name = "Buffer progress", value = data["buffer_status"])
		
		async def check(interaction: discord.Interaction):
			return interaction.user == self.author
		
		async def timeout():
			view.stop()
			view.clear_items()
		
		view = discord.ui.View(timeout = 60)
		view.add_item(discord.ui.Button(emoji = "➕"))
		view.add_item(discord.ui.Button(emoji = "➖"))
		
		async def modify(interaction: discord.Interaction, _add: bool):
			view.stop()
			
			async def handler(details: discord.Interaction):
				playlist_name = details.data["components"][0]["components"][0]["value"]
				user = details.user
				if _add:
					response = f"Added{data['title']} to playlist {self.md.sn_(playlist_name)}!"
					coll.update_one(
						{
							"user": user.id,
							"name": playlist_name
						}, {
							"$addToSet": {
								"songs": (data["link"], data["title"], data["duration"].total_seconds())
							}
						}, upsert = True
					)
				else:
					response = f"Removed {data['title']} from playlist {self.md.sn_(playlist_name)}"
					coll.update_one(
						{
							"user": user.id,
							"name": playlist_name
						}, {
							"$pull": {
								"songs": {
									"$elemMatch": {
										"$in": [data["link"]]
									}
								}
							}
						}, upsert = True
					)
			
				emb = self.bot.responder.emb_resp("Info", response, "success")
				await details.response.send_message(embed = emb, ephemeral = True)
				await interaction.message.delete()
			
			modal = discord.ui.Modal(title = "Add song to playlist" if _add else "Remove song from playlist")
			modal.on_submit = handler
			modal.add_item(discord.ui.TextInput(
				label = "Name of the playlist you want to modify",
				required = True))
			try:
				await interaction.response.send_modal(modal)
			except Exception as e:
				txt = f"{repr(e)}\n{''.join(traceback.format_tb(e.__traceback__))}"
				await interaction.channel.send(embed = self.bot.responder.emb_resp2(txt))
				await interaction.message.delete()
		
		async def add(interaction):
			await modify(interaction, True)

		async def remove(interaction):
			await modify(interaction, False)
		
		view.interaction_check = check
		view.on_timeout = timeout
		view.children[-2].callback = add
		view.children[-1].callback = remove
		await self.channel.send(embed = embed, view = view, delete_after = 60)
	
	async def pause(self):
		if not self.voice_client.is_paused():
			embed = self.bot.responder.emb_resp("Paused!")
			self.voice_client.pause()
		else:
			embed = self.bot.responder.emb_resp("Resumed!")
			self.voice_client.resume()
		return embed

	async def play(self, **kwargs):
		print(self.voice_client)
		if embed := await self._try_join():
			await self.channel.send(embed = embed)
		print(self.voice_client)

		msg = await self.channel.send(embed = self.bot.responder.emb_resp("Searching!", "", "info"))
		idx = 1
		res = []
		for el in ["new", "playlist", "stored", "shuffle"]:
			idx, temp = get_arg(idx, el, kwargs)
			res.append(temp)
		
		new, playlist, stored, shuffle = res
		
		# noinspection PyTypeChecker
		search = kwargs.get(
			"search",
			" ".join(list(kwargs.values())[1:]) if not kwargs.get("arg0") else ""
		)
		print(playlist, stored, search)

		play_all = ""

		if not stored and search and "youtu" not in search:
			print(search, playlist)
			request = youtube.search().list(
				part = "snippet",
				q = search,
				type = "video" if not playlist else "playlist"
			)
			response = request.execute()
			if playlist:
				_type = ("list", "playlist")
			else:
				_type = ("v", "video")

			url = u.to_yt_url(_type[0], response["items"][0]["id"][f"{_type[1]}Id"])
			res = f"Found {_type[1]}!\n"
			msg = await self.channel.send(res + url)

		elif not stored:
			if not playlist and (video_id := re.search(r"(v=|be/)(.*?)([\s?&]|$)", search)):
				video_id = video_id.group(2)
				url = u.to_yt_url("v", video_id)
			elif playlist_id := re.search(r"(list=|be/)(.*?)([\s?&]|$)", search):
				playlist_id = playlist_id.group(2)
				url = u.to_yt_url("list", playlist_id)
			else:
				url = "None"

		else:
			url = "None"
			play_all = search or "default"

		data = {
			"url": url,
			"bot": self.bot,
			"channel": self.channel,
			"guild": self.channel.guild,
			"author": self.author,
			"v_c": self.voice_client,
			"loop": self.bot.loop,
			"play_all": play_all,
			"msg": msg,
			"type": "default",
			"sh": shuffle,
			"new": True if new else False
		}
		m.MusicManager.put(data)

		return self.bot.responder.emb_resp("Trying to play", search, color = "info")

	async def queue(self, *, msg = None, **kwargs):
		res = m.Player.get_queue_info(self.channel.guild.id)
		if not res:
			return self.bot.responder.emb_resp("No queue found")
		all_items, loop_value = res
		if not all_items:
			return self.bot.responder.emb_resp("Queue is empty")

		def transform(data: dict):
			return f"{data['title']}, ({data['duration']})"

		current = all_items[0]
		current = transform(current)
		items = all_items[1:]
		durations = map(lambda x: x["duration"].seconds, items)
		queue_duration = timedelta(seconds = sum(durations))
		count = 0

		def get_short():
			return items[count * 10:(count + 1) * 10]

		async def embed(lis):
			try:
				text = list(map(lambda x: f"\n[{x[0] + count * 10}] {transform(x[1])}", enumerate(lis, start = 1)))
				q = f"{discord.utils.escape_markdown(''.join(text))}"
				emb: discord.Embed = self.bot.responder.emb_resp(f"Page {count + 1}/{math.ceil(len(items) / 10) or 1}")
				emb.set_author(name = f"Size: {len(items)} + 1")
				emb.add_field(name = "Currently Playing", value = f"[0] {current}", inline = False)
				emb.add_field(name = f"Queue ({queue_duration})", value = q, inline = False) if q else None
				emb.set_footer(text = f"🔁 Loop: {loop_value}")
			except Exception as embed_error:
				print("".join(traceback.format_tb(embed_error.__traceback__)), repr(embed_error), file = sys.stderr)
				txt = f"{repr(embed_error)}\n{traceback.format_tb(embed_error.__traceback__)[-1]}"
				return self.bot.responder.emb_resp2(txt)
			return emb

		try:
			if isinstance(msg, discord.Interaction):
				msg = await msg.followup.send(embed = await embed(get_short()))
			else:
				msg = await self.channel.send(embed = await embed(get_short()))
		except Exception as e:
			print(e)
			return self.bot.responder.emb_resp2("Can't fit the queue in one message, something went wrong")

		if len(items) > 10:
			await msg.add_reaction("⬅️")
			await msg.add_reaction("➡️")

		await msg.add_reaction("➕")

		def check1(check_reaction, check_user):
			return check_user == self.author and check_reaction.message.id == msg.id

		def check2(check_message: discord.Message):
			c_1 = check_message.author == self.author
			c_2 = check_message.channel == self.channel
			c_3 = not check_message.content.startswith(self.bot.prefix)
			return c_1 and c_2 and c_3

		while True:
			response = None
			toggle = False
			try:
				reaction, user = await self.bot.wait_for("reaction_add", check = check1, timeout = 60.0)
			except asyncio.exceptions.TimeoutError:
				break

			if reaction.emoji == "➡️":
				toggle = True
				count += 1
				if count >= (math.ceil(len(items) / 10)):
					count = 0

			elif reaction.emoji == "⬅️":
				toggle = True
				count -= 1
				if count < 0:
					count = math.ceil(len(items) / 10) - 1

			elif reaction.emoji == "➕":
				coll = db.db.get_collection("Playlists")
				toggle = False
				info_msg = await self.channel.send("Type the name of the playlist you wish to add the queue to!")
				try:
					playlist_name_msg: discord.Message = await self.bot.wait_for("message", check = check2, timeout = 60.0)
					playlist_name = playlist_name_msg.content
					await playlist_name_msg.delete(delay = 20.0)
					await info_msg.delete(delay = 20.0)
				except asyncio.exceptions.TimeoutError:
					await info_msg.edit(content = "Timed out!")
					await info_msg.delete(delay = 20.0)
					continue
				response = f"Added the current queue to the playlist `{playlist_name}`!"
				coll.find_one_and_update(
					{
						"user": user.id,
						"name": playlist_name
					}, {
						"$addToSet": {
							"songs": {
								"$each": [(item["link"], item["title"]) for item in all_items]
							}
						}
					}, upsert = True
				)
			if response:
				await self.channel.send(embed = self.bot.responder.emb_resp("Info", response, "success"),
										delete_after = 10.0)
				continue
			if toggle:
				await msg.edit(embed = await embed(get_short()))
		await msg.clear_reactions()
	
	async def queues(self, *, msg = None, **kwargs):
		merge = kwargs.get("merge_src", int(kwargs.get("1", 0))), kwargs.get("merge_dst", int(kwargs.get("2", 0)))
		if all(merge):
			return await self._merge_queues(*merge)
		switch = kwargs.get("switch", int(kwargs.get("1", 0)))
		if switch:
			return await self._switch_queue(switch)
		res = m.Player.get_queues_info(self.channel.guild.id)
		if not res:
			return self.bot.responder.emb_resp("No player found")
		all_queues, queue = res
		
		def transform(*data):
			return f"Queue: {data[0]}, Track-Count: {data[1]}"
		
		current = transform(queue, all_queues.pop(queue))
		items = list(all_queues.items())
		count = 0
		
		def get_short():
			return items[count * 10:(count + 1) * 10]
		
		async def embed(lis):
			try:
				text = "".join(map(lambda x: f"\n{transform(*x)}", lis))
				emb: discord.Embed = self.bot.responder.emb_resp(f"Page {count + 1}/{math.ceil(len(items) / 10) or 1}")
				emb.set_author(name = f"Queues: {len(items)} + 1")
				emb.add_field(name = "Current", value = current, inline = False)
				emb.add_field(name = "Other Queues", value = text, inline = False) if text else None
			except Exception as embed_error:
				print("".join(traceback.format_tb(embed_error.__traceback__)), repr(embed_error), file = sys.stderr)
				txt = f"{repr(embed_error)}\n{traceback.format_tb(embed_error.__traceback__)[-1]}"
				return self.bot.responder.emb_resp2(txt)
			return emb
		
		try:
			if isinstance(msg, discord.Interaction):
				msg = await msg.followup.send(embed = await embed(get_short()))
			else:
				msg = await self.channel.send(embed = await embed(get_short()))
		except Exception as e:
			print(e)
			return self.bot.responder.emb_resp2("Can't fit the queue in one message, something went wrong")
		
		if len(items) > 10:
			await msg.add_reaction("⬅️")
			await msg.add_reaction("➡️")
		
		def check(check_reaction, check_user):
			return check_user == self.author and check_reaction.message.id == msg.id
		
		while True:
			toggle = False
			try:
				reaction, user = await self.bot.wait_for("reaction_add", check = check, timeout = 60.0)
			except asyncio.exceptions.TimeoutError:
				break
			
			if reaction.emoji == "➡️":
				toggle = True
				count += 1
				if count >= (math.ceil(len(items) / 10)):
					count = 0
			
			elif reaction.emoji == "⬅️":
				toggle = True
				count -= 1
				if count < 0:
					count = math.ceil(len(items) / 10) - 1
			
			if toggle:
				await msg.edit(embed = await embed(get_short()))
		await msg.clear_reactions()
	
	async def _switch_queue(self, queue_id):
		res = m.Player.switch_queues(self.channel.guild.id, queue_id)
		if not res:
			return self.bot.responder.emb_resp("No player found")
		elif res == -1:
			return self.bot.responder.emb_resp("No matching queue found")
		return self.bot.responder.emb_resp(f"Switched to queue {queue_id}!", color = self.bot.responder.success)
	
	async def seek(self, *, msg = None, **kwargs):
		amount = int(kwargs.get("seek", kwargs.get("1", 0)))
		m.Player.get_player(self.channel.guild.id).seek(amount)
		await msg.delete()

	async def skip(self, **kwargs):
		amount = kwargs.get("skip", kwargs.get("1"))
		if not amount:
			self.voice_client.stop()
			return self.bot.responder.emb_resp("Skipped 1 song!")

		try:
			amount = int(amount)
		except ValueError:
			pass

		res = m.Player.skip(self.channel.guild.id, amount)
		if not res:
			embed = self.bot.responder.emb_resp("Can't skip!", "no music player found", "error_2")
		else:
			embed = self.bot.responder.emb_resp(*res)
		return embed

	async def showplaylist(self, *, msg = None, **kwargs):
		bot = self.bot
		channel = self.channel
		author = self.author
		coll = db.db.get_collection("Playlists")
		playlists = list(coll.find({"user": author.id}))
		args = kwargs.get("search", "").split() or list(kwargs.values())[1:]

		if not args:
			playlist_type = "all"
			title = f"Showing all playlists ({len(playlists)} in total)"
		else:
			playlist_type = " ".join(args)
			title = f"Showing playlist `{playlist_type}`"

		color = "info"

		def clean(data: list):
			return "- " + "\n- ".join(data) if data else "Empty"

		if not playlists:
			return bot.responder.emb_resp("Error", "You don't have any playlist registered yet!", "error")

		if playlist_type == "all":
			playlist_data = list(map(lambda x: f"{x['name']} ({len(x['songs'])} songs)", playlists))
		else:
			playlist_data = coll.find_one({"user": author.id, "name": playlist_type})
			if playlist_data:
				playlist_data = list(map(lambda x: x[1], playlist_data["songs"]))
			else:
				return bot.responder.emb_resp("Error", f"Playlist {playlist_type} couldn't be found!", "error")

		if len(playlist_data) < 10:
			return bot.responder.emb_resp(title, clean(playlist_data), color)

		page = 0

		def edit_embed(emb):
			emb.description = clean(playlist_data[page * 10:(page + 1) * 10])
			emb.set_author(name = f"{page + 1}/{math.ceil(len(playlist_data) / 10) or 1}")
			return emb

		embed = bot.responder.emb_resp(title, "", color)
		if isinstance(msg, discord.Interaction):
			msg = await msg.followup.send(embed = edit_embed(embed))
		else:
			msg = await channel.send(embed = edit_embed(embed))

		await msg.add_reaction("⬅️")
		await msg.add_reaction("➡️")

		def check(check_reaction, check_user):
			return check_user == author and check_reaction.message.id == msg.id

		while True:
			try:
				reaction, user = await bot.wait_for("reaction_add", check = check, timeout = 60.0)
			except asyncio.exceptions.TimeoutError:
				break

			if reaction.emoji == "➡️":
				page += 1
				if page >= (math.ceil(len(playlist_data) / 10)):
					page = 0

			elif reaction.emoji == "⬅️":
				page -= 1
				if page < 0:
					page = math.ceil(len(playlist_data) / 10) - 1

			await msg.edit(embed = edit_embed(embed))
		await msg.clear_reactions()

	async def shuffle(self):
		m.Player.shuffle(self.channel.guild.id)
		return self.bot.responder.emb_resp("🔀 Queue shuffled!")

	async def stop(self):
		if self.voice_client != Ellipsis:
			await m.MusicManager.stop(str(self.channel.guild.id))
			self.voice_client.stop()
			await self.voice_client.disconnect(force = True)
			embed = self.bot.responder.emb_resp("Left voice channel", color = "info")
			music_instances.pop(self.vc.id)
		else:
			embed = self.bot.responder.emb_resp("Error!!", "I am not connected to any voice channel!", "error")

		return embed


@Permissions.register_command(
	"",
	slash_args = {
		"arg0": typing.Optional[typing.Literal[
			'play',
			'pause',
			'skip',
			'shuffle',
			'loop',
			'move',
			'stop',
			'join',
			"queue",
			"queues",
			"deletesong",
			"showplaylist",
			"seek"
		]],
		"playlist": typing.Optional[typing.Literal['playlist']],
		"skip": typing.Optional[int],
		"loop": typing.Optional[str],
		"src": typing.Optional[int],
		"dst": typing.Optional[int],
		"switch": typing.Optional[int],
		"seek": typing.Optional[int],
		"stored": typing.Optional[typing.Literal['stored']],
		"shuffle": typing.Optional[typing.Literal['shuffle']],
		"new": typing.Optional[typing.Literal["new"]],
		"merge_src": typing.Optional[int],
		"merge_dst": typing.Optional[int],
		"search": typing.Optional[str]
	}
)
async def music(data: Result):
	"""music functionalities
	``````py
	arg0: typing.Literal
		functionality
	playlist: typing.Literal
		search query will be a playlist - only used with 'play' functionality
	skip: int
		amount of songs to skip - only used with 'skip' functionality
	loop: str
		loop setting - only used with 'loop' functionality
	src: int
		current song position - only used with 'move' functionality
	dst: int
		target song position - only used with 'move' functionality
	switch: int
		the id of the queue you want to switch to - only used with 'queues' functionality
	seek: int
		the amount of seconds to skip for- or backward in the current track - only used with 'seek' functionality
	stored: typing.Literal
		do not search for playlist name on youtube, use a saved one in the bot - only used with 'play' functionality
	shuffle: typing.Literal
		auto-shuffle the registered playlist that you are about the add - only used with 'play' functionality
	new: typing.Literal
		make a new queue and add to that one - only used with 'play' functionaliry
	merge_src: int
		source for merging two queues - only used with 'queues' functionality
	merge_dst: int
		destination for merging two queues - only used with 'queues' functionality
	search: str
		song-link or playlist-link / -name – used with 'play' and 'showplaylist' functionality
	"""
	channel = data.message.channel
	bot = data.bot
	author: discord.Member |discord.User = data.user[0]
	args: dict[str | int, typing.Any] = data.args

	vc: discord.VoiceChannel = getattr(author.voice, "channel", None)
	func = args.get("arg0", args.get("0", ""))
	music_commands = get_instance(channel = channel, bot = bot, vc = vc, author = author)
	
	# args.update({"msg": data.message})

	if func:
		if vc:
			embed = await music_commands.call_func(func, msg = data.message, **args)
		else:
			embed = bot.responder.emb_resp("You aren't connected to a voice channel!", color = "error")

	else:  # TODO implement music UI thingy
		raise RuntimeError("__**UI based player not implemented yet!**__")

	to_send = {
		"embed": embed
	}
	return (data, to_send) if embed else data
