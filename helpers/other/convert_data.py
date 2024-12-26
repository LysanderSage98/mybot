import datetime
import googleapiclient
import json
import pymongo
import re

from googleapiclient import discovery

api_args: dict = {"maxResults": 50}
api_info = json.load(open("../../data/info.json"))["api_info"]
youtube = googleapiclient.discovery.build(api_info[0], api_info[1], developerKey = api_info[2])
iso_duration_values = ["hours", "minutes", "seconds"]
iso_duration_regex = re.compile("PT" + r"".join(map(lambda el:
													rf"(?P<{el}>\d+(?={el[0].upper()}))?(?({el}){el[0].upper()}|)",
													iso_duration_values)))

client = pymongo.MongoClient()
db = client.get_database("MyBot")
coll = db.get_collection("PlayerCache")


def get_video_details(ids: list[str]):
	def duration_to_seconds(duration: str):
		match = re.search(iso_duration_regex, duration)
		matches = match.groupdict()
		if not matches:
			return 0
		return datetime.timedelta(**dict(map(lambda item: (item[0], int(item[1] or 0)), matches.items()))).total_seconds()
	
	_api_args = api_args.copy()
	_api_args["part"] = "snippet,contentDetails"
	curr = 0
	count = len(ids)
	res = []
	while curr * 50 < count:
		to_search = ids[curr * 50: (curr + 1) * 50]
		curr += 1
		_id = ",".join(to_search)
		_api_args["id"] = _id
		request = youtube.videos().list(**_api_args)
		response = request.execute()
		times = map(lambda el: (el["snippet"]["title"], duration_to_seconds(el["contentDetails"]["duration"])),
					response.get("items", []))
		res.extend(times)
	ret = list(map(lambda x: (x[0], *x[1]), zip(ids, res)))
	return ret


if __name__ == '__main__':
	data = list(coll.find())
	for el in data:
		res = get_video_details([x[0] for x in el["items"]])
		coll.find_one_and_update({"name": el["name"]}, {"$set": {"items": res}})
		# songs = el["songs"]
		# songs = {song[0].split("=")[1]: song for song in songs}
		# res = get_video_details(list(songs.keys()))
		# coll.find_one_and_update({"_id": el["_id"]},
		# 						{"$set": {"songs": [[*songs.pop(item[0]), item[1]] for item in res]}})
		# if songs:
		# 	with open("../../data/deadLinks.json", "a", encoding = "utf-8") as f:
		# 		f.write("\n" + json.dumps(songs, ensure_ascii = False))
