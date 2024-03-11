import discord
import threading
import os
import pathlib
try:
	pass
	# os.remove("data/MyBot.db")
	# os.remove("data/MyBot.db-journal")
except FileNotFoundError:
	pass
from helpers.other import responder
from modules import bot, music, gui

# modules = ([], [])

# for f in os.listdir("."):
# 	f = pathlib.Path(f)
# 	if f.is_dir():
# 		modules[1].append(f.name)
# 	elif f.stem == "py":
# 		modules[0].append(f.name)


class Holder:
	def __init__(self, responder_class, _bot = None, _music = None, _gui = None):
		self.music: music.MusicManager = _music
		self.gui = _gui
		self.bot: bot.Bot = _bot(self.reload, responder_class, self.gui, self.music, intents = discord.Intents.all())
		self.threads = {}
		if self.bot:
			thread = threading.Thread(target = self.bot.run)
			self.threads["bot_thread"] = thread
			thread.start()
			if self.music:
				# noinspection PyTypeChecker
				thread = threading.Thread(target = self.music)
				self.threads["music_thread"] = thread
				thread.start()
			if self.gui:
				thread = threading.Thread(target = self.gui, args = [self.bot.loop, self.bot, responder_class])
				self.threads["gui_thread"] = thread
				thread.start()
		self.join()

	def join(self):
		for thread in self.threads.values():
			try:
				thread.join()
			except Exception as e:
				print(e)

	def reload(self):
		if self.music:
			# print("stop music")
			# await self.music.stop(full = True)
			# noinspection PyTypeChecker
			self.threads["music_thread"] = threading.Thread(target = self.music)
			self.threads["music_thread"].start()
		if self.gui:
			gui.fill_queue("STOP")
			self.threads["gui_thread"] = threading.Thread(target = self.gui, args = [self.bot.loop, self.bot])
			self.threads["gui_thread"].start()
		self.join()


if __name__ == '__main__':
	print("Starting")
	runner = Holder(responder.Responder(), bot.Bot, music.MusicManager, None)
