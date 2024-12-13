import aiohttp
import bs4
import datetime
import typing
import re

from helpers.other.permissions import Permissions
from . import Result

time_is_settings = "?c=d3l1_3F_3j1_3Y1_3WXtH2i2sXfmtsXc0Xo120Xz1Xa1Xb51ea29.4e4185.28571f.2d99db.80265.1bb85e" \
	".1c3b23Xw0Xv20200430Xh0Xi1XZ1XmXuXB0&l=en "
time_formats = {
	r"^\d{1,2}:\d{1,2}:\d{1,2}_\d{1,2}.\d{1,2}.\d{4}$": "%H:%M:%S_%d.%m.%Y",
	r"^\d{1,2}:\d{1,2}_\d{1,2}.\d{1,2}.\d{4}$": "%H:%M_%d.%m.%Y",
	r"^\d{1,2}.\d{1,2}.\d{4}_\d{1,2}:\d{1,2}:\d{1,2}$": "%d.%m.%Y_%H:%M:%S",
	r"^\d{1,2}.\d{1,2}.\d{4}_\d{1,2}:\d{1,2}$": "%d.%m.%Y_%H:%M"
}


@Permissions.register_command("", slash_args = {
	"arg0": typing.Literal['time_date', 'time', 'date'], "value": str,
	"location1": str, "location3": typing.Optional[str], "location2": typing.Optional[str]})
async def comparetime(data: Result):
	"""Compare times between locations.
	``````py
	arg0: typing.Literal
	value: str
		value for arg0
	location1: str
	location3: str
	location2: str
	"""
	from helpers.other.utilities import Markdown

	args = data.args
	if not args:
		data.error = data.bot.responder.emb_resp("Error", "No time or place(s) given!", "error")
		return data
	elif len(args) < 3:
		data.error = data.bot.responder.emb_resp("Error", "Not enough arguments given!", "error")  # todo test
		return data
	
	kind = args.pop("arg0", args.pop("0", ""))
	time = args.pop("value", args.pop("1", ""))
	place = args.pop("location1", args.pop("2", ""))
	if args:
		print(args)
		places = [args.pop(f"location{2 + x}", args.pop(f"{3 + x}", None)) for x in range(len(args))]
	else:
		places = []
	print(time, place, places)
	base = "https://www.time.is/"
	if kind == "time":
		time += datetime.datetime.today().strftime("_%d.%m.%Y")
	elif kind == "date":
		time = datetime.datetime.now(datetime.UTC).strftime("%H:%M_") + time
	print(time)
	fmt = None
	for item in time_formats:
		if re.match(item, time):
			fmt = time_formats[item]
			break
	else:
		embed = data.bot.responder.emb_resp("Error", "Invalid time format!", "error")
	
	if fmt:
		t = datetime.datetime.strptime(time, fmt)
		t = t.replace(tzinfo = datetime.timezone.utc)
		time_new = t.strftime("%H%M_%d_%B_%Y")
		time_in = f"{time_new}_in_{place}/{'/'.join(filter(None, places))}"
		print(time_in)
		url = base + time_in
		
		async with aiohttp.request("GET", url + time_is_settings) as resp:
			if resp.status == 400:
				embed = data.bot.responder.emb_resp("Error", f"Invalid syntax, check {data.prefix}help comparetime!", "error")
			else:
				text = await resp.text()
				html = bs4.BeautifulSoup(text, "html.parser")
				info = html.find(attrs = {"class": "w90"})
		
				title = ''.join(info.find_all('h1')[0].strings)
				embed = data.bot.responder.emb_resp(title, "", "success", url = url.replace(" ", "_"))
				
				print(t.timestamp())
				desc = f"{Markdown.hb_('Difference between now and the requested time: ')}{Markdown.tr_(t.timestamp())}\n"
				
				if places:
					append = Markdown.hm_('Comparison with the other places:')
					n_places = info.find(attrs = {"class": "tbx leftfloat"}).find_all("h2")
					for pl in n_places:
						loc_info = list(pl.strings)
						name = loc_info.pop(0)
						if name not in title:
							value = f'{Markdown.cb_("".join(loc_info))}'
							embed.add_field(name = name, value = value)
				
				else:
					append = ""
				
				embed.description = desc + append
	
	to_send = {"embed": embed}
	return data, to_send
