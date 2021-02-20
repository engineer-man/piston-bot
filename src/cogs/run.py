"""This is a cog for a discord.py bot.
It will add the run command for everyone to use

Commands:
    run            Run code using the Piston API

"""
# pylint: disable=E0402
import json
import re
from dataclasses import dataclass
from discord import Embed, Message, errors as discord_errors
from discord.ext import commands, tasks
from discord.utils import escape_mentions
from aiohttp import ContentTypeError
from .utils.codeswap import add_boilerplate
from .utils.errors import PistonInvalidContentType, PistonInvalidStatus, PistonNoOutput
#pylint: disable=E1101


@dataclass
class RunIO:
    input: Message
    output: Message


class Run(commands.Cog, name='CodeExecution'):
    def __init__(self, client):
        self.client = client
        self.run_IO_store = dict()  # Store the most recent /run message for each user.id
        self.run_regex = re.compile(
            r'(?s)/(?:edit_last_)?run(?: +(?P<language>\S*)\s*|\s*)(?:\n'
            r'(?P<args>(?:[^\n\r\f\v]*\n)*?)\s*|\s*)'
            r'```(?:(?P<syntax>\S+)\n\s*|\s*)(?P<source>.*)```'
            r'(?:\n?(?P<stdin>(?:[^\n\r\f\v]\n?)+)+|)'
        )
        self.languages = dict()  # Store the supported languages and aliases
        self.get_available_languages.start()

    @tasks.loop(count=1)
    async def get_available_languages(self):
        async with self.client.session.get(
            'https://emkc.org/api/v1/piston/versions'
        ) as response:
            versions = await response.json()
        for version in versions:
            language = version['name']
            for alias in version['aliases']:
                self.languages[alias] = language

    async def send_to_log(self, ctx, language, source):
        logging_data = {
            'server': ctx.guild.name if ctx.guild else 'DMChannel',
            'server_id': str(ctx.guild.id) if ctx.guild else '0',
            'user': f'{ctx.author.name}#{ctx.author.discriminator}',
            'user_id': str(ctx.author.id),
            'language': language,
            'source': source
        }
        headers = {'Authorization': self.client.config["emkc_key"]}

        async with self.client.session.post(
            'https://emkc.org/api/internal/piston/log',
            headers=headers,
            data=json.dumps(logging_data)
        ) as response:
            if response.status != 200:
                await self.client.log_error(
                    commands.CommandError(f'Error sending log. Status: {response.status}'),
                    ctx
                )
                return False

        return True

    async def get_run_output(self, ctx):
        if ctx.message.content.count('```') != 2:
            raise commands.BadArgument('Invalid command format (missing codeblock?)')

        match = self.run_regex.search(ctx.message.content)

        if not match:
            raise commands.BadArgument('Invalid command format')

        language, args, syntax, source, stdin = match.groups()

        if args:
            args = [arg for arg in args.strip().split('\n') if arg]

        if not language:
            language = syntax

        if language not in self.languages:
            raise commands.BadArgument(f'Unsupported language: {language}')

        if not source:
            raise commands.BadArgument(f'No source code found')

        # Resolve aliases for language
        language = self.languages[language]

        # Add boilerplate code to supported languages
        source = add_boilerplate(language, source)

        # Call piston API
        data = {
            'language': language, 'source': source, 'args': args, 'stdin': stdin or "", 'log': 0
        }
        headers = {'Authorization': self.client.config["emkc_key"]}

        async with self.client.session.post(
            'https://emkc.org/api/v1/piston/execute',
            headers=headers,
            data=json.dumps(data)
        ) as response:
            try:
                r = await response.json()
            except ContentTypeError:
                raise PistonInvalidContentType('invalid content type')
        if not response.status == 200:
            raise PistonInvalidStatus(f'{response.status}{r.get("message", "")}')
        if r['output'] is None:
            raise PistonNoOutput('no output')

        # Logging
        await self.send_to_log(ctx, language, source)

        # Return early if no output was received
        if len(r['output']) == 0:
            return f'Your code ran without output {ctx.author.mention}'

        # Limit output to 30 lines maximum
        output = '\n'.join(r['output'].split('\n')[:30])

        # Prevent mentions in the code output
        output = escape_mentions(output)

        # Prevent code block escaping by adding zero width spaces to backticks
        output = output.replace("`", "`\u200b")

        # Truncate output to be below 2000 char discord limit.
        if len(r['stdout']) == 0 and len(r['stderr']) > 0:
            introduction = f'{ctx.author.mention} I only received error output\n'
        else:
            introduction = f'Here is your output {ctx.author.mention}\n'
        truncate_indicator = '[...]'
        len_codeblock = 7  # 3 Backticks + newline + 3 Backticks
        available_chars = 2000-len(introduction)-len_codeblock
        if len(output) > available_chars:
            output = output[:available_chars-len(truncate_indicator)] + truncate_indicator

        return (
            introduction
            + '```\n'
            + output
            + '```'
        )

    async def delete_last_output(self, user_id):
        try:
            msg_to_delete = self.run_IO_store[user_id].output
            del self.run_IO_store[user_id]
            await msg_to_delete.delete()
        except KeyError:
            # Message does not exist in store dicts
            return
        except discord_errors.NotFound:
            # Message no longer exists in discord (deleted by server admin)
            return

    @commands.command(aliases=['del'])
    async def delete(self, ctx):
        """Delete the most recent output message you caused
        Type "/run" or "/help" for instructions"""
        await self.delete_last_output(ctx.author.id)

    @commands.command()
    async def run(self, ctx, *, source=None):
        """Run some code
        Type "/run" or "/help" for instructions"""
        if self.client.maintenance_mode:
            await ctx.send('Sorry - I am currently undergoing maintenance.')
            return
        await ctx.trigger_typing()
        if not source:
            await self.send_howto(ctx)
            return
        try:
            run_output = await self.get_run_output(ctx)
            msg = await ctx.send(run_output)
        except commands.BadArgument as error:
            embed = Embed(
                title='Error',
                description=str(error),
                color=0x2ECC71
            )
            msg = await ctx.send(ctx.author.mention, embed=embed)
        self.run_IO_store[ctx.author.id] = RunIO(input=ctx.message, output=msg)

    @commands.command(hidden=True)
    async def edit_last_run(self, ctx, *, source=None):
        """Run some edited code and edit previous message"""
        if self.client.maintenance_mode:
            return
        if not source:
            return
        try:
            msg_to_edit = self.run_IO_store[ctx.author.id].output
            run_output = await self.get_run_output(ctx)
            await msg_to_edit.edit(content=run_output, embed=None)
        except KeyError:
            # Message no longer exists in output store
            # (can only happen if smartass user calls this command directly instead of editing)
            return
        except discord_errors.NotFound:
            # Message no longer exists in discord
            if ctx.author.id in self.run_IO_store:
                del self.run_IO_store[ctx.author.id]
            return
        except commands.BadArgument as error:
            # Edited message probably has bad formatting -> replace previous message with error
            embed = Embed(
                title='Error',
                description=str(error),
                color=0x2ECC71
            )
            try:
                await msg_to_edit.edit(content=ctx.author.mention, embed=embed)
            except discord_errors.NotFound:
                # Message no longer exists in discord
                del self.run_IO_store[ctx.author.id]
            return

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if self.client.maintenance_mode:
            return
        if after.author.bot:
            return
        if before.author.id not in self.run_IO_store:
            return
        if before.id != self.run_IO_store[before.author.id].input.id:
            return
        prefixes = await self.client.get_prefix(after)
        if isinstance(prefixes, str):
            prefixes = [prefixes, ]
        if any(after.content in (f'{prefix}delete', f'{prefix}del') for prefix in prefixes):
            await self.delete_last_output(after.author.id)
            return
        for prefix in prefixes:
            if after.content.lower().startswith(f'{prefix}run'):
                after.content = after.content.replace(f'{prefix}run', f'{prefix}edit_last_run')
                await self.client.process_commands(after)
                break

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if self.client.maintenance_mode:
            return
        if message.author.bot:
            return
        if message.author.id not in self.run_IO_store:
            return
        if message.id != self.run_IO_store[message.author.id].input.id:
            return
        await self.delete_last_output(message.author.id)

    async def send_howto(self, ctx):
        languages = sorted(set(self.languages.values()))

        run_instructions = (
            '**Here are my supported languages:**\n'
            + ', '.join(languages) +
            '\n\n**You can run code like this:**\n'
            '/run <language>\ncommand line parameters (optional) - 1 per line\n'
            '\\`\\`\\`\nyour code\n\\`\\`\\`\nstandard input (optional)\n'
            '\n**Provided by the Engineer Man Discord Server - visit:**\n'
            '• https://emkc.org/run to get it in your own server\n'
            '• https://discord.gg/engineerman for more info\n'
        )

        e = Embed(title='I can execute code right here in Discord! (click here for instructions)',
                  description=run_instructions,
                  url='https://github.com/engineer-man/piston-bot#how-to-use',
                  color=0x2ECC71)

        await ctx.send(embed=e)

    @commands.command(name='help')
    async def send_help(self, ctx):
        await self.send_howto(ctx)


def setup(client):
    client.add_cog(Run(client))
