import asyncio

# Required by Red
import aiohttp
import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import bold, humanize_number
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS

USER_AGENT = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.72 Safari/537.36"
}


class SteamCog(commands.Cog):
    """Show various info and metadata about a Steam game."""

    __author__ = "siu3334 (<@306810730055729152>)"
    __version__ = "0.1.1"

    def format_help_for_context(self, ctx: commands.Context) -> str:
        """Thanks Sinbad!"""
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\n\nCog Version: {self.__version__}"

    def __init__(self, bot: Red):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.emojis = self.bot.loop.create_task(self.init())

    def cog_unload(self):
        if self.emojis:
            self.emojis.cancel()
        self.bot.loop.create_task(self.session.close())

    # Credits and many thanks to flare#0001 for providing this logic ❤️
    async def init(self):
        await self.bot.wait_until_ready()
        self.platform_emojis = {
            "windows": discord.utils.get(self.bot.emojis, id=501562795880349696),
            "mac": discord.utils.get(self.bot.emojis, id=501561088815661066),
            "linux": discord.utils.get(self.bot.emojis, id=501561148156542996),
        }

    # Logic taken from https://github.com/TrustyJAID/Trusty-cogs/blob/master/notsobot/notsobot.py#L212
    # All credits to TrustyJAID ❤️, I do not claim any credit for this.
    async def fetch_steam_game_id(self, ctx: commands.Context, query: str):
        url = "https://store.steampowered.com/api/storesearch"
        params = {"cc": "us", "l": "en", "term": query}
        try:
            async with self.session.get(url, params=params, headers=USER_AGENT) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
        except asyncio.TimeoutError:
            return None

        if data.get("total") == 0:
            return None
        elif data.get("total") == 1:
            app_id = data.get("items")[0].get("id")
            return app_id
        elif data.get("total") > 1:
            # This logic taken from https://github.com/Sitryk/sitcogsv3/blob/master/lyrics/lyrics.py#L142
            # All credits belong to Sitryk, I do not take any credit for this code snippet.
            items = ""
            for count, value in enumerate(data.get("items")):
                items += "**{}.** {}\n".format(count + 1, value.get("name"))
            choices = (
                f"Found multiple results for your game query. Please select one from:\n\n{items}"
            )
            send_to_channel = await ctx.send(choices)

            def check(msg):
                content = msg.content
                if (
                    content.isdigit()
                    and int(content) in range(0, len(items) + 1)
                    and msg.author is ctx.author
                    and msg.channel is ctx.channel
                ):
                    return True

            try:
                choice = await self.bot.wait_for("message", timeout=60.0, check=check)
            except asyncio.TimeoutError:
                choice = None

            if choice is None or choice.content.strip() == "0":
                await send_to_channel.edit(content="Operation cancelled.")
                return None
            else:
                choice = choice.content.strip()
                choice = int(choice) - 1
                app_id = data.get("items")[choice].get("id")
                await send_to_channel.delete()
                return app_id
        else:
            return None

    @commands.command()
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True, read_message_history=True)
    async def steam(self, ctx: commands.Context, *, query: str):
        """Show various info and metadata about a Steam game."""
        await ctx.trigger_typing()
        app_id = await self.fetch_steam_game_id(ctx, query)
        base_url = "https://store.steampowered.com/api/appdetails"
        params = {"appids": app_id, "l": "en", "cc": "us", "json": 1}

        if not app_id:
            return await ctx.send("Could not find any results.")
        try:
            async with self.session.get(base_url, params=params, headers=USER_AGENT) as response:
                if response.status != 200:
                    return await ctx.send(f"https://http.cat/{response.status}")
                data = await response.json()
        except asyncio.TimeoutError:
            return await ctx.send("Operation timed out.")

        appdata = data[f"{app_id}"].get("data")

        pages = []
        embed = discord.Embed(
            title=appdata["name"],
            description=appdata.get("short_description", "No description."),
            colour=await ctx.embed_color(),
        )
        embed.url = f"https://store.steampowered.com/app/{app_id}"
        embed.set_author(name="Steam", icon_url="https://i.imgur.com/xxr2UBZ.png")
        embed.set_image(url=str(appdata.get("header_image")).replace("\\", ""))
        if appdata.get("price_overview") is not None:
            embed.add_field(
                name="Game Price",
                value=appdata["price_overview"].get("final_formatted"),
            )
        if appdata.get("release_date").get("coming_soon"):
            embed.add_field(name="Release Date", value="Coming Soon")
        else:
            embed.add_field(name="Release Date", value=appdata["release_date"].get("date"))
        if appdata.get("metacritic") is not None:
            metacritic = (
                bold(str(appdata.get("metacritic").get("score")))
                + f" ([Critic Reviews]({appdata['metacritic'].get('url')}))"
            )
            embed.add_field(name="Metacritic Score", value=metacritic)
        if appdata.get("recommendations") is not None:
            embed.add_field(
                name="Recommendations",
                value=humanize_number(appdata["recommendations"].get("total")),
            )
        if appdata.get("achievements") is not None:
            embed.add_field(name="Achievements", value=appdata["achievements"].get("total"))
        if appdata.get("dlc") is not None:
            embed.add_field(name="DLC Count", value=len(appdata["dlc"]))
        embed.add_field(name="Developers", value=", ".join(appdata.get("developers")))
        embed.add_field(name="Publishers", value=", ".join(appdata.get("publishers")))
        if appdata.get("platforms"):
            windows_emoji = self.platform_emojis["windows"] or "Microsoft Windows\n"
            linux_emoji = self.platform_emojis["linux"] or "Linux\n"
            macos_emoji = self.platform_emojis["mac"] or "Mac OS\n"
            platforms = ""
            if appdata["platforms"].get("windows"):
                platforms += f"{windows_emoji}"
            if appdata["platforms"].get("linux"):
                platforms += f" {linux_emoji}"
            if appdata["platforms"].get("mac"):
                platforms += f" {macos_emoji}"
            embed.add_field(name="Supported Platforms", value=platforms)
        if appdata.get("genres"):
            genres = ", ".join(m.get("description") for m in appdata["genres"])
            embed.add_field(name="Genres", value=genres)
        footer = "Click on reactions to browse through this game's screenshot previews\n"
        if appdata.get("content_descriptors").get("notes"):
            footer += f"Note: {appdata['content_descriptors']['notes']}"
        embed.set_footer(text=footer)
        pages.append(embed)

        if appdata.get("screenshots"):
            for i, preview in enumerate(appdata["screenshots"]):
                embed = discord.Embed(colour=await ctx.embed_color())
                embed.title = appdata["name"]
                embed.url = f"https://store.steampowered.com/app/{app_id}"
                embed.set_author(name="Steam", icon_url="https://i.imgur.com/xxr2UBZ.png")
                embed.set_image(url=preview["path_full"])
                embed.set_footer(text=f"Preview {i + 1} of {len(appdata['screenshots'])}")
                pages.append(embed)

        if len(pages) == 1:
            return await ctx.send(embed=pages[0])
        else:
            await menu(ctx, pages, DEFAULT_CONTROLS, timeout=60.0)
