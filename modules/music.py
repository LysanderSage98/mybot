import asyncio
import bs4
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
		
		# log.info('Preparing to terminate ffmpeg process %s.', proc.pid)
		
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
		self.readers = {}
		
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
				print("PAUSED", self._source)
				self._resumed.wait()
				print("RESUMED", self._source)
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
			self.readers[self._source] = threading.Thread(target = self._source.read)
			self.readers[self._source].start()
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
			if not self.readers.get(source):
				self.readers[source] = threading.Thread(target = source.read)
				self.readers[source].start()
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
	_queue_counters = {}
	
	@classmethod
	def get_player(cls, _id):
		"""
		@param _id: discord guild.id as string
		"""
		if isinstance(_id, Player):
			_id = _id._name
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

		item = player._currently_playing[player._queue]
		to_return = {
			"title": item["title"],
			"duration": item["duration"],
			"link": item["link"],
			"thumbnail": item["thumbnail"],
			"description": item["description"],
			"passed": player.get_progress(),
			"buffer_status": player.get_buffer_progress(),
			"ffmpeg_options": item.get("ffmpeg_options")
		}
		return to_return
	
	@classmethod
	def get_queues_info(cls, _id):
		"""
		@param _id: discord guild.id
		"""
		player = cls.get_player(_id)
		if not player:
			return
		data = {x: len(y) for x, y in player._queues.items()}
		print(data)
		return data, player._queue
	
	@classmethod
	def merge_queues(cls, _id, source, dest):
		"""
		@param _id: discord guild.id
		@param source: source queue
		@param dest: queue to merge source into
		"""
		player = cls.get_player(_id)
		if not player:
			return
		print("in merge queues:", _id, source, dest)
		
		q1 = player._queues.get(source, None)
		q2 = player._queues.get(dest)
		if not (q1 and q2):
			return -1
		
		curr = q1[0]
		q1.rotate(-1)
		player.add_multiple(list(q1), new = False)
		q1.clear()
		q1.append(curr)
		return 1
	
	@classmethod
	def switch_queues(cls, _id, val, new = False):
		"""
		@param _id: discord guild.id
		@param val: queue to try switching to
		@param new: switch into entirely new queue
		"""
		player = cls.get_player(_id)  # todo move that block into decorator
		if not player:
			return
		print("in switch queues:", _id, val, new)
		
		q = player._queues.get(val)
		if q is None:
			return -1
		
		player._queue = val
		source = player.sources.get(val)
		if not new and source:
			player.source = source
			player._v_c.source = player.source
		elif not source:
			player.source = None
			player._event.set()
		else:
			player.source = None
		return 1
	
	@classmethod
	def get_queue_info(cls, _id):
		"""
		@param _id: discord guild.id
		"""
		player = cls.get_player(_id)
		if not player:
			return
		# print(player._queues[player._queue])
		data = map(
			lambda x: {
				'title': x['data']['title'],
				'duration': x['data']['duration'],
				'link': x['data']['link']
			}, player._queues[player._queue]
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
		current = player._queues[player._queue][0]
		# print(player._queues[player._queue])
		temp = [el for el in player._queues[player._queue]][1:]
		# print(temp)
		random.shuffle(temp)
		player._queues[player._queue].clear()
		player._queues[player._queue].extend([current, *temp])
	
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
		size = len(player._queues[player._queue])
		
		def remove(song):
			player._queues[player._queue].remove(song)
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
			to_remove: dict = player._queues[player._queue][x]
			remove(to_remove)
			to_remove = {
				"title": to_remove["data"]["title"],
				"original": [to_remove]
			}

		elif isinstance(x, slice):
			try:
				to_remove = player._queues[player._queue][x]
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
				to_remove: dict = player._queues[player._queue][number]
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
			player._queues[player._queue].insert(y, to_remove["original"])
			if y == 0 or to_remove["original"]["data"] == player._currently_playing[player._queue]:
				player._v_c.stop()
			return f"Moved {to_remove['title']} to position {y}!", "", "success"
		
		else:
			if player._currently_playing[player._queue] in map(lambda original: original["data"], to_remove["original"]):
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
		value = value % len(player._queues[player._queue])
		while value - 1:
			player.loop_handler()
			count += 1
			value -= 1
		# print("skipped multiple, stopping current")
		player._v_c.stop()
		return "Skipped", f"{count} songs!", "success"
	
	def queue_idx(self):
		c = self._queue_counters.get(self._name, 0) + 1
		self._queue_counters[self._name] = c
		return c  # int((int(self._name) / datetime.datetime.now(datetime.UTC).timestamp())**0.5)
	
	def __init__(self, name: str, v_c: VoiceClientCopy, data):
		self._players[name] = self
		super().__init__(name = name)
		self.bot = data["bot"]
		self.sources = {}
		self.source = None
		self._data = data
		self._skipped = False
		self._v_c = v_c
		self._event = threading.Event()
		self._ffmpeg_options = {
			"options": "-vn -sn -loglevel level+fatal",
			"before_options": " -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
		}
		self._name = name
		null_queue = self.queue_idx()
		self._queues = {null_queue: deque()}
		self._queue = null_queue
		self._work = True
		self._loop = "stop"
		self._loop_value = ""
		self._error_count = 0
		self._currently_playing = {}
		self._finished = False
		self._is_started = False
		
	def __repr__(self):
		return f"Player for {self._data.get('guild')}"
	
	def new(self, do_switch = True, name = None):
		val = name or self.queue_idx()
		if val not in self._queues:
			self._queues[val] = deque()
		if do_switch:
			self.switch_queues(self._name, val, True)
		return val
	
	def get_progress(self):
		return self.source.buffer.pos
	
	def add(self, item: dict, new, silent = False):
		# if self._data.get("show"):
		q = new or self._queue
		if not silent:
			self.show(item["data"]["title"], len(self._queues[q]))
		self._queues[q].append(item)
		if not self._is_started:
			self._is_started = True
			print(self, "started")
			self._event.set()
		elif new and len(self._queues[q]) >= 1:
			self._event.set()
	
	def add_multiple(self, items: List[dict], new):
		# if self._data.get("show"):
		q = new or self._queue
		self.show(f"{len(items)} songs", len(self._queues[q]))
		self._queues[q].extend(items)
		if not self._is_started:
			self._is_started = True
			print(self, "started")
			self._event.set()
		elif new and len(self._queues[q]) >= 1:
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
		self._queues[self._queue].clear()
		self._queues[self._queue].append(None)
		self._event.set()
		for downloader in Downloader.get_all(key = lambda x: self._name in x[0]):
			downloader.stop()
		print("downloaders for %s cleared", self)
		# return self._data["loop"].create_task(self._v_c.disconnect(force = True))
	
	def del_current(self, playlist = None):
		self._currently_playing[self._queue] = None
		temp = self._queues[self._queue].popleft()
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
		items = list(map(lambda x: (x[1]['data'].get("title"), x[0]), enumerate(self._queues[self._queue])))
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
		print("Started", self)
		
		async def reconnect(src):
			print("%", self._v_c)
			print("%", self._v_c.channel)
			await self.bot.wait_until_ready()
			await self._v_c.channel.connect(cls = VoiceClientCopy)
			await self._v_c.play(src, after = self.after)
		
		async def info(q):
			try:
				title = "🎵 Now playing:"
				song_title = self._currently_playing[q]['title']
				desc = f"[{song_title}]({self._currently_playing[q]['link']}) ({self._currently_playing[q]['duration']})"
				embed = self.bot.responder.emb_resp(title, desc, "info")
				embed.set_author(name = f"Requested by {self._currently_playing[q]['user']}")
				embed = embed.set_thumbnail(url = self._currently_playing[q]["thumbnail"])
				try:
					next_song = self._queues[q][1]["data"]["title"]
					next_song += f" ({self._queues[q][1]['data']['duration']})"
				except IndexError:
					next_song = "None"
				embed.add_field(name = "next:", value = next_song)
				
				await self._data["channel"].send(embed = embed, delete_after = 60.0)
			except Exception as e2:
				await self._data["channel"].send(
					embed = self.bot.responder.emb_resp2(
						f"({type(e2)}, Line: {e2.__traceback__.tb_lineno}), {e2}"))
		
		while self._work:
			try:
				if not self._is_started:
					print(self, "waiting for first music")
					self._event.wait()
				_q = self._queue
				temp = self._queues[_q][0]
				if not temp:
					break
				# print(temp)
				self._event.clear()
				video_data = temp["data"]
				if video_data["expired"]():
					print("updating data for", video_data.get("title"))
					video_data = temp["func"](True)
					new_data = {
						"data": video_data,
						"func": temp["func"]
					}
					self._queues[_q].popleft()
					self._queues[_q].appendleft(new_data)
				show = False
				if not self.source:
					self._currently_playing[_q] = video_data
					ffmpeg_options = self._ffmpeg_options.copy()
					if temp.get("ffmpeg_options"):
						self._currently_playing[_q].update({"ffmpeg_options": temp["ffmpeg_options"]})
						ffmpeg_options[temp["ffmpeg_options"][0][0]] += temp["ffmpeg_options"][0][1]
						ffmpeg_options[temp["ffmpeg_options"][1][0]] += temp["ffmpeg_options"][1][1]
					self.source = FFmpegPCMAudioCopy(source = self._currently_playing[_q]["url"], **ffmpeg_options)
					self.sources[_q] = self.source
					if self._v_c.is_playing():  # no source but playing? -> switch to new source from some other queue
						show = True
						self._v_c.source = self.source
				print("playing")
				try:
					if not self._v_c.is_playing():
						show = True
						self._v_c.play(self.source, after = self.after)
				except discord.ClientException as e:
					print(e)
					break
					# self._data["loop"].create_task(reconnect(self.source))
				
				if show:
					self._data["loop"].create_task(info(_q))
				if self._is_started:
					print(self, "waiting for music")
					self._event.wait()
				
			except Exception as e:
				print("VoiceClient:", self._v_c)
				removed = self._queues[self._queue].popleft()
				extra = f"\nSkipping {removed['data']['title']}"
				self._error_count += 1
				if self._error_count == 10:
					extra += "\nQuitting, too many errors in a row"
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
			current = self._queues[self._queue].popleft()
			# print(current["data"]["title"])
		except (IndexError, TypeError):
			return
		# print(self._loop, self._queues[self._queue])
		
		if not self._queues[self._queue] and self._loop == "stop":
			q = self._queues.pop(self._queue)  # pop to get next queue in dict if there are others
			self.sources.pop(self._queue)
			self._currently_playing.pop(self._queue)
			print("music queue empty, finishing")
			if not self._queues and not self._finished:
				self._queues[self._queue] = q  # fill back in because we're finishing anyway now
				self.stop()
			elif self._queues and not self._finished:
				self._queue = next(iter(self._queues.keys()))  # get next queue in dict
				if self._v_c.is_playing():
					self.source = self.sources[self._queue]
					self._v_c.source = self.source
		
		else:
			# print("loop:", self._loop)
			
			if self._loop == "stop":
				return
			
			elif self._loop == "all":
				self._queues[self._queue].append(current)
			
			elif self._loop == "range":
				numbers = list(filter(None, re.findall(r"\d*", self._loop_value)))
				
				if not int(numbers[0]):
					self._queues[self._queue].insert(int(numbers[1]), current)
				else:
					self._loop_value = f"{int(numbers[0]) - 1} to {int(numbers[1]) - 1}"
			
			elif self._loop == "after":
				number = list(filter(None, re.findall(r"\d+", self._loop_value)))
				
				if int(number[0]):
					self._loop_value = f"after {int(number[0]) - 1}"
				else:
					self._loop = "all"
					self._queues[self._queue].append(current)
			
			elif self._loop == "until":
				try:
					number = list(filter(None, re.findall(r"\d*", self._loop_value)))
					self._queues[self._queue].insert(int(number[-1]), current)
				except Exception as e:
					print(e, __name__)
			
			elif self._loop == "number":
				match = int(re.match(r"\d+", self._loop_value).group())
				# print("loop one song at", match)
				
				if not match:
					self._queues[self._queue].insert(0, current)
				else:
					self._loop_value = str(match - 1)
	
	def after(self, error = None):
		if not error:
			self._error_count = 0
		
		print("ERROR:", error)
		
		self.loop_handler()
		self.source = None
		self._skipped = False
		self._event.set()
	
	def get_buffer_progress(self):
		if self.source.done:
			return "```Fully buffered```"
		else:
			return f"```{datetime.timedelta(seconds = int(self.source.buffer.qsize() * 0.02))}```"


class Downloader(threading.Thread):
	
	iso_duration_values = ["hours", "minutes", "seconds"]
	iso_duration_regex = "PT" + "".join(map(lambda el: rf"(?P<{el}>)\d*{el[0].upper()}", iso_duration_values))
	
	class Comp(dict):
		
		def __lt__(self, other):
			return isinstance(self["url"], list)
		
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
		
	@staticmethod
	def get_video_data_from_url(url: str) -> dict:
		_id = re.search("(v=|.be/)(.{11})", url).group(2)
		resp = subprocess.run(["curl", u.to_yt_url("v", _id)], capture_output = True, encoding = "utf-8")
		if resp.returncode != 0:
			print(resp.returncode)  # todo send as response
			print(resp.stderr)  # todo send as response
			return {}
		data = bs4.BeautifulSoup(resp.stdout, "html.parser")
		try:
			body: bs4.element.Tag = data.find("body")
			script: bs4.element.Tag = body.find("script")
			script_text = script.text
		except Exception as e:
			print(e)  # todo send as response
			return {}
		json_val = re.search("({.*);$", script_text)
		if json_val is None:
			print("Regex failed")  # todo send as response
			return {}
		parsed = json.loads(json_val.group(1))
		return parsed

	def __init__(self, **data):
		super().__init__(name = data["_id"])
		self._downloaders[data["_id"]] = self
		self._work = True
		self._data = data
		# self._playlist = ""
		self._coll = db.db.get_collection("PlayerCache")
		self._name = data["_id"]
		self._ytdl = ytdl.YoutubeDL({
			"extractor_args": {
				"youtube": {
					"player_client": ["mweb"]
				}
			},
			"quiet": True,
			"verbose": True,
			"format": "bestaudio/best",
			# "ignoreerrors": True,
			"youtube_include_dash_manifest": False
		})
		self._api_args = self.__class__.kwargs.copy()
		api_info = self.__class__._api_info
		self.youtube = googleapiclient.discovery.build(api_info[0], api_info[1], developerKey = api_info[2])
		self._player: Player = data.get("player")
		self._queue = queue.PriorityQueue()
		self._bot = data.get("bot")
		self._lock = threading.Lock()
		self.add(data)
		# self.run()
		
	def __repr__(self):
		return f"Downloader for {self._data.get('author')} in {self._data.get('guild')}"
	
	def add(self, data: dict):
		self._queue.put(self.Comp(data))
	
	def stop(self):
		self._work = False
		self._queue.queue.clear()
		self._queue.put_nowait(None)
		
	def get_video_details(self, ids: list[str]):
		def duration_to_seconds(duration: str):
			match = re.search(self.iso_duration_regex, duration)
			matches = match.groupdict()
			if not matches:
				return 0
			return datetime.timedelta(
				**dict(map(lambda item: (item[0], int(item[1] or 0)), matches.items()))).total_seconds()
		
		_api_args = self._api_args.copy()
		_api_args["part"] = "snippet,contentDetails"
		curr = 0
		count = len(ids)
		res = []
		while curr * 50 < count:
			to_search = ids[curr * 50: (curr + 1) * 50]
			curr += 1
			_id = ",".join(to_search)
			_api_args["id"] = _id
			request = self.youtube.videos().list(**_api_args)
			response = request.execute()
			times = map(lambda el: (el["snippet"]["title"], duration_to_seconds(el["contentDetails"]["duration"])),
						response.get("items", []))
			res.extend(times)
		ret = list(map(lambda x: (x[0], *x[1]), zip(ids, res)))
		return ret
	
	def run(self):
		print("Started", self)
		api_args = self._api_args.copy()
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
			streaming_data = d["streamingData"]
			video_details = d["videoDetails"]
			
			video_url = u.to_yt_url("v", video_details["videoId"])
			duration = int(video_details["lengthInSeconds"])
			thumbnails = video_url.get("thumbnail", {}).get("thumbnails", {})
			thumbnails = filter(lambda thumbnail: "webp" not in thumbnail["url"], thumbnails)
			thumbnails = sorted(thumbnails, key = lambda x: (x.get("height") or 0) * (x.get("width") or 0))
			
			check = 5 * 60  # 5 min in seconds
			try:
				expiration_time = int(streaming_data["expiresInSeconds"])
				expired = (lambda: expiration_time - duration - datetime.datetime.now(datetime.UTC).timestamp() < check)
			except AttributeError:
				expired = (lambda: True)
			
		def clean_ytdl(_url, name, _dur, load = False):
			if load:
				d = self._ytdl.extract_info(_url, download = False)
				if not d:
					return None
				video_url = d.get("url")
				_dur = d.get("duration")
				check = 5 * 60
				try:
					expiration_time = int(re.search(r"expire=(\d+)", video_url).group(1))
					expired = (lambda: expiration_time - _dur - datetime.datetime.now(datetime.UTC).timestamp() < check)
				except AttributeError:
					expired = (lambda: True)
					
				thumbnails = filter(lambda thumbnail: "webp" not in thumbnail["url"], d.get("thumbnails"))
				thumbnails = sorted(thumbnails, key = lambda x: (x.get("height") or 0) * (x.get("width") or 0))
				thumbnail_url = thumbnails[-1].get("url")
				name = d.get("title")
				webpage = d.get("webpage_url")
				desc = d.get("description")
			else:
				webpage = ""
				desc = ""
				thumbnail_url = ""
				video_url = u.to_yt_url("v", _url)
				expired = (lambda: True)
			
			new_item = {
				"title": name,
				"link": webpage,
				"duration": datetime.timedelta(seconds = _dur),
				"start": None,
				"end": None,
				"description": desc,
				"thumbnail": thumbnail_url,
				"url": video_url,
				"expired": expired,
				"user": self._data.get("author")
			}
			return new_item
		
		def update_msg(message, title = "", desc = "", color = "", _type = "embed"):
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
				message.edit(**kwargs)
			)
			
		while True:
			print(self, "waiting for current data to be processed")
			self._lock.acquire(blocking = True)
			if not self._queue:
				print("something went wrong, no queue object found on first start!")
				break
			
			print(self, "waiting for data")
			new_data = self._queue.get()
			if not new_data:
				break
			print("in downloader:", new_data)
			# if not self._data:
			# 	self._data.update(new_data)
			
			url = new_data.get("url")
			
			if not url:
				continue
				
			new = new_data.get("new")
			print(type(url))
			if new is True:
				new = self._player.new(do_switch = False)
				new_data["new"] = new
				print("created new queue:", new)
			elif new is not False:
				self._player.new(do_switch = False, name = new)
				print("created new queue:", new)
			
			try:
				if "list" in url:
					msg = new_data.get("msg")  # sent by bot, so the bot can edit it as well
					# elf._playlist = ""
					playlist = []
					playlist_id = url.split("=")[1]
					api_args["playlistId"] = playlist_id
					
					request = self.youtube.playlistItems().list(**api_args)
					response = request.execute()
					if response.get("error"):
						print(response)
						if self._data.get("type") == "default":
							update_msg(msg,
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
							update_msg(msg, desc = "Updating local playlist cache!", _type = "text")
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
						api_args["part"] = "snippet"
						request = self.youtube.playlistItems().list(**api_args)
						response = request.execute()
						next_page_token = response.get("nextPageToken")
						items = get_id(response.get("items"))
						playlist.extend(items)
						
						while next_page_token:
							print(next_page_token)
							api_args["pageToken"] = next_page_token
							request = self.youtube.playlistItems().list(**api_args)
							response = request.execute()
							
							if response.get("error"):
								print(response)
								if self._data.get("type") == "default":
									update_msg(msg,
										"Error",
										"Youtube API denied that request\n" + json.dumps(response, indent = 4),
										"error_2"
									)
								continue

							next_page_token = response.get("nextPageToken")
							
							items = get_id(response.get("items"))
							playlist.extend(items)
						playlist = self.get_video_details(playlist)
						self._coll.find_one_and_update({"name": playlist_id}, {"$set": {"items": playlist}})
					
					new_data["url"] = playlist
					self.add(new_data)
					if self._lock.locked():
						self._lock.release()
	
				elif "watch" in url:
					msg = new_data.get("msg")  # sent by bot, so the bot can edit it as well
					func = (lambda load, own_url = url: clean_ytdl(own_url, "", 0, load))
					try:
						data = func(True)
					except Exception as e:
						print(e)
						if self._data.get("type") == "default":
							update_msg(msg, f"Error in {url}", str(e), "error_2")
						if self._lock.locked():
							self._lock.release()
						continue
					track_data = {
						"ffmpeg_options": new_data.get("ffmpeg_options"),
						"data": data,
						"func": func
					}
					self._player.add(track_data, new)
					if self._data.get("type") == "default":
						update_msg(msg, "Done", "", "ok")
						self._player.switch_queues(self._player, new)
					if self._lock.locked():
						self._lock.release()
					
				elif url == "None":
					msg = new_data.get("msg")  # sent by bot, so the bot can edit it as well
					playlist_name = new_data.get("play_all")
					if self._data.get("type") == "default":
						update_msg(msg, desc = f"Adding all songs from playlist `{playlist_name}` to queue", _type = "text")
					songs_data = db.db.get_collection("Playlists").find_one(
						{
							"user": new_data["author"].id,
							"name": playlist_name
						}
					)
					if songs_data:
						songs = songs_data["songs"]
					else:
						if self._data.get("type") == "default":
							update_msg(msg, "Error", f"Playlist {new_data.get('play_all')} wasn't found!", "error")
						if self._lock.locked():
							self._lock.release()
						continue
					new_data["url"] = songs
					# self._playlist = new_data.pop("play_all")
					self.add(new_data)
					if self._lock.locked():
						self._lock.release()
	
				elif isinstance(url, list):
					msg = new_data.get("msg")  # sent by bot, so the bot can edit it as well
					# playlist_name = new_data.get("play_all")
					results = []
					# track_data = None
					
					if self._data.get("type") == "default":
						update_msg(msg, "Estimated time:", str(datetime.timedelta(seconds = len(url))), "info")
					if new_data.pop("sh", None):
						random.shuffle(url)
					
					# x = 1
				
					while url:
						el = url.pop(0)
						print(el, type(el), el[0], el[1], el[2])
						# now = datetime.datetime.now()

						if not self._work:
							if self._data.get("type") == "default":
								update_msg(msg, "Aborted adding the playlist", "", "info")
							break
							
						if len(el) != 3:
							continue

						func = (lambda load, _el = el: clean_ytdl(*_el, load))

						# try:
						data = func(False)
						#	x = 1
						# except Exception as e:
						# 	x += 1
						# 	print(e)
						# 	if name:
						# 		print(link, name)
						# 		err = str(e)
						# 		if "try again later" in err:
						# 			self._bot.loop.create_task(msg.channel.send(embed = self._bot.responder.emb_resp(
						# 				f"Error in {name}\n{link}", f"{err}\nWaiting {x} minutes before continuing!", "error_2"
						# 			)))
						# 			url.append(el)
						# 			time.sleep(60 * x)
						# 			continue
						# 		if self._data.get("type") == "default":
						# 			self._bot.loop.create_task(msg.channel.send(embed = self._bot.responder.emb_resp(
						# 				f"Error in {name}\n{link}", err, "error_2")))
						# 			request = self.youtube.search().list(
						# 				part = "snippet",
						# 				q = name,
						# 				type = "video"
						# 			)
						# 			response = request.execute()
						# 			if not response["items"]:
						# 				self._bot.loop.create_task(msg.channel.send("No alternative video found!"))
						# 				continue
						# 			try:
						# 				if track_data and len(url) >= 30:
						# 					dur = track_data["data"]["duration"] - datetime.timedelta(seconds = 30)
						# 				else:
						# 					dur = datetime.timedelta(seconds = 60 * 5)
						# 				new_url = u.to_yt_url("v", response["items"][0]["id"]["videoId"])
						# 				content = f"{new_data.get('author').mention}\nDo you want to add {new_url} instead?"
						# 				x = int((datetime.datetime.now(datetime.UTC) + dur).timestamp())
						# 				content += f"\nTime left to decide: <t:{x}:R>"
						# 				check_msg = asyncio.run_coroutine_threadsafe(
						# 					msg.channel.send(content, delete_after = dur.total_seconds() + 30),
						# 					self._bot.loop
						# 				).result()
						#
						# 				future = asyncio.run_coroutine_threadsafe(
						# 					u.reaction(check_msg, new_data.get("author"), self._bot),
						# 					self._bot.loop
						# 				)
						#
						# 				if future.result(timeout = dur.seconds) == "✅":
						# 					func = (lambda save_url = new_url: clean_ytdl(
						# 						self._ytdl.extract_info(save_url, download = False)))
						# 					data = func()
						# 					track_data = {
						# 						"data": data,
						# 						"func": func
						# 					}
						# 					if len(url) < 30:
						# 						results.append(track_data)
						# 					else:
						# 						self._player.add(track_data, new)
						# 					db.db.get_collection("Playlists").find_one_and_update(
						# 						{
						# 							"user": new_data["author"].id,
						# 							"name": playlist_name
						# 						}, {
						# 							"$addToSet": {
						# 								"songs": [new_url, data["title"]]
						# 							}
						# 						}
						# 					)
						# 				db.db.get_collection("Playlists").find_one_and_update(  # always delete invalid track
						# 					{
						# 						"user": new_data["author"].id,
						# 						"name": playlist_name
						# 					}, {
						# 						"$pull": {
						# 							"songs": el
						# 						}
						# 					}
						# 				)
						#
						# 			except TimeoutError:
						# 				self._bot.loop.create_task(msg.channel.send("You took too long, continuing!"))
						# 			except KeyError as e:
						# 				print(e, e.__traceback__.tb_lineno)
						# 			except Exception as e:
						# 				print(e, e.__traceback__.tb_lineno)
						#
						# 	# if self._lock.locked():
						# 	# 	self._lock.release()
						# 	continue
							
						track_data = {
							"data": data,
							"func": func
						}
						if len(url) < 30:
							results.append(track_data)
						else:
							self._player.add(track_data, new, True)
						# print(datetime.datetime.now() - now)
					else:  # execute when every song has been added to result list
						if len(results) < 30:
							self._player.add_multiple(results, new)
						if self._data.get("type") == "default":
							update_msg(msg, "Done", "", "ok")
						self._player.switch_queues(self._player, new)
						if self._lock.locked():
							self._lock.release()
						continue
						
					if self._lock.locked():
						self._lock.release()
					break
				
				else:
					msg = new_data.get("msg")  # sent by bot, so the bot can edit it as well
					if self._data.get("type") == "default":
						update_msg(msg, "Error", f"received invalid data type {type(url)}", "error_2")
					if self._lock.locked():
						self._lock.release()
					
			except Exception as e:
				msg = new_data.get("msg")  # sent by bot, so the bot can edit it as well
				if self._data.get("type") == "default":
					update_msg(msg, "❌ Error! Something went wrong!", f"{e}\n{e.__traceback__.tb_lineno}", "error_2")
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
				print("in music manager:", data)
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
					Downloader(**data).start()
			except Exception as e:
				print("".join(traceback.format_tb(e.__traceback__)), repr(e), file = sys.stderr)
		print(self, "stopped!")
