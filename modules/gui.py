import discord
import queue
import threading
import re

import tkinter as tk


class Channel(tk.Frame):
	def __init__(self, root, loop, message, name):
		super().__init__(root, name = name)
		print(self)
		try:
			self.root = root
			self.target = message.author
			self.loop = loop
			name = re.sub("\\\\N", "", self.target.name.encode("cp1252", "namereplace").decode())
			content = re.sub("\\\\N", "", message.content.encode("cp1252", "namereplace").decode())
			
			self.entry = tk.Entry(self)
			self.button = tk.Button(self, text = "Reply!", command = lambda: self.loop.create_task(self.reply()))
			self.label = tk.Label(self, text = f"{name}: {content}")
			
			self.entry.pack()
			self.button.pack()
			self.label.pack()
			
			self.root.callback()
		except Exception as e:
			print(e)
			return
	
	def add(self, val):
		tk.Label(self, text = val).pack()
	
	async def reply(self):
		try:
			msg = self.entry.get()
			self.entry.delete(0, "end")
			await self.target.dm_channel.send(msg)
		finally:
			try:
				self.root.authors.remove(self.target.id)
				self.root.count -= 1
				self.root.callback()
			except Exception as e:
				print(e)
			self.destroy()
			return


class Gui(tk.Tk):
	event = threading.Event()
	queue = queue.Queue(maxsize = 1)
	
	def __init__(self, loop, client):
		super().__init__()
		self.count = 0
		self.authors = []
		self.frames = []
		self.obj = []
		self.loop = loop
		self.bot = client
		self.frame = tk.Frame(self)
		button = tk.Button(self.frame, name = "button", text = "Send!", command = self.dm)
		entry = tk.Entry(self.frame, name = "entry")
		button.pack()
		entry.pack()
		self.frame.pack()
		self.label = tk.Label(self, text = self.count)
		self.label.pack()
		self.after(1000, threading.Thread(target = self.check).start)
		self.mainloop()
	
	def callback(self):
		self.label["text"] = self.count
	
	def dm(self):
		_id, message = self.frame.children["entry"].get().split(" ", 1)
		self.frame.children["entry"].delete(0, "end")
		self.queue.put({self.bot.get_user(int(_id)): message})
		self.event.set()
	
	def check(self):
		while True:
			# print(self.event.is_set())
			self.event.wait()
			self.obj.insert(0, self.queue.get(block = True))
			# print(self.obj, self.authors, self.frames)
			
			if self.obj[0] == "STOP":
				self.after(10, self.quit)
				break
			
			elif type(self.obj[0]) == discord.Message:
				if self.obj[0].author.id not in self.authors:
					self.count += 1
					self.authors.append(self.obj[0].author.id)
					frame = Channel(self, self.loop, self.obj[0], str(self.obj[0].author.id))
					frame.pack(side = tk.LEFT)
					self.frames.append(frame)
					self.focus_force()
				else:
					obj = self.obj.pop(0)
					self.children[str(obj.author.id)].add(obj.content)
			
			elif type(self.obj[0]) == dict:
				obj = self.obj.pop(0)
				print(obj)
				self.loop.create_task(dm_send(obj))
			
			elif type(self.obj[0]) == tuple:
				obj = self.obj.pop(0)
				# print(obj)
				if obj[0] == "MSG":
					# print(obj[1])
					rep = '\\\\N'
					text = "\n".join([f"{el[0][0]} um {el[0][1]}: "
						f"{re.sub(rep, '', el[1].encode('cp1252', 'namereplace').decode('cp1252'))}\n"
						for el in obj[1]])
					# print(text)
					label = tk.Label(self, text = text, wraplength = 1000, anchor = tk.W, justify = tk.LEFT)
					label.pack()
					self.after(60000, label.destroy)
			
			self.event.clear()


async def dm_send(obj):
	try:
		dm = await list(obj.keys())[0].create_dm()
		await dm.send(list(obj.values())[0])
	except Exception as e:
		print(e)
	finally:
		return


def fill_queue(msg):
	Gui.queue.put(msg)
	Gui.event.set()
