"""This is a cog for a discord.py bot.
It will add some management commands to a bot.

Commands:
    load            load an extension / cog
    unload          unload an extension / cog
    reload          reload an extension / cog
    cogs            show currently active extensions / cogs
    error           print the traceback of the last unhandled error to chat
"""
import json
import typing
import subprocess
import re
from io import BytesIO
from datetime import datetime, timezone
from os import path, listdir
from discord import File, errors as discord_errors
from discord.ext import commands


class Management(commands.Cog, name='Management'):
    def __init__(self, client):
        self.client = client
        self.reload_config()
        self.cog_re = re.compile(r'\s*src\/cogs\/(.+)\.py\s*\|\s*\d+\s*[+-]+')

    async def cog_check(self, ctx):
        return self.client.user_is_admin(ctx.author)

    @commands.Cog.listener()
    async def on_ready(self):
        loaded = self.client.extensions
        unloaded = [x for x in self.crawl_cogs() if x not in loaded and 'extra.' not in x]
        activity = self.client.error_activity if unloaded else self.client.default_activity
        await self.client.change_presence(activity=activity)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        self.client.recent_guilds_joined.append(
            (datetime.now(tz=timezone.utc).isoformat()[:19], guild)
        )
        self.client.recent_guilds_joined = self.client.recent_guilds_joined[-10:]

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        self.client.recent_guilds_left.append(
            (datetime.now(tz=timezone.utc).isoformat()[:19], guild)
        )
        self.client.recent_guilds_left = self.client.recent_guilds_left[-10:]

    def reload_config(self):
        with open("../state/config.json") as conffile:
            self.client.config = json.load(conffile)

    def crawl_cogs(self, directory='cogs'):
        cogs = []
        for element in listdir(directory):
            if element in ('samples', 'utils'):
                continue
            abs_el = path.join(directory, element)
            if path.isdir(abs_el):
                cogs += self.crawl_cogs(abs_el)
            else:
                filename, ext = path.splitext(element)
                if ext == '.py':
                    dot_dir = directory.replace('\\', '.')
                    dot_dir = dot_dir.replace('/', '.')
                    cogs.append(f'{dot_dir}.' + filename)
        return cogs

    # ----------------------------------------------
    # Function to load extensions
    # ----------------------------------------------
    @commands.command(
        name='load',
        brief='Load bot extension',
        description='Load bot extension',
        hidden=True,
    )
    async def load_extension(self, ctx, extension_name):
        for cog_name in self.crawl_cogs():
            if extension_name in cog_name:
                target_extension = cog_name
                break
        try:
            await self.client.load_extension(target_extension)
        except Exception as e:
            await self.client.log_error(e, ctx)
            await ctx.send(f'```py\n{type(e).__name__}: {str(e)}\n```')
            return
        await ctx.send(f'```css\nExtension [{target_extension}] loaded.```')

    # ----------------------------------------------
    # Function to unload extensions
    # ----------------------------------------------
    @commands.command(
        name='unload',
        brief='Unload bot extension',
        description='Unload bot extension',
        hidden=True,
    )
    async def unload_extension(self, ctx, extension_name):
        for cog_name in self.client.extensions:
            if extension_name in cog_name:
                target_extension = cog_name
                break
        if target_extension.lower() in 'cogs.management':
            await ctx.send(
                f"```diff\n- {target_extension} can't be unloaded" +
                f"\n+ try reload instead```"
            )
            return
        if self.client.extensions.get(target_extension) is None:
            return
        await self.client.unload_extension(target_extension)
        await ctx.send(f'```css\nExtension [{target_extension}] unloaded.```')

    # ----------------------------------------------
    # Function to reload extensions
    # ----------------------------------------------
    @commands.command(
        name='reload',
        brief='Reload bot extension',
        description='Reload bot extension',
        hidden=True,
        aliases=['re']
    )
    async def reload_extension(self, ctx, extension_name):
        target_extensions = []
        if extension_name == 'all':
            target_extensions = [__name__] + \
                [x for x in self.client.extensions if not x == __name__]
        else:
            for cog_name in self.client.extensions:
                if extension_name in cog_name:
                    target_extensions = [cog_name]
                    break
        if not target_extensions:
            return
        result = []
        for ext in target_extensions:
            try:
                await self.client.reload_extension(ext)
                result.append(f'Extension [{ext}] reloaded.')
            except Exception as e:
                await self.client.log_error(e, ctx)
                result.append(f'#ERROR loading [{ext}]')
                continue
        result = '\n'.join(result)
        await ctx.send(f'```css\n{result}```')

    # ----------------------------------------------
    # Function to get bot extensions
    # ----------------------------------------------
    @commands.command(
        name='cogs',
        brief='Get loaded cogs',
        description='Get loaded cogs',
        aliases=['extensions'],
        hidden=True,
    )
    async def print_cogs(self, ctx):
        loaded = self.client.extensions
        unloaded = [x for x in self.crawl_cogs() if x not in loaded]
        response = ['\n[Loaded extensions]'] + ['\n  ' + x for x in loaded]
        response += ['\n[Unloaded extensions]'] + \
            ['\n  ' + x for x in unloaded]
        await ctx.send(f'```css{"".join(response)}```')
        return True

    @commands.command(
        name='servers',
        hidden=True,
    )
    async def show_servers(self, ctx, include_txt: bool = False):
        to_send = '\n'.join(str(guild) for guild in self.client.guilds)
        file = File(
            fp=BytesIO(to_send.encode()),
            filename=f'servers_{datetime.now(tz=timezone.utc).isoformat()}.txt'
        ) if include_txt else None
        j = '\n'.join(f'{time} | {guild.name}' for time, guild in self.client.recent_guilds_joined)
        l = '\n'.join(f'{time} | {guild.name}' for time, guild in self.client.recent_guilds_left)
        await ctx.send(
            f'**I am active in {len(self.client.guilds)} Servers ' +
            f'| # of Shards: {len(self.client.shards)}** ' +
            f'```\nJoined recently:\n{j}```\n```\nLeft Recently:\n{l}```',
            file=file
        )

    # ----------------------------------------------
    # Command to pull the latest changes from github
    # ----------------------------------------------
    @commands.group(
        name='git',
        hidden=True,
    )
    async def git(self, ctx):
        """Commands to run git commands on the local repo"""
        pass

    @git.command(
        name='pull',
    )
    async def pull(self, ctx, noreload: typing.Optional[str] = None):
        """Pull the latest changes from github"""
        try:
            await ctx.trigger_typing()
        except discord_errors.Forbidden:
            pass
        try:
            output = subprocess.check_output(
                ['git', 'pull']).decode()
            await ctx.send('```git\n' + output + '\n```')
        except Exception as e:
            return await ctx.send(str(e))

        if noreload is not None:
            return

        _cogs = [f'cogs.{i}' for i in self.cog_re.findall(output)]
        active_cogs = [i for i in _cogs if i in self.client.extensions]
        if active_cogs:
            for cog_name in active_cogs:
                await ctx.invoke(self.client.get_command('reload'), cog_name)

    # ----------------------------------------------
    # Command to reset the repo to a previous commit
    # ----------------------------------------------
    @git.command(
        name='reset',
    )
    async def reset(self, ctx, n: int):
        """Reset repo to HEAD~[n]"""
        if not n > 0:
            raise commands.BadArgument('Please specify n>0')
        try:
            await ctx.trigger_typing()
        except discord_errors.Forbidden:
            pass
        try:
            output = subprocess.check_output(
                ['git', 'reset', '--hard', f'HEAD~{n}']).decode()
            await ctx.send('```git\n' + output + '\n```')
        except Exception as e:
            await ctx.send(str(e))

    # ----------------------------------------------
    # Command to stop the bot
    # ----------------------------------------------
    @commands.command(
        name='restart',
        aliases=['shutdown'],
        hidden=True
    )
    async def shutdown(self, ctx):
        """Stop/Restart the bot"""
        await self.client.close()

    # ----------------------------------------------
    # Command to toggle maintenance mode
    # ----------------------------------------------
    @commands.command(
        name='maintenance',
        hidden=True
    )
    async def maintenance(self, ctx):
        """Toggle maintenance mode"""
        if self.client.maintenance_mode:
            self.client.maintenance_mode = False
            await self.client.change_presence(activity=self.client.default_activity)
        else:
            self.client.maintenance_mode = True
            await self.client.change_presence(activity=self.client.maintenance_activity)


async def setup(client):
    await client.add_cog(Management(client))
