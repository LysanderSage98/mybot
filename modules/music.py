import asyncio
import datetime
import discord
import googleapiclient.discovery
import json
import logging
import queue
import random
import re
import shlex
import subprocess
import sys
import time
import threading
import traceback
import zlib

from collections import deque
from typing import List

import helpers.other.db_stuff as db
import helpers.other.utilities as u
import yt_dlp as ytdl

log = logging.getLogger(__name__)


class BufferedQueue:
	
	def __init__(self):
		self._pos = 0
		self._frame_length = 0.02
		self._queue = deque()
		self._mutex = threading.Lock()
		self._not_empty = threading.Condition(self._mutex)
		self._not_full = threading.Condition(self._mutex)
	
	@property
	def pos(self):
		return int(self._pos * self._frame_length)
	
	def clear(self):
		self._queue.clear()
	
	def qsize(self):
		return len(self._queue)
	
	def put(self, item):
		with self._not_full:
			compressed = zlib.compress(item)
			self._queue.append(compressed)
			self._not_empty.notify()
	
	def get(self):
		with self._not_empty:
			while self._pos >= self.qsize():
				self._not_empty.wait()
			item = self._queue[self._pos]
			self._pos += 1
			return zlib.decompress(item)
	
	def seek(self, duration):
		new_pos = self._pos + int(duration / self._frame_length)
		fixed_pos = min(max(0, new_pos), self.qsize())
		# print(self._pos, new_pos, fixed_pos, self._qsize())
		with self._mutex:
			self._pos = fixed_pos
			

class FFmpegPCMAudioCopy(discord.FFmpegAudio):
	# Original code from discord.py library
	
	def __init__(self, source, *, pipe = False, stderr = None, before_options = None, options = None):
		args = []
		subprocess_kwargs = {'stdin': source if pipe else subprocess.DEVNULL, 'stderr': stderr}
		self.ret = True
		self.buffer = BufferedQueue()
		self.allow_read = threading.Lock()
		self.done = False
		if isinstance(before_options, str):
			args.extend(shlex.split(before_options))
		
		args.append('-i')
		args.append('-' if pipe else source)
		args.extend(('-f', 's16le', '-ar', '48000', '-ac', '2'))
		
		if isinstance(options, str):
			args.extend(shlex.split(options))
		
		args.append('pipe:1')
		executable = 'ffmpeg'
		super().__init__(source, executable = executable, args = args, **subprocess_kwargs)
	
	def read(self):
		while self.ret:
			with self.allow_read:
				if not self.ret:
					break
				self.ret = self._stdout.read(discord.opus.Encoder.FRAME_SIZE)
				# print(self.ret)
				if len(self.ret) != discord.opus.Encoder.FRAME_SIZE:
					self.buffer.put(self.ret)
					self.ret = b''
				self.buffer.put(self.ret)
		self.done = True
			
	def is_opus(self):
		return False
	
	def cleanup(self):
		proc = self._process
		if proc is None:
			return
		
		log.info('Preparing to terminate ffmpeg process %s.', proc.pid)
		
		try:
			proc.kill()
		except Exception as e:
			print(e)
			log.exception("Ignoring error attempting to kill ffmpeg process %s", proc.pid)
		
		if proc.poll() is None:
			log.info('ffmpeg process %s has not terminated. Waiting to terminate...', proc.pid)
			proc.communicate()
			log.info('ffmpeg process %s should have terminated with a return code of %s.', proc.pid, proc.returncode)
		else:
			log.info('ffmpeg process %s successfully terminated with return code of %s.', proc.pid, proc.returncode)
		self.buffer.clear()
		print("buffer cleared")
		self.buffer = self._process = self._stdout = None


