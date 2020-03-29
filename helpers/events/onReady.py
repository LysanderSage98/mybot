from helpers.other import status_rotation, db_handler as db


async def ready_handler(bot):
	coll = db.db.get_collection("Lists")
	coll.update_one({
		"name": "guilds"
	}, {
		"$set": {
			"name": "guilds",
			"joined": [{
				"id": guild.id,
				"name": guild.name,
				"owner": {
					"id": guild.owner_id,
					"name": guild.owner.name
				}
			} for guild in bot.guilds]
		}
	}, upsert = True)
	changer = status_rotation.StatusRotation(bot)
	return changer
