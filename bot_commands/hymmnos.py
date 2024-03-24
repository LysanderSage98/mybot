import discord
import io

from helpers.other.permissions import Permissions
from . import Result

from PIL import Image, ImageDraw, ImageFont

font = ImageFont.truetype(font = "data/hymmnos.ttf", size = 40)


def make_temp_file(im, file_type = None, name = None):
	if file_type:
		if name:
			bytesio = io.BytesIO()
			im.save(bytesio, file_type)
			bytesio.seek(0)
			file = discord.File(bytesio, filename = name)
			return file
		else:
			raise RuntimeError("No name provided!")
	else:
		raise TypeError("No filetype provided!")


def get_text_dimensions(text_string, _font, lines = 1):  # https://levelup.gitconnected.com/how-to-properly-calculate-text-size-in-pil-images-17a2cc6f51fd
	# https://stackoverflow.com/a/46220683/9263761
	ascent, descent = _font.getmetrics()
	print(ascent, descent)
	
	text_width = _font.getmask(text_string).getbbox()[2]
	print(text_width)
	text_height = _font.getmask(text_string).getbbox()[3] + descent
	print(text_height)
	
	return text_width, (text_height - descent * (lines - 1)) * lines


@Permissions.register_command("", slash_args = {"text": str})
async def hymmnos(data: Result):
	"""creates an image containing the provided text transcribed to hymmnos
	``````py
	text: str
	"""
	content = " ".join(data.args.values())
	print(content)
	lines = content.split("\n")
	count = len(lines)
	longest = max(lines, key = lambda x: len(x))
	
	width, height = get_text_dimensions(longest, font, count)
	im = Image.new("L", (width, (height + 10) * count), 255)
	draw = ImageDraw.Draw(im)
	draw.text((0, 0), content, font = font, fill = 0)
	im = im.crop((0, 0, width, height + (10 if count == 1 else -10)))
	file = make_temp_file(im, "PNG", "hymmnos.png")

	to_send = {"file": file}
	return data, to_send