class AudioPlayer(threading.Thread):
	# Original code from discord.py library
	
	DELAY = discord.opus.Encoder.FRAME_LENGTH / 1000.0
	
	def __init__(self, source, bot, *, after = None):
		threading.Thread.__init__(self)
		self.daemon = True
		self.bot = bot
		self.after = after
		self.reader = None
		
		self._source: FFmpegPCMAudioCopy = source
		self._end = threading.Event()
		self._resumed = threading.Event()
		self._resumed.set()  # we are not paused
		self._current_error = None
		self._connected = getattr(bot, "_connected")
		self._lock = threading.Lock()
		
		self.loops = 0
		self._start = None
		
		if after is not None and not callable(after):
			raise TypeError('Expected a callable for the "after" parameter.')
	
	def _do_run(self):
		self.loops = 0
		self._start = time.perf_counter()
		
		# getattr lookup speed ups
		play_audio = self.bot.send_audio_packet
		self._speak(True)
		
		while not self._end.is_set():
			# are we paused?
			if not self._resumed.is_set():
				# wait until we aren't
				self._resumed.wait()
				continue
			
			# are we disconnected from voice?
			if not self._connected.is_set():
				print(self, "waiting for connection")
				# wait until we are connected
				self._connected.wait()
				print(self, "connected")
				if not self.is_paused():
					self.resume()
				# reset our internal data
				# self.loops = 0
				# self._start = time.perf_counter()
			
			self.loops += 1
			data = self._source.buffer.get()

			if not data:
				self.stop()
				break
			
			play_audio(data, encode = not self._source.is_opus())
			next_time = self._start + self.DELAY * self.loops
			delay = max(0, self.DELAY + (next_time - time.perf_counter()))
			# print(delay)
			time.sleep(delay)
	
	def run(self):
		try:
			self.reader = threading.Thread(target = self._source.read)
			self.reader.start()
			self._do_run()
		except Exception as exc:
			self._current_error = exc
			self.stop()
		finally:
			self._source.cleanup()
			self._call_after()
	
	def _call_after(self):
		error = self._current_error
		
		if self.after is not None:
			try:
				self.after(error)
			except Exception as exc:
				log.exception('Calling the after function failed.')
				exc.__context__ = error
				traceback.print_exception(type(exc), exc, exc.__traceback__)
		elif error:
			msg = 'Exception in voice thread {}'.format(self.name)
			log.exception(msg, exc_info = error)
			print(msg, file = sys.stderr)
			traceback.print_exception(type(error), error, error.__traceback__)
	
	def stop(self):
		self._end.set()
		self._resumed.set()
		with self._source.allow_read:
			self._source.ret = b''
		self._speak(False)
	
	def pause(self, *, update_speaking = True):
		self._resumed.clear()
		if update_speaking:
			self._speak(False)
	
	def resume(self, *, update_speaking = True):
		self.loops = 0
		self._start = time.perf_counter()
		self._resumed.set()
		if update_speaking:
			self._speak(True)
	
	def is_playing(self):
		return self._resumed.is_set() and not self._end.is_set()
	
	def is_paused(self):
		return not self._end.is_set() and not self._resumed.is_set()
	
	def _set_source(self, source):
		with self._lock:
			self.pause(update_speaking = False)
			self._source = source
			self.resume(update_speaking = False)
	
	def _speak(self, speaking):
		try:
			asyncio.run_coroutine_threadsafe(self.bot.ws.speak(speaking), self.bot.loop)
		except Exception as e:
			log.info("Speaking call in player failed: %s", e)


class VoiceClientCopy(discord.VoiceClient):
	# subclassed to use modified AudioPlayer class
	
	def play(self, source, *, after=None):
		
		if not self.is_connected():
			raise discord.errors.ClientException('Not connected to voice.')
		
		if self.is_playing():
			raise discord.errors.ClientException('Already playing audio.')
		
		if not isinstance(source, discord.AudioSource):
			raise TypeError('source must be an AudioSource not {0.__class__.__name__}'.format(source))
		
		if not self.encoder and not source.is_opus():
			self.encoder = discord.opus.Encoder()
		
		self._player = AudioPlayer(source, self, after = after)
		self._player.start()

#######################################################################################################


