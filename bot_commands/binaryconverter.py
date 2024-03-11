import typing

from helpers.other.permissions import Permissions
from . import Result

@Permissions.register_command("", slash_args = {"arg0": typing.Optional[typing.Literal['-hex', '-oct']], "some_text": str})
async def binaryconverter(data: Result):
	"""Convert text from or to binary, octal or hexadecimal format.
	``````py
	arg0: typing.Literal
		other formats
	some_text: str
		the text you want to convert
	"""
	# raise RuntimeError("__**Not implemented yet!**__")  # TODO implement command 'binaryconverter'
	bases = {
		"-bin": ("0b", 2),
		"-oct": ("0o", 8),
		"-hex": ("0x", 16)
	}
	formatting = data.args.get("arg0", data.args.get("0", "-bin"))
	s = data.args.get("some_text", data.args.get("0" if formatting == "-bin" else "-1", " ".join(data.args.values())))

	try:  # to convert from binary to text
		res = "".join(
			list(
				map(
					lambda x: chr(
						int(
							bases[formatting][0] + x,
							bases[formatting][1]
						)
					) if len(x) else None,
					s.split()
				)
			)
		)
		encrypt = True
	except ValueError:  # convert from text to binary
		res = " ".join([eval(bases[formatting])(ord(x))[2:] for x in s])
		encrypt = False

	title = f"Converted from {formatting} to normal text" if encrypt else f"Convert from normal text to {formatting}"
	embed = data.bot.responder.emb_resp(title, res, "success")

	to_send = {"embed": embed}
	return data, to_send
