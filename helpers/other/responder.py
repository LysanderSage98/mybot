import discord


class Responder:
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

    def emb_resp(self, title: str = "", desc: str = "", color: str = None, url: str = "") -> discord.Embed:
        """Any basic embed object"""
        color = self.colors[color] if color else discord.Embed.Empty
        return discord.Embed(title = title, description = desc, url = url, color = color)

    def emb_resp2(self, msg: str) -> discord.Embed:
        """Generic error response"""
        title = "❌ Error! Something went wrong!"
        description = f"Details: {msg}"
        color = self.colors["error_2"]
        return discord.Embed(title = title, description = description, color = color)
