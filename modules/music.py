import discord
import os
import threading
import queue
import re
import youtube_dl as yt

from helpers.other import utilities as u

music_queues = {}
player_queues = {}


class Player(threading.Thread):
	def __init__(self, responder, client, name, path, a_loop, v_c, channel):
		super().__init__(name = name)
		# self.sources = []
		self.responder = responder
		self.queue = queue.Queue()
		self.audioplayer = None
		self.bot = client
		self.path = path
		self.started = 0
		self.loop = a_loop
		self.repeat = "stop"
		self.f = None
		self.v_c = v_c
		self.finished = 0
		self.channel = channel
		self.event = threading.Event()
	
	def run(self):
		while True:
			try:
				print(self, "waiting for music")
				self.event.wait()
				self.started = 1
				self.event.clear()
				self.f = self.queue.get_nowait()
				print(self.f)
				
				if not self.f:
					print(self, "leaving loop")
					break
				
				async def info():
					title = "🎵 Now playing:"
					desc, tag = self.f.split("\\")[-1].rsplit(".", 1)[0].rsplit("°°__°°", 1)
					user = self.f.split("\\")[-2]
					desc_final = f"[{discord.utils.escape_markdown(desc)}]({u.to_yt_url(tag)})"
					embed = self.responder.emb_resp(title, desc_final, "info")
					embed.set_author(name = f"Requested by {self.bot.get_user(int(user))}")
					await self.channel.send(embed = embed, delete_after = 60.0)
				
				self.loop.create_task(info())
				source = discord.FFmpegPCMAudio(source = self.f)
				# print("playing")
				self.audioplayer = self.v_c.play(source, after = self.after)
			
			except Exception as e:
				print(e)
		print(self, "stop music!")
		if not self.finished:
			self.after()
		del player_queues[self.name]
	
	def after(self, error = None):
		
		if error:
			print("ERROR:", error)
		
		if self.queue.empty():
			print("finishing")
			temp = list(music_queues.keys())
			for q in filter(lambda x: re.search(str(self.v_c.guild.id), x), temp):
				temp = music_queues.pop(q)
				temp.put({"url": "STOP"})
			
			self.loop.create_task(self.v_c.disconnect())
			self.finished = 1
			self.queue.put_nowait(None)
		
		else:
			print(self.repeat)
			# src = self.sources.pop(0)
			if self.repeat == "stop":
				pass
			
			elif self.repeat in ("all", "full"):
				self.queue.put(self.f)
			# self.sources.append(src)
			
			elif re.match(r"\d ?(-|to) ?\d", self.repeat):
				numbers = list(filter(None, re.findall("\d*", self.repeat)))
				if not int(numbers[0]):
					# self.sources.insert(int(numbers[1]), src)
					self.queue.queue.insert(int(numbers[1]), self.f)
				else:
					self.repeat = f"{int(numbers[0]) - 1} to {int(numbers[1]) - 1}"
			
			elif re.match(r"after ?\d", self.repeat):
				number = list(filter(None, re.findall("\d*", self.repeat)))
				if int(number[0]):
					self.repeat = f"after {int(number[0]) - 1}"
				else:
					self.repeat = "all"
					self.queue.put(self.f)
			# self.sources.append(src)
			
			elif re.match(r"until ?\d", self.repeat):
				try:
					# print("short loop!")
					number = list(filter(None, re.findall("\d*", self.repeat)))
					# print(number)
					# self.sources.insert(int(number[-1]), src)
					# print(self.sources)
					self.queue.queue.insert(int(number[-1]), self.f)
				# print(self.queue.queue)
				except Exception as e:
					print(e)
			
			elif re.match(r"\d*", self.repeat):
				match = int(re.match(r"\d*", self.repeat).group())
				print("loop one song at", match)
				
				if not match:
					self.queue.queue.insert(0, self.f)
				
				else:
					self.repeat = str(match - 1)
			
			else:
				self.loop.create_task(self.channel.send(
					embed = self.responder.emb_resp("Invalid loop parameter!", "Defaulting to \"all\"!", "error_2")))
				self.queue.put(self.f)
				# self.sources.append(src)
				self.repeat = "all"
		
		self.event.set()