class Player(threading.Thread):
	_players = {}
	_loop_options = {
		"stop": "stop",
		"all": "all",
		r"\d+ ?(-|to) ?\d+": "range",
		r"after ?\d+": "after",
		r"until ?\d+": "until",
		r"\d+": "number"
	}
	
	@classmethod
	def get_player(cls, _id):
		"""
		@param _id: discord guild.id as string
		"""
		player: Player = cls._players.get(str(_id))
		return player
	
	@classmethod
	def get_all(cls):
		players: List[Player] = list(cls._players.values())
		return players
	
	@classmethod
	def set_loop(cls, _id, value):
		"""
		@param _id: discord guild.id
		@param value: loop-value
		"""
		print(value)
		player = cls.get_player(_id)
		if not player:
			return "No music player found for this guild!"
		else:
			for key in cls._loop_options.keys():
				if re.match(key, value):
					player._loop = cls._loop_options[key]
					player._loop_value = value
					break
			else:
				return "No valid loop parameter given!"
	
	@classmethod
	def del_player(cls, _id):
		"""
		@param _id: discord guild.id
		"""
		cls._players.pop(_id)
	
	@classmethod
	def get_current(cls, _id):
		"""
		@param _id: discord guild.id
		"""
		player = cls.get_player(_id)
		if not player:
			return
		to_return = {
			"title": player._current["title"],
			"duration": player._current["duration"],
			"link": player._current["link"],
			"thumbnail": player._current["thumbnail"],
			"description": player._current["description"],
			"passed": player.get_progress(),
			"buffer_status": player.get_buffer_progress(),
			"ffmpeg_options": player._current.get("ffmpeg_options")
		}
		return to_return
	
	@classmethod
	def get_queue_info(cls, _id):
		"""
		@param _id: discord guild.id
		"""
		player = cls.get_player(_id)
		if not player:
			return
		# print(player._queue)
		data = map(
			lambda x: {
				'title': x['data']['title'],
				'duration': x['data']['duration'],
				'link': x['data']['link']
			}, player._queue
		)
		# print(data)
		return list(data), player._loop_value
	
	@classmethod
	def shuffle(cls, _id):
		"""
		@param _id: discord guild.id
		"""
		player = cls.get_player(_id)
		if not player:
			return
		current = player._queue[0]
		# print(player._queue)
		temp = [el for el in player._queue][1:]
		# print(temp)
		random.shuffle(temp)
		player._queue.clear()
		player._queue.extend([current, *temp])
	
	@classmethod
	def edit_queue(cls, _id, x, y = 0, keep = True, playlist = None):
		"""
		@param playlist: string
		@param keep: boolean
		@param y: position to move element to
		@param x: position to take element from
		@param _id: discord guild.id
		"""
		
		player = cls.get_player(_id)
		if not player:
			return
		size = len(player._queue)
		
		def remove(song):
			player._queue.remove(song)
			if playlist:
				db.db.get_collection("Playlists").find_one_and_update(
					{
						"user": song["data"]["user"].id,
						"name": playlist
					}, {
						"$pull": {
							"songs": [song["data"]["link"], song["data"]["title"]]
						}
					}
				)

		if isinstance(x, int):
			if x < 0:
				x = size + (x + 1)
			else:
				x %= size
			to_remove: dict = player._queue[x]
			remove(to_remove)
			to_remove = {
				"title": to_remove["data"]["title"],
				"original": [to_remove]
			}

		elif isinstance(x, slice):
			try:
				to_remove = player._queue[x]
				songs = []
				for item in to_remove:
					remove(item)
					songs.append(to_remove)
				to_remove = {
					"title": "- " + "\n- ".join(map(lambda song: song["data"].get("title"), songs)),
					"original": songs
				}
				keep = False
			except IndexError:
				return "Out of bounds!", "", "error_2"

		elif type(x) in (list, tuple):
			songs = []
			for number in reversed(x):
				to_remove: dict = player._queue[number]
				remove(to_remove)
				songs.append(to_remove)
			to_remove = {
				"title": "- " + "\n- ".join(map(lambda song: song["data"].get("title"), songs)),
				"original": songs
			}
			keep = False
		
		else:
			return "Received invalid value", str(x), "error_2"

		if keep:
			if y < 0:
				y = size + (y + 1)
			else:
				y %= size
			player._queue.insert(y, to_remove["original"])
			if y == 0 or to_remove["original"]["data"] == player._current:
				player._v_c.stop()
			return f"Moved {to_remove['title']} to position {y}!", "", "success"
		
		else:
			if player._current in map(lambda original: original["data"], to_remove["original"]):
				player._skipped = True
				player._v_c.stop()
			return "Removed", f"```{to_remove['title']}```", "success"
	
	@classmethod
	def skip(cls, _id, value):
		"""
		@param _id: discord guild.id
		@param value: skip-value
		"""
		player = cls.get_player(_id)
		if not player:
			return
		count = 1
		if not isinstance(value, int):
			value = player.find_by_name(value)
			if not isinstance(value, int):
				return "Error", value, "error_2"
		while value - 1:
			player.loop_handler()
			count += 1
			value -= 1
		# print("skipped multiple, stopping current")
		player._v_c.stop()
		return "Skipped", f"{count} songs!", "success"
	
	def __init__(self, name: str, v_c: VoiceClientCopy, data):
		self._players[name] = self
		super().__init__(name = name)
		self.bot = data["bot"]
		self.source = None
		self._data = data
		self._skipped = False
		self._queue = deque()
		self._v_c = v_c
		self._event = threading.Event()
		self._ffmpeg_options = {
			"options": "-vn -sn -loglevel level+fatal",
			"before_options": " -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
		}
		self._name = name
		self._work = True
		self._loop = "stop"
		self._loop_value = ""
		self._error_count = 0
		self._current = None
		self._finished = False
		self._is_started = False
		
	def __repr__(self):
		return f"Player for {self._data.get('guild')}"
	
	def get_progress(self):
		return self.source.buffer.pos
	
	def add(self, item: dict, silent = False):
		# if self._data.get("show"):
		if not silent:
			self.show(item["data"]["title"], len(self._queue))
		self._queue.append(item)
		if not self._is_started:
			self._is_started = True
			print(self, "started")
			self._event.set()
	
	def add_multiple(self, items: List[dict]):
		# if self._data.get("show"):
		self.show(f"{len(items)} songs", len(self._queue))
		self._queue.extend(items)
		if not self._is_started:
			self._is_started = True
			print(self, "started")
			self._event.set()
	
	def update_data(self, data: dict):
		self._data.update(data)
	
	def show(self, title, pos):
		channel = self._data.get("channel")
		embed = self.bot.responder.emb_resp("", f"{title} added to queue at position {pos}!", "info")
		task = channel.send(embed = embed, delete_after = 10.0)
		self._data["loop"].create_task(task)
	
	def seek(self, duration = 5):
		self.source.buffer.seek(duration)
	
	def stop(self):
		self._work = False
		self._finished = True
		self._queue.clear()
		self._queue.append(None)
		self._event.set()
		for downloader in Downloader.get_all(key = lambda x: self._name in x[0]):
			downloader.stop()
		print("downloaders for %s cleared", self)
		# return self._data["loop"].create_task(self._v_c.disconnect(force = True))
	
	def del_current(self, playlist = None):
		self._current = None
		temp = self._queue.popleft()
		self._skipped = True
		self._v_c.stop()
		if playlist:
			db.db.get_collection("Playlists").find_one_and_update(
				{
					"user": temp["data"]["user"].id,
					"name": playlist
				}, {
					"$pull": {
						"songs": [temp["data"]["link"], temp["data"]["title"]]
					}
				}
			)
		return temp
	
	def find_by_name(self, name: str, multi = False):
		if not name:
			return None
		items = list(map(lambda x: (x[1]['data'].get("title"), x[0]), enumerate(self._queue)))
		# print(items)
		results = list(
			filter(
				lambda item, value = name: re.search(re.escape(value), item[0], re.I),
				items
			)
		)
		if results:
			idx = list(zip(*results))[1]
		else:
			return None
		
		if multi:
			return idx
		else:
			try:
				return idx[0]
			except IndexError:
				return "No song found!"
	
	def run(self):
		
		async def reconnect(src):
			print("%", self._v_c)
			print("%", self._v_c.channel)
			await self.bot.wait_until_ready()
			await self._v_c.channel.connect(cls = VoiceClientCopy)
			await self._v_c.play(src, after = self.after)
		
		async def info():
			try:
				title = "🎵 Now playing:"
				song_title = self._current['title']
				desc = f"[{song_title}]({self._current['link']}) ({self._current['duration']})"
				embed = self.bot.responder.emb_resp(title, desc, "info")
				embed.set_author(name = f"Requested by {self._current['user']}")
				embed = embed.set_thumbnail(url = self._current["thumbnail"])
				try:
					next_song = self._queue[1]["data"]["title"]
					next_song += f" ({self._queue[1]['data']['duration']})"
				except IndexError:
					next_song = "None"
				embed.add_field(name = "next:", value = next_song)
				
				await self._data["channel"].send(embed = embed, delete_after = 60.0)
			except Exception as e2:
				await self._data["channel"].send(embed = self.bot.responder.emb_resp2(f"{type(e2)}, {e2}"))
		
		while self._work:
			try:
				if not self._is_started:
					print(self, "waiting for first music")
					self._event.wait()
				temp = self._queue[0]
				if not temp:
					break
				# print(temp)
				self._event.clear()
				video_data = temp["data"]
				if video_data["expired"]():
					print("updating data for", video_data.get("title"))
					video_data = temp["func"]()
					new_data = {
						"data": video_data,
						"func": temp["func"]
					}
					self._queue.popleft()
					self._queue.appendleft(new_data)
				self._current = video_data
				ffmpeg_options = self._ffmpeg_options.copy()
				if temp.get("ffmpeg_options"):
					self._current.update({"ffmpeg_options": temp["ffmpeg_options"]})
					ffmpeg_options[temp["ffmpeg_options"][0][0]] += temp["ffmpeg_options"][0][1]
					ffmpeg_options[temp["ffmpeg_options"][1][0]] += temp["ffmpeg_options"][1][1]
				self.source = FFmpegPCMAudioCopy(source = self._current["url"], **ffmpeg_options)
				print("playing")
				try:
					self._v_c.play(self.source, after = self.after)
				except discord.ClientException:
					break
					# self._data["loop"].create_task(reconnect(self.source))
					
				self._data["loop"].create_task(info())
				if self._is_started:
					print(self, "waiting for music")
					self._event.wait()
				
			except Exception as e:
				print("VoiceClient:", self._v_c)
				extra = ""
				self._error_count += 1
				if self._error_count == 10:
					extra = "\nQuitting, too many errors in a row"
					self.stop()
				print(traceback.extract_tb(e.__traceback__))
				self._data["loop"].create_task(
					self._data["channel"].send(
						f"error `{e}` in line `{e.__traceback__.tb_lineno}` in `{__name__}`" + extra
					)
				)
				self._event.set()
				
		print(self, "stopped!")
		if not self._finished:
			self._loop = "stop"
			self.after()
		Player.del_player(self._name)
	
	def loop_handler(self):
		if self._skipped:
			return
		try:
			current = self._queue.popleft()
			# print(current["data"]["title"])
		except (IndexError, TypeError):
			return
		# print(self._loop, self._queue)
		
		if not self._queue and self._loop == "stop":
			print("music queue empty, finishing")
			if not self._finished:
				self.stop()
		
		else:
			# print("loop:", self._loop)
			
			if self._loop == "stop":
				pass
			
			elif self._loop == "all":
				self._queue.append(current)
			
			elif self._loop == "range":
				numbers = list(filter(None, re.findall(r"\d*", self._loop_value)))
				
				if not int(numbers[0]):
					self._queue.insert(int(numbers[1]), current)
				else:
					self._loop_value = f"{int(numbers[0]) - 1} to {int(numbers[1]) - 1}"
			
			elif self._loop == "after":
				number = list(filter(None, re.findall(r"\d+", self._loop_value)))
				
				if int(number[0]):
					self._loop_value = f"after {int(number[0]) - 1}"
				else:
					self._loop = "all"
					self._queue.append(current)
			
			elif self._loop == "until":
				try:
					number = list(filter(None, re.findall(r"\d*", self._loop_value)))
					self._queue.insert(int(number[-1]), current)
				except Exception as e:
					print(e, __name__)
			
			elif self._loop == "number":
				match = int(re.match(r"\d+", self._loop_value).group())
				# print("loop one song at", match)
				
				if not match:
					self._queue.insert(0, current)
				else:
					self._loop_value = str(match - 1)
	
	def after(self, error = None):
		if not error:
			self._error_count = 0
		
		print("ERROR:", error)
		
		self.loop_handler()
		self._skipped = False
		self._event.set()
	
	def get_buffer_progress(self):
		if self.source.done:
			return "```Fully buffered```"
		else:
			return f"```{datetime.timedelta(seconds = int(self.source.buffer.qsize() * 0.02))}```"


