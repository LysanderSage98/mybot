import threading
import os

from modules import bot, music, gui

modules = ([], [])

for f in os.listdir("."):
	if os.path.isdir(f):
		modules[1].append(f)
	else:
		modules[0].append(f[:-3])


class Holder:
	def __init__(self, _bot = None, _music = None, _gui = None):
		self.music = _music
		self.gui = _gui
		self.bot = _bot(self.reload, gui, None)
		if self.bot:
			self.bot_thread = threading.Thread(target = self.bot.run)
			self.bot_thread.start()
			if self.music:
				self.music_thread = threading.Thread(target = self.music)
				self.music_thread.start()
			if self.gui:
				self.gui_thread = threading.Thread(target = self.gui, args = [self.bot.loop, self.bot])
				self.gui_thread.start()

	def reload(self):
		if self.music:
			print("stop music")
			self.music_thread.join()
			self.music_thread = threading.Thread(target = self.music)
			self.music_thread.start()
		if self.gui:
			gui.fill_queue("STOP")
			self.gui_thread.join()
			self.gui_thread = threading.Thread(target = self.gui, args = [self.bot.loop, self.bot])
			self.gui_thread.start()


runner = Holder(bot.Bot, None, gui.Gui)
print("Starting")
