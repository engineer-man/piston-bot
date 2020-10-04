"""This is a cog for a discord.py bot.
It will add the run command for everyone to use

Commands:
    run            Run code using the Piston API

"""
# pylint: disable=E0402
import json
import re
from discord import Embed, errors as discord_errors
from discord.ext import commands
from discord.utils import escape_mentions
from .utils.codeswap import add_boilerplate

# DEBUG = True


class Run(commands.Cog, name='CodeExecution'):
    def __init__(self, client):
        self.client = client
        self.languages = {
            'asm': 'nasm',
            'asm64': 'nasm64',
            'awk': 'awk',
            'bash': 'bash',
            'bf': 'brainfuck',
            'brainfuck': 'brainfuck',
            'c': 'c',
            'c#': 'csharp',
            'c++': 'cpp',
            'cpp': 'cpp',
            'cs': 'csharp',
            'csharp': 'csharp',
            'duby': 'ruby',
            'el': 'emacs',
            'elisp': 'emacs',
            'emacs': 'emacs',
            'elixir': 'elixir',
            'go': 'go',
            'java': 'java',
            'javascript': 'javascript',
            'jl': 'julia',
            'julia': 'julia',
            'js': 'javascript',
            'kotlin': 'kotlin',
            'nasm': 'nasm',
            'nasm64': 'nasm64',
            'node': 'javascript',
            'perl': 'perl',
            'php': 'php',
            'php3': 'php',
            'php4': 'php',
            'php5': 'php',
            'py': 'python3',
            'py3': 'python3',
            'python': 'python3',
            'python2': 'python2',
            'python3': 'python3',
            'r': 'r',
            'rb': 'ruby',
            'ruby': 'ruby',
            'rs': 'rust',
            'rust': 'rust',
            'sage': 'python3',
            'swift': 'swift',
            'ts': 'typescript',
            'typescript': 'typescript',
        }
        self.run_command_store = dict()
        self.run_output_store = dict()
        self.run_regex = re.compile(
            r'(?s)/(?:edit_last_)?run(?: +(?P<language>\S*)\s*|\s*)(?:\n(?P<args>(?:[^\n\r\f\v]*\n)*?)\s*|\s*)```(?:(?P<syntax>\S+)\n\s*|\s*)(?P<source>.*)```'
        )

    async def get_run_output(self, ctx):
        if ctx.message.content.count('```') != 2:
            raise commands.BadArgument('Invalid command format (missing codeblock?)')
        match = self.run_regex.search(ctx.message.content)
        if not match:
            raise commands.BadArgument('Invalid command format')
        language, args, syntax, source = match.groups()

        if args:
            args = [arg for arg in args.strip().split('\n') if arg]

        if not language:
            language = syntax

        if language not in self.languages:
            raise commands.BadArgument(f'Unsupported language: {language}')

        if not source:
            raise commands.BadArgument(f'No source code found')

        source = add_boilerplate(language, source)

        language = self.languages[language]
        data = {'language': language, 'source': source, 'args': args}
        headers = {'Authorization': self.client.config["emkc_key"]}

        # Call piston API
        # if DEBUG:
        #     await ctx.send('```DEBUG:\nSending Source to Piston\n' + str(data) + '```')
        async with self.client.session.post(
            'https://emkc.org/api/v1/piston/execute',
            headers=headers,
            data=json.dumps(data)
        ) as response:
            r = await response.json()
        if not response.status == 200:
            raise commands.CommandError(f'ERROR calling Piston API. {response.status}')
        if r['output'] is None:
            raise commands.CommandError(f'ERROR calling Piston API. No output received')

        len_syntax = 0 if syntax is None else len(syntax)

        output = escape_mentions('\n'.join(r['output'].split('\n')[:30]))
        if len(output) > 1945-len_syntax:
            output = output[:1945-len_syntax] + '[...]'

        # Logging
        logging_data = {
            'server': ctx.guild.name if ctx.guild else 'DMChannel',
            'server_id': str(ctx.guild.id) if ctx.guild else '0',
            'user': f'{ctx.author.name}#{ctx.author.discriminator}',
            'user_id': str(ctx.author.id),
            'language': language,
            'source': source
        }
        # if DEBUG:
        # await ctx.send('```DEBUG:\nSending Log\n' + str(logging_data) + '```')

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

        return (
            f'Here is your output {ctx.author.mention}\n'
            + f'```{syntax or ""}\n'
            + output
            + '```'
        )

    @commands.command()
    async def run(self, ctx, *, source=None):
        """Run some code
        Type "/run" or "/help" for instructions"""
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
            msg = await ctx.send(embed=embed)
        self.run_command_store[ctx.author.id] = ctx.message
        self.run_output_store[ctx.author.id] = msg

    @commands.command(hidden=True)
    async def edit_last_run(self, ctx, *, source=None):
        """Run some edited code and edit previous message"""
        if not source:
            return
        try:
            msg_to_edit = self.run_output_store[ctx.author.id]
            run_output = await self.get_run_output(ctx)
            await msg_to_edit.edit(content=run_output, embed=None)
        except KeyError:
            # Message no longer exists in output store
            # (can only happen if smartass user calls this command directly instead of editing)
            return
        except discord_errors.NotFound:
            # Message no longer exists in discord
            del self.run_output_store[ctx.author.id]
            return
        except commands.BadArgument as error:
            # Edited message probably has bad formatting
            embed = Embed(
                title='Error',
                description=str(error),
                color=0x2ECC71
            )
            try:
                await msg_to_edit.edit(content=None, embed=embed)
            except discord_errors.NotFound:
                del self.run_output_store[ctx.author.id]
            return

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if after.author.bot:
            return
        if before.author.id not in self.run_command_store:
            return
        if before.id != self.run_command_store[before.author.id].id:
            return
        prefixes = await self.client.get_prefix(after)
        if isinstance(prefixes, str):
            prefixes = [prefixes, ]
        for prefix in prefixes:
            if after.content.lower().startswith(f'{prefix}run'):
                after.content = after.content.replace(f'{prefix}run', f'{prefix}edit_last_run')
                await self.client.process_commands(after)
                break

    async def send_howto(self, ctx):
        languages = sorted(set(self.languages.values()))

        run_instructions = (
            '**Here are my supported languages:**\n'
            + ', '.join(languages) +
            '\n\n**You can run code like this:**\n'
            '/run <language>\ncommand line parameters (optional) - 1 per line\n'
            '\\`\\`\\`\nyour code\n\\`\\`\\`\n'
            '\n**Provided by the EngineerMan Discord Server - visit:**\n'
            '• https://emkc.org/run to get it in your own server\n'
            '• https://discord.gg/engineerman for more info\n'
            '• https://top.gg/bot/730885117656039466 and vote if you like this bot'
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
