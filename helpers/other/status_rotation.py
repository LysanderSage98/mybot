import asyncio
import discord
import random
from helpers.other import db_stuff as db


class StatusRotation:
	def __init__(self, bot):
		self.client = bot
		self.edit = asyncio.Event()
		self.coll = db.db.get_collection(name = "Statuses")
		self.data = [el["status"] for el in self.coll.find()]

		if not self.data:
			self.coll.insert_one({"status": "test"})
			self.statuses = ["test"]
		else:
			self.statuses = self.data
		
		self.edit.set()
		self.task = self.client.loop.create_task(self.change_status())
	
	async def change_status(self):
		while True:
			statuses = self.statuses[:]
			random.shuffle(statuses)
			
			for status in statuses:
				if await self.edit.wait():
					await self.client.change_presence(activity = discord.Game(name = status))
				await asyncio.sleep(180)

	def update(self):
		self.statuses = db.db.get_collection(name = "Lists").find_one({"name": "statuses"})["statuses"]

	async def change(self, value, duration = None):
		self.edit.clear()
		await self.client.change_presence(activity = discord.Game(name = value))
		if duration:
			await asyncio.sleep(duration)
			self.edit.set()

	def toggle(self, edit):
		if edit:
			self.edit.set()
		else:
			self.edit.clear()

	def stop(self):
		self.task.cancel()