class Downloader:
	def __init__(self, responder, **d):
		self.responder = responder
		self.path = "other stuff\\music\\" + str(d.get("author").id) + "\\"
		self.ytdl = yt.YoutubeDL({
			"quiet": True,
			"format": "bestaudio",
			"outtmpl": self.path + "%(title)s°°__°°%(id)s.%(ext)s",
			"ignoreerrors": True,
			"youtube_include_dash_manifest": False
		})
		self.queue = d.get("queue")
		self.all = d.get("all")
		self.loop = d.get("loop")
		self.channel = d.get("channel")
		self.key = str(d.get("v_c").guild.id)
		
		if not player_queues.get(self.key):
			self.player = Player(
				self.responder,
				d.get("client"),
				self.key,
				self.path,
				self.loop,
				d.get("v_c"),
				d.get("channel")
			)
			player_queues[self.key] = self.player
		else:
			self.player = player_queues.get(self.key)
		self.download()
	
	def download(self):
		if not self.player.started:
			self.player.start()
		# print("CREATED")
		
		while True:
			try:
				print(self, "waiting for url")
				item = self.queue.get()
				print("ITEM: ", item)
				
				if not item:
					# print(self, "preparing to stop!")
					# del self.player.queue
					# self.player.queue = asyncio.Queue(loop = self.loop)
					self.player.queue.queue.clear()
					self.player.queue.put_nowait(None)
					self.player.event.set()
					break
				
				url = item.get("url")
				print("URL: ", url)
				if url == "STOP":
					print(self, "leaving loop")
					break
				
				elif isinstance(item, dict) and not url:
					info = item
					
					if info.get("loop"):
						print("LOOP:", info["loop"])
						self.player.repeat = info["loop"]
					
					elif info.get("amount"):
						print("AMOUNT:", info["amount"])
						self.player.queue.queue.rotate(-int(info["amount"]))
					continue
				
				if url != "None":
					print("downloading!")
					res = self.ytdl.extract_info(url, download = False)
					entries = res.get("entries")
					
					if not entries:
						# print(res)
						entries = [res]
						self.loop.create_task(item["msg"].edit(embed = self.responder.emb_resp("Song found!", "", "success")))
					
					links = list(filter(None, map(lambda x: u.to_yt_url(x["id"] if x else None), entries)))
					
					if len(links) == 1:
						self.loop.create_task(item["msg"].edit(embed = self.responder.emb_resp("Downloading!", links[0], "success")))
						self.ytdl.download(links)
					elif len(links) > 1:
						for link in links:
							self.queue.put({"url": link, "msg": item["msg"]})
					else:
						return print("something went wrong")
				
				# print(links)
				# print(self.all)
				if self.all:
					cond = "True"
					self.all = 0
				else:
					cond = "res['id'] in source.name"
				
				with os.scandir(self.path) as path:
					for source in path:
						# print(source.name)
						if source.path not in self.player.queue.queue:
							if eval(cond):
								# self.player.sources.append(source.name)
								self.player.queue.put_nowait(self.path + source.name)
								pos = self.player.queue.qsize()
								text = f"Added `{source.name.rsplit('°°__°°')[0]}` to queue at position {pos}!"
								embed = self.responder.emb_resp("Info", text, "success")
								self.loop.create_task(self.channel.send(embed = embed, delete_after = 5.0))
								
								if not self.player.started:
									self.player.event.set()
									self.player.started = 1
				
				self.loop.create_task(
					item["msg"].edit(embed = self.responder.emb_resp("Done!", "", "ok")))  # self.queue.put_nowait(None)
			except Exception as e:
				self.loop.create_task(self.channel.send(embed = self.responder.emb_resp2(str(e))))


class CreateDownloader:
	"""manage all voice clients in all guilds"""
	queue = queue.Queue()
	"""collect url and info about request"""
	
	def __init__(self, responder):
		self.create()
		self.responder = responder
	
	def create(self):
		
		while True:
			try:
				threads = [x.name for x in threading.enumerate()]
				print(threads)
				print("Waiting!")
				arg = self.queue.get(block = True)
				if not arg:  # put "None" or equivalent in queue to stop bot
					break
				
				if arg["type"] == "default":
					key = str(arg.get("v_c").guild.id) + str(arg.get("author").id)
					print(key)
					if arg.get("data"):  # check if queue content requested
						music_queues[key].put(arg["data"])
						continue
					
					elif not arg["url"]:  # disconnect provided voice client
						q = music_queues[key]
						q.queue.clear()
						# while not q.empty():
						# 	q.get()
						music_queues[key].put(None)
						continue
					
					else:
						if key not in threads:
							print("Creating downloader for ", arg["author"].name, " in ", arg["channel"].guild.name)
							q = queue.Queue()
							music_queues[key] = q
							q.put(arg)
							arg["queue"] = q
							threading.Thread(name = key, target = Downloader, args = [self.responder], kwargs = arg).start()
						else:
							music_queues[key].put(arg)
				elif arg["type"] == "gui":
					print("gui")
			
			except Exception as e:
				print("Create-error: ", e)
		
		print("preparing to stop!")
		for x in music_queues.keys():
			print(x)
			q = music_queues[x]
			q.queue.clear()
			# while not q.empty():
			# 	q.get()
			music_queues[x].put(None)
		# print(threads)
		print("stopping")