class Downloader:
	_downloaders = {}
	_api_info = json.load(open("data/info.json", "r"))["api_info"]
	kwargs = {
		"part": "id",
		"maxResults": 50,
	}
	
	@classmethod
	def get_downloader(cls, _id):
		downloader: Downloader = cls._downloaders.get(_id)
		return downloader
	
	@classmethod
	def get_all(cls, key = lambda x: True):
		try:
			downloaders = cls._downloaders.items()
			# print(downloaders)
			zip_data = list(filter(key, downloaders))
			# print(zip_data)
			downloader_objects = list(zip(*zip_data))[1]
			# print(downloader_objects)
			return downloader_objects
		except Exception as e:
			print(e.__traceback__.tb_lineno, e)
			return []
		
	@classmethod
	def del_downloader(cls, _id):
		cls._downloaders.pop(_id)

	def __init__(self, **data):
		self._downloaders[data["_id"]] = self
		self._work = True
		self._data = data
		self._playlist = ""
		self._coll = db.db.get_collection("PlayerCache")
		self._name = data["_id"]
		self._ytdl = ytdl.YoutubeDL({
			"quiet": True,
			# "verbose": True,
			"format": "bestaudio/best",
			# "ignoreerrors": True,
			"youtube_include_dash_manifest": False
		})
		self._api_args = self.__class__.kwargs.copy()
		api_info = self.__class__._api_info
		self.youtube = googleapiclient.discovery.build(api_info[0], api_info[1], developerKey = api_info[2])
		self._player: Player = data.get("player")
		self._queue = queue.Queue()
		self._bot = data.get("bot")
		self._lock = threading.Lock()
		self.add(data)
		self.run()
		
	def __repr__(self):
		return f"Downloader for {self._data.get('author')} in {self._data.get('guild')}"
	
	def add(self, data: dict):
		self._queue.put(data)
	
	def stop(self):
		self._work = False
		self._queue.queue.clear()
		self._queue.put_nowait(None)
	
	def run(self):
		# def get_urls(item_list):
		# 	return map(lambda item: u.concat(("watch", "v"), item["contentDetails"]["videoId"]), item_list)
		
		def get_id(item_list: List[dict]):
			new_list = []
			for item in item_list:
				_id = item["snippet"]["resourceId"]["videoId"]
				new_list.append(_id)
			return new_list
		
		def clean(d: dict):
			if not d:
				return None
			video_url = d.get("url")
			duration = datetime.timedelta(seconds = d.get("duration"))
			check = datetime.timedelta(minutes = 5)
			try:
				expiration_time = datetime.datetime.fromtimestamp(int(re.search(r"expire=(\d+)", video_url).group(1)))
				expired = (lambda: expiration_time - duration - datetime.datetime.now() < check)
			except AttributeError:
				expired = (lambda: True)
			thumbnails = filter(lambda thumbnail: "webp" not in thumbnail["url"], d.get("thumbnails"))
			thumbnails = sorted(thumbnails, key = lambda x: (x.get("height") or 0) * (x.get("width") or 0))
			new_item = {
				"title": d.get("title"),
				"link": d.get("webpage_url"),
				"duration": duration,
				"start": None,
				"end": None,
				"description": d.get("description"),
				"thumbnail": thumbnails[-1].get("url"),
				"url": video_url,
				"expired": expired,
				"user": self._data.get("author")
			}
			return new_item
		
		def update_msg(title = "", desc = "", color = "", _type = "embed"):
			if _type == "embed":
				kwargs = {
					"embed": self._bot.responder.emb_resp(title, desc, color)
				}
			elif _type == "text":
				kwargs = {
					"content": desc
				}
			else:
				return None
			self._bot.loop.create_task(
				msg.edit(**kwargs)
			)
			
		while True:
			try:
				print(self, "waiting for current data to be processed")
				self._lock.acquire(blocking = True)
				if not self._queue:
					print("something went wrong, no queue object found on first start!")
					break
					
				print(self, "waiting for data")
				new_data = self._queue.get()
				if not new_data:
					break
				self._data.update(new_data)
				
				msg = self._data.get("msg")
				
				url = new_data.get("url")
				print(url)
				
				if not url:
					continue
	
				if "list" in url:
					self._playlist = ""
					playlist = []
					playlist_id = re.search("list=(.{18,34})", url, re.I).group(1)
					self._api_args["playlistId"] = playlist_id
					
					request = self.youtube.playlistItems().list(**self._api_args)
					response = request.execute()
					if response.get("error"):
						print(response)
						if self._data.get("type") == "default":
							update_msg(
								"Error",
								"Youtube API denied that request\n" + json.dumps(response, indent = 4),
								"error_2"
							)
						continue
					
					playlist_info = self._coll.find_one({"name": playlist_id})
					
					if not playlist_info:
						self._coll.insert_one({"name": playlist_id, "etag": response.get("etag")})
						update_playlist = True
					
					elif playlist_info.get("etag") != response.get("etag"):
						
						print("updating playlist!")
						if self._data.get("type") == "default":
							update_msg(desc = "Updating local playlist cache!", _type = "text")
						self._coll.find_one_and_update(
							{"name": playlist_id},
							{
								"$set": {
									"etag": response.get("etag")
								}
							}
						)
						update_playlist = True
					
					else:
						playlist = playlist_info.get("items")
						update_playlist = False
					
					if update_playlist:
						self._api_args["part"] = "snippet"
						request = self.youtube.playlistItems().list(**self._api_args)
						response = request.execute()
						next_page_token = response.get("nextPageToken")
						items = get_id(response.get("items"))
						playlist.extend(items)
						
						while next_page_token:
							print(next_page_token)
							self._api_args["pageToken"] = next_page_token
							request = self.youtube.playlistItems().list(**self._api_args)
							response = request.execute()
							
							if response.get("error"):
								print(response)
								if self._data.get("type") == "default":
									update_msg(
										"Error",
										"Youtube API denied that request\n" + json.dumps(response, indent = 4),
										"error_2"
									)
								continue

							next_page_token = response.get("nextPageToken")
							
							items = get_id(response.get("items"))
							playlist.extend(items)
						if "pageToken" in self._api_args:
							self._api_args.pop("pageToken")
							
						self._coll.find_one_and_update({"name": playlist_id}, {"$set": {"items": playlist}})
					
					self._data["url"] = playlist
					self.add(self._data)
					if self._lock.locked():
						self._lock.release()
	
				elif "watch" in url:
					func = (lambda own_url = url: clean(self._ytdl.extract_info(own_url, download = False)))
					try:
						data = func()
					except Exception as e:
						if self._data.get("type") == "default":
							update_msg(f"Error in {url}", str(e), "error_2")
						continue
					track_data = {
						"ffmpeg_options": new_data.get("ffmpeg_options"),
						"data": data,
						"func": func
					}
					self._player.add(track_data)
					if self._data.get("type") == "default":
						update_msg("Done", "", "ok")
					if self._lock.locked():
						self._lock.release()
					
				elif new_data.get("play_all"):
					playlist_name = new_data.get("play_all")
					if self._data.get("type") == "default":
						update_msg(desc = f"Adding all songs from playlist `{playlist_name}` to queue", _type = "text")
					songs_data = db.db.get_collection("Playlists").find_one(
						{
							"user": self._data["author"].id,
							"name": playlist_name
						}
					)
					if songs_data:
						songs = songs_data["songs"]
					else:
						if self._data.get("type") == "default":
							update_msg("Error", f"Playlist {new_data.get('play_all')} wasn't found!", "error")
						if self._lock.locked():
							self._lock.release()
						continue
					self._data["url"] = songs
					self._playlist = self._data.pop("play_all")
					self.add(self._data)
					if self._lock.locked():
						self._lock.release()
	
				elif isinstance(url, list):
					results = []
					track_data = None
					
					if self._data.get("type") == "default":
						update_msg("Estimated time:", str(datetime.timedelta(seconds = len(url))), "info")
					if self._data.pop("sh", None):
						random.shuffle(url)
				
					for el in url:
						# print(el, type(el), el[0], el[1])
						# now = datetime.datetime.now()

						if not self._work:
							if self._data.get("type") == "default":
								update_msg("Aborted adding the playlist", "", "info")
							break
							
						if type(el) in (tuple, list):
							link = el[0]
							name = el[1]

						else:
							link = el
							name = ""

						func = (lambda save_url = link: clean(self._ytdl.extract_info(save_url, download = False)))

						try:
							data = func()
						except Exception as e:
							print(name, link)
							if name:
								print(link, name)
								db.db.get_collection("Playlists").find_one_and_update(
									{
										"user": self._data["author"].id,
										"name": self._playlist
									}, {
										"$pull": {
											"songs": el
										}
									}
								)
							
								if self._data.get("type") == "default":
									self._bot.loop.create_task(msg.channel.send(embed = self._bot.responder.emb_resp(
										f"Error in {name}\n{link}", str(e), "error_2")))
									request = self.youtube.search().list(
										part = "snippet",
										q = name,
										type = "video"
									)
									response = request.execute()
									try:
										dur = track_data["data"]["duration"]-30 if track_data and len(url) < 30 else 60 * 5
										new_url = u.to_yt_url("v", response["items"][0]["id"]["videoId"])
										content = f"{self._data.get('author').mention}\nDo you want to add {new_url} instead?"
										content += f"\nTime left to decide: <t:{datetime.datetime.now(datetime.UTC) + dur}:R>"
										check_msg = asyncio.run_coroutine_threadsafe(
											msg.channel.send(content),
											self._bot.loop
										).result()
										
										future = asyncio.run_coroutine_threadsafe(
											u.reaction(check_msg, self._data.get("author"), self._bot),
											self._bot.loop
										)
										
										if future.result(timeout = dur) == "✅":
											func = (lambda save_url = new_url: clean(
												self._ytdl.extract_info(save_url, download = False)))
											data = func()
											track_data = {
												"data": data,
												"func": func
											}
											if len(url) < 30:
												results.append(track_data)
											else:
												self._player.add(track_data, True)
									
									except TimeoutError:
										self._bot.loop.create_task(msg.channel.send("You took too long, continuing!"))
									except KeyError:
										pass
									except Exception as e:
										print(e, e.__traceback__.tb_lineno)
								
							if self._lock.locked():
								self._lock.release()
							continue
							
						track_data = {
							"data": data,
							"func": func
						}
						if len(url) < 30:
							results.append(track_data)
						else:
							self._player.add(track_data, True)
						# print(datetime.datetime.now() - now)
					else:  # execute when every song has been added to result list
						if len(url) < 30:
							self._player.add_multiple(results)
						if self._data.get("type") == "default":
							update_msg("Done", "", "ok")
						if self._lock.locked():
							self._lock.release()
						continue
						
					if self._lock.locked():
						self._lock.release()
					break
				
				else:
					if self._data.get("type") == "default":
						update_msg("Error", f"received invalid data type {type(url)}", "error_2")
					if self._lock.locked():
						self._lock.release()
					
			except Exception as e:
				if self._data.get("type") == "default":
					update_msg("❌ Error! Something went wrong!", f"{e}\n{e.__traceback__.tb_lineno}", "error_2")
				print(e, e.__traceback__.tb_lineno)
				if self._lock.locked():
					self._lock.release()
		print(self, "has stopped")
		Downloader.del_downloader(self._name)


