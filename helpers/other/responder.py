import datetime
import discord


class Responder:
    __slots__ = ("colors", "ok", "std_info", "info", "error", "error_2", "success")

    def __init__(self):
        self.colors = {
            "": 0,
            "ok": 0x00FF00,
            "std_info": 0xF0F8FF,
            "info": 0x000000,
            "error": 0xFF0000,
            "error_2": 0xCD00CD,
            "success": 0xFFFF00
        }
        self.ok = "ok"
        self.std_info = "std_info"
        self.info = "info"
        self.error = "error"
        self.error_2 = "error_2"
        self.success = "success"

    def emb_resp(self, title: str = "", desc: str = "", color: str = None, url: str = "") -> discord.Embed:
        """Any basic embed object"""
        color = self.colors[color] if color else None
        return discord.Embed(
            title = title,
            description = desc,
            url = url,
            color = color,
            timestamp = datetime.datetime.utcnow()
        )

    def emb_resp2(self, msg: str) -> discord.Embed:
        """Generic error response"""
        title = "❌ Error! Something went wrong!"
        description = f"### Details:\n{msg}"
        color = self.colors["error_2"]
        return discord.Embed(title = title, description = description, color = color)
