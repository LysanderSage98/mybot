from helpers.other import db_stuff as db


def guild_handler(guild):
	coll = db.db.get_collection("Lists")
	coll.update_one({
		"name": "guilds"
	}, {
		"$addToSet": {
			"joined": {
				"id": guild.id,
				"guild": guild.name,
				"owner": {
					"id": guild.owner_id,
					"name": guild.owner.name
				}
			}
		}
	}, upsert = True)