class MusicManager:
	"""manage all voice clients in all guilds"""
	_queue = queue.Queue()
	
	@classmethod
	def put(cls, data):
		cls._queue.put(data)
	
	@classmethod
	async def stop(cls, _id = None, full = False):
		if _id:
			player: Player = Player.get_player(_id)
			if player:
				player.stop()
		if full:
			ev = asyncio.Event()
			for p in Player.get_all():
				ev.clear()
				task: asyncio.Task = p.stop()
				task.add_done_callback(lambda x: ev.set())
				print("waiting for", p, "to terminate")
				await ev.wait()
			cls._queue.queue.clear()
			cls._queue.put({})
	
	def __init__(self):
		self._coll = db.db.get_collection("PlayerCache")
		self.create()
	
	def create(self):
		while True:
			print("waiting")
			try:
				data: dict = self._queue.get()
				if not data:
					break
				
				# Create Thread ID
				downloader_id = str(data.get("author").id) + str(data.get("guild").id)
				player_id = str(data.get("guild").id)
				
				# Check if thread with id exists
				downloader: Downloader = Downloader.get_downloader(downloader_id)
				player: Player = Player.get_player(player_id)
				
				if not player:
					player = Player(player_id, data.get("v_c"), data)
					player.start()
				else:
					player.update_data(data)
				
				if downloader:
					downloader.add(data)
				
				else:
					q = queue.Queue()
					data.update({
						"_id": downloader_id,
						"queue": q,
						"player": player
					})
					threading.Thread(target = Downloader, kwargs = data).start()
			except Exception as e:
				print("".join(traceback.format_tb(e.__traceback__)), repr(e), file = sys.stderr)
		print(self, "stopped!")
