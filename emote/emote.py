from redbot.core import Config, checks, commands
from redbot.core.bot import Red
from redbot.core.data_manager import cog_data_path

from aiohttp import ClientSession
from asyncio import TimeoutError
from discord import File, Guild, Message
from itertools import product
from os import remove, rename, scandir
from PIL import Image
from re import compile, findall
from typing import List


# if this seem hard to read/understand, remove the comments. Might make it easier


class Emote(commands.Cog):
    """Emote was made using irdumb's sadface cog's code.
    Owner is responsible for its handling."""

    default_guild_settings = {"status": False, "emotes": {}}

    def __init__(self, bot: Red):
        self.bot = bot
        self._emote = Config.get_conf(self, 1824791591)
        self._emote_path = cog_data_path(self) / "images"

        self._emote.register_guild(**self.default_guild_settings)

        self.session = ClientSession(loop=self.bot.loop)

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

    __unload = cog_unload

    # doesn't make sense to use this command in a pm, because pms aren't in servers
    # mod_or_permissions needs something in it otherwise it's mod or True which is always True
    @commands.group()
    @commands.guild_only()
    async def emotes(self, ctx: commands.Context) -> None:
        """Emote settings"""
        pass

    @emotes.command()
    @checks.mod_or_permissions(manage_roles=True)
    @commands.guild_only()
    async def set(self, ctx: commands.Context) -> None:
        """Enables/Disables emotes for this server"""
        # default off.
        guild = ctx.guild
        status = not await self._emote.guild(guild).status()
        await self._emote.guild(guild).status.set(status)
        # for a toggle, settings should save here in case bot fails to send message
        if status:
            await ctx.send(
                "Emotes on. Please turn this off in the Red - DiscordBot server."
                " This is only an example cog."
            )
        else:
            await ctx.send("Emotes off.")

    @emotes.command()
    @checks.is_owner()
    @commands.guild_only()
    async def add(self, ctx: commands.Context, name: str, url: str) -> None:
        """Allows you to add emotes to the emote list
        [p]emotes add pan http://i.imgur.com/FFRjKBW.gifv"""
        guild = ctx.guild
        name = name.lower()
        emotes = await self._emote.guild(guild).emotes()
        option = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/52.0.2743.116 Safari/537.36"
        }
        if not url.endswith((".gif", ".gifv", ".png")):
            await ctx.send(
                "Links ending in .gif, .png, and .gifv are the only ones accepted."
                "Please try again with a valid emote link, thanks."
            )
            return
        if name in emotes:
            await ctx.send("This keyword already exists, please use another keyword.")
            return
        if url.endswith(".gifv"):
            url = url.replace(".gifv", ".gif")
        try:
            await ctx.send(f"Downloading {name}.")
            async with self.session.get(url, headers=option) as r:
                emote = await r.read()
                print(self._emote_path)
                emote_info = f"{name}.{url[-3:]}"
                with open(self._emote_path + emote_info, "wb") as f:
                    f.write(emote)
                await ctx.send(f"Adding {name} to the list.")
                emotes[name] = emote_info
                await self._emote.guild(guild).emotes.set(emotes)
            await ctx.send(f"{name} has been added to the list")
        except Exception as e:
            print(e)
            await ctx.send(
                "It seems your url is not valid."
                " Please make sure you are not typing names with spaces"
                " as the url might be confused for that."
                " If you want to save an emote with spaces in the name, do"
                " [p]emotes add name_with_spaces url"
                f" Attached is the exception: {e}"
            )

    @checks.is_owner()
    @emotes.command()
    @commands.guild_only()
    async def remove(self, ctx: commands.Context, name: str) -> None:
        """Allows you to remove emotes from the emotes list"""
        guild = ctx.guild
        name = name.lower()
        emotes = await self._emote.guild(guild).emotes()
        try:
            if name in emotes:
                remove(self._emote + emotes[name])
                del emotes[name]
            else:
                await ctx.send(
                    f"{name} is not a valid name, please make sure the name of the"
                    " emote that you want to remove actually exists."
                    " Use [p]emotes list to verify it's there."
                )
                return
            await self._emote.guild(guild).emotes.set(emotes)
            await ctx.send(f"{name} has been removed from the list")
        except FileNotFoundError:
            await ctx.send(
                "For some unknown reason, your emote is not available in the default directory"
                ", that is, data/emote/images. This means that it can't be removed. "
                "But it has been successfully removed from the emotes list."
            )

    @checks.is_owner()
    @emotes.command()
    @commands.guild_only()
    async def edit(self, ctx: commands.Context, name: str, newname: str) -> None:
        """Allows you to edit the keyword that triggers the emote
        from the emotes list"""
        guild = ctx.guild
        name = name.lower()
        emotes = await self._emote.guild(guild).emotes()
        if newname in emotes:
            await ctx.send("This keyword already exists, please use another keyword.")
            return
        try:
            if name in emotes:
                emotes[newname] = f"{newname}.{emotes[name[-3:]]}"
                rename(self._emote + emotes[name], self._emote + emotes[newname])
                del emotes[name]
            else:
                await ctx.send(
                    f"{name} is not a valid name, please make sure the name of the"
                    " emote that you want to edit exists"
                    " Use [p]emotes list to verify it's there."
                )
                return
            await self._emote.guild(guild).emotes.set(emotes)
            await ctx.send(f"{name} in the emotes list has been renamed to {newname}")
        except FileNotFoundError:
            await ctx.send(
                "For some unknown reason, your emote is not available in the default directory,"
                " that is, data/emote/images. This means that it can't be edited."
                " But it has been successfully edited in the emotes list."
            )

    @emotes.command()
    @commands.guild_only()
    async def list(self, ctx: commands.Context, style: str) -> None:
        """Shows you the emotes list.
        Supported styles: [p]emotes list 10 (shows 10 emotes per page)
        and [p]emotes list a (shows all the emotes beginning with a)"""
        guild = ctx.guild
        style = style.lower()
        emotes = await self._emote.guild(guild).emotes()
        istyles = sorted(emotes)
        if not istyles:
            await ctx.send(
                "Your emotes list is empty."
                " Please add a few emotes using the [p]emote add function."
            )
            return
        if style.isdigit():
            if style == "0":
                await ctx.send("Only numbers from 1 to infinite are accepted.")
                return
            style = int(style)
            istyle = istyles
        elif style.isalpha():
            istyle = []
            for i in range(len(istyles)):
                ist = findall(f"\\b{style}\\w+", istyles[i])
                if len(ist) > 0:
                    istyle = istyle + ist
            style = 10
        else:
            await ctx.send(
                "Your list style is not correct, please use one"
                " of the accepted styles, either do [p]emotes list A or [p]emotes list 10"
            )
            return
        msg = "List of available emotes:\n"
        self.emote_paging(ctx, istyle, msg, style)

    @checks.is_owner()
    @emotes.command()
    @commands.guild_only()
    async def compare(
        self, ctx: commands.Context, style: str, all_keyword: str = None
    ) -> None:
        """Allows you to compare keywords to files
        or files to keywords and then make sure that
        they all match.
        Keywords to Files name: K2F
        Files to Keywords name: F2K
        [p]emotes compare K2F
        [p]emotes compare K2F all
        [p]emotes compare F2K all"""
        style = style.lower()
        if all_keyword is not None:
            all_keyword = all_keyword.lower()
        styleset = ["k2f", "f2k"]
        if style not in styleset:
            return
        msg = "Keywords deleted due to missing files in the emotes list:\n"
        c = list()
        for entry in scandir(str(self._emote_path)):
            c.append(entry.name)
        if style == styleset[0]:
            if all_keyword == "all":
                self.k2f_all_function(ctx, msg, c)
            else:
                self.k2f_function(ctx, msg, c)
        elif style == styleset[1]:
            if all_keyword == "all":
                self.f2k_all_function(ctx, c)
            else:
                self.f2k_function(ctx, c)

    async def f2k_function(
        self,
        ctx: commands.Context,
        c: List[str],
        guild: Guild = None,
        in_guild: bool = False,
    ) -> None:
        msg = "All files and keywords are accounted for"
        if in_guild:
            msg = msg + f" in {guild}"
        if guild is None:
            guild = ctx.guild
        emotes = await self._emote.guild(guild).emotes()
        count = 0
        for emote in c:
            listing = emote.split(".")
            if listing[0] not in emotes:
                emotes[listing[0]] = emote
                count += 1
        if count == 0:
            await ctx.send(msg)
        else:
            count_msg = (
                f"{count} Keywords have been successfully added to the image list"
            )
            if in_guild:
                count_msg = count_msg + f" in {guild}"
            await self._emote.guild(guild).emotes.set(emotes)
            await ctx.send(count_msg)

    async def f2k_all_function(self, ctx: commands.Context, c: List[str]) -> None:
        if not c:
            await ctx.send(
                "It is impossible to verify the integrity of files and "
                "keywords due to missing files. Please make sure that the"
                " files have not been deleted."
            )
            return
        servers = sorted(await self._emote.all_guilds())
        for guild in servers:
            self.f2k_function(ctx, c, guild, in_guild=True)

    async def k2f_all_function(self, ctx: commands.Context, msg, c) -> None:
        servers = sorted(await self._emote.all_guilds())
        for guild in servers:
            self.k2f_function(ctx, msg, c, guild, in_guild=True)

    async def k2f_function(
        self,
        ctx: commands.Context,
        msg: str,
        c: List[str],
        guild: Guild = None,
        in_guild: bool = False,
    ) -> None:
        missing_msg = "All files and keywords are accounted for"
        if in_guild:
            missing_msg = missing_msg + f" in {guild}"
        if guild is None:
            guild = ctx.guild
        missing = list()
        emotes = await self._emote.guild(guild).emotes()
        istyles = sorted(emotes)
        for n in istyles:
            emote = "|".join(c)
            if not n[0].isalnum():
                z = compile(r"\B" + n + r"\b")
            else:
                z = compile(r"\b" + n + r"\b")
            if z.search(emote) is None:
                missing.append(n)
        if not missing:
            await ctx.send(missing_msg)
        else:
            for m in missing:
                if m in emotes:
                    del emotes[m]
            await self._emote.guild(guild).emotes.set(emotes)
            self.emote_paging(ctx, missing, msg)

    async def emote_paging(
        self, ctx: commands.Context, missing: List[str], msg: str, style: int = 10
    ) -> None:
        s = "\n".join
        count = style
        counter = len(missing) + style
        while style <= counter:
            if style <= count:
                y = s(missing[:style])
                await ctx.send(msg + y)
                if style >= len(missing):
                    return
                style += count
            elif style > count:
                style2 = style - count
                y = s(missing[style2:style])
                await ctx.send(f"Continuation:\n{y}")
                if style >= len(missing):
                    return
                style += count
            await ctx.send("Do you want to continue seeing the list? Yes/No")

            def check(m):
                return (
                    m.content.lower().strip() in ["yes", "no"]
                    and m.author == ctx.author
                )

            try:
                answer = await self.bot.wait_for("messsage", timeout=15, check=check)
            except TimeoutError:
                return
            else:
                if answer.content.lower().strip() == "yes":
                    continue
                return

    async def check_emotes(self, message: Message) -> None:
        # check if setting is on in this server
        # Let emotes happen in PMs always
        guild = message.guild
        if guild is None:
            return
        emotes = await self._emote.guild(guild).emotes()
        # Filter unauthorized users, bots and empty messages
        if not message.content:
            return

        # Don't respond to commands
        for m in await self.bot.db.prefix():
            if message.content.startswith(m):
                return

        if guild is not None:
            if not (await self._emote.guild(guild).status()):
                return

        msg = message.content.lower().split()
        listed = []
        regexen = []
        for n in sorted(emotes):
            if not n[0].isalnum():
                regexen.append(compile(r"\B" + n + r"\b"))
            else:
                regexen.append(compile(r"\b" + n + r"\b"))

        for w, r in product(msg, regexen):
            match = r.search(w)
            if match:
                listed.append(emotes[match.group(0)])

        pnglisted = list(filter(lambda n: not n.endswith(".gif"), listed))
        giflisted = list(filter(lambda n: n.endswith(".gif"), listed))
        if pnglisted and len(pnglisted) > 1:
            ims = self.imgprocess(pnglisted)
            image = self._emote_path / ims
            await message.channel.send(file=File(str(image)))
        elif pnglisted:
            image = self._emote_path / pnglisted[0]
            await message.channel.send(file=File(str(image)))
        if giflisted:
            for ims in giflisted:
                image = self._emote_path / ims
                await message.channel.send(file=File(str(image)))

    def imgprocess(self, listed: list) -> str:
        for i in range(len(listed)):
            listed[i] = str(self._emote_path / listed[i])
        images = [Image.open(i) for i in listed]
        widths, heights = zip(*(i.size for i in images))
        total_width = sum(widths)
        max_height = max(heights)
        new_im = Image.new("RGBA", (total_width, max_height))
        x_offset = 0
        for im in images:
            new_im.paste(im, (x_offset, 0))
            x_offset += im.size[0]
        final_image = "test.png"
        new_im.save(self._emote_path + final_image)
        return final_image
