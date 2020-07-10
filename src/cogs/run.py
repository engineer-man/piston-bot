"""This is a cog for a discord.py bot.
It will add the run command for everyone to use

Commands:
    run            Run code using the Piston API

"""

import typing
from discord.ext import commands
from discord import Embed


class Run(commands.Cog, name='CodeExecution'):
    def __init__(self, client):
        self.client = client
        self.languages = {
            'asm': 'nasm',
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
            'node': 'javascript',
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
        self.last_run_command_msg = dict()
        self.last_run_outputs = dict()

    async def get_api_response(self, ctx, language):
        language = language.replace('```', '')
        if language not in self.languages:
            return f'`Unsupported language: {language}`'
        language = self.languages[language]
        message = ctx.message.content.split('```')
        if len(message) < 3:
            return '`No code or invalid code present`'
        source = message[1]
        source = source[source.find('\n'):].strip()

        url = 'https://emkc.org/api/internal/piston/execute'
        headers = {'Authorization': self.client.config["emkc_key"]}
        data = {'language': language, 'source': source}

        async with self.client.session.post(
            url,
            headers=headers,
            data=data
        ) as response:
            r = await response.json()
        if not response.status == 200:
            return f'`Sorry, execution problem - Invalid status {response.status}`'
        if r['output'] is None:
            return f'`Sorry, execution problem - Invalid Output received`'
        return (
            f'Here is your output {ctx.author.mention}\n'
            + '```\n'
            + '\n'.join(r['output'].split('\n')[:30])
            + '```'
        )

    async def send_howto(self, ctx):
        languages = []
        last = ''
        for language in sorted(set(self.languages.values())):
            current = language[0].lower()
            if current not in last:
                languages.append([language])
            else:
                languages[-1].append(language)
            last = current
        languages = map(', '.join, languages)

        run_instructions = (
            '**Here are my supported languages:**\n'
            + ', '.join(languages) +
            '\n\n**You can run code like this:**\n'
            '/run <language>\n'
            '\\`\\`\\`\nyour code\n\\`\\`\\`\n'
            '\n**Support:**\n'
            'Provided by the EngineerMan Discord Server\n'
            'visit -> **emkc.org/run** to get it in your own server\n'
            'visit -> **discord.gg/engineerman** for more info'
        )

        e = Embed(title='I can execute code right here in Discord!',
                  description=run_instructions,
                  color=0x2ECC71)
        e.set_thumbnail(
            url='https://cdn.discordapp.com/avatars/473160828502409217/1789e1e10d429ff4ef37d863433e684e.png'
        )
        await ctx.send(embed=e)
        return

    @commands.command()
    async def run(self, ctx, language: typing.Optional[str] = None):
        """Run some code
        Type "/run" for instructions"""
        await ctx.trigger_typing()
        if not language:
            await self.send_howto(ctx)
            return
        api_response = await self.get_api_response(ctx, language)
        msg = await ctx.send(api_response)
        self.last_run_command_msg[ctx.author.id] = ctx.message
        self.last_run_outputs[ctx.author.id] = msg

    @commands.command(hidden=True)
    async def edit_last_run(self, ctx, language: typing.Optional[str] = None):
        """Run some edited code"""
        if not ctx.invoked_with == 'run':
            return
        if not language:
            await self.client.get_command('howto').invoke(ctx)
            return
        api_response = await self.get_api_response(ctx, language)
        try:
            msg_to_edit = self.last_run_outputs[ctx.author.id]
            await msg_to_edit.edit(content=api_response)
        except KeyError:
            return

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if after.author.bot:
            return
        if before.author.id not in self.last_run_command_msg:
            return
        if before.id != self.last_run_command_msg[before.author.id].id:
            return
        content = after.content.lower()
        prefixes = await self.client.get_prefix(after)
        if isinstance(prefixes, str):
            prefixes = [prefixes, ]
        if not any(content.startswith(f'{prefix}run') for prefix in prefixes):
            return
        ctx = await self.client.get_context(after)
        if ctx.valid:
            await self.client.get_command('edit_last_run').invoke(ctx)


def setup(client):
    client.add_cog(Run(client))
