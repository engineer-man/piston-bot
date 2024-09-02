"""This is a cog for a discord.py bot.
It will add the run command for everyone to use

Commands:
    run            Run code using the Piston API

"""
# pylint: disable=E0402
import sys
from dataclasses import dataclass
from discord import Embed, Message, errors as discord_errors
from discord.ext import commands
# pylint: disable=E1101


@dataclass
class RunIO:
    input: Message
    output: Message

def get_size(obj, seen=None):
    """Recursively finds size of objects"""
    size = sys.getsizeof(obj)
    if seen is None:
        seen = set()
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    # Important mark as seen *before* entering recursion to gracefully handle
    # self-referential objects
    seen.add(obj_id)
    if isinstance(obj, dict):
        size += sum([get_size(v, seen) for v in obj.values()])
        size += sum([get_size(k, seen) for k in obj.keys()])
    elif hasattr(obj, '__dict__'):
        size += get_size(obj.__dict__, seen)
    elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, bytearray)):
        size += sum([get_size(i, seen) for i in obj])
    return size

class Run(commands.Cog, name='CodeExecution'):
    def __init__(self, client):
        self.client = client
        self.run_IO_store: dict[int, RunIO] = dict()
        # Store the most recent /run message for each user.id

    async def get_run_output(self, ctx: commands.Context):
        # Get parameters to call api depending on how the command was called (file <> codeblock)
        if ctx.message.attachments:
            source, language, output_syntax, args, stdin = self.client.runner.get_api_params_with_file(
                input_language="",
                output_syntax="",
                args="",
                stdin="",
                content=ctx.message.content,
                file=ctx.message.attachments[0],
            )
            return await self.client.runner.get_run_output(
                ctx.guild,
                ctx.author,
                source=source,
                language=language,
                output_syntax=output_syntax,
                args=args,
                stdin=stdin,
                mention_author=True,
            )

        source, language, output_syntax, args, stdin = self.client.runner.get_api_params_with_codeblock(
            content=ctx.message.content,
            mention_author=True,
            needs_strict_re=True,
        )
        return await self.client.runner.get_run_output(
            ctx.guild,
            ctx.author,
            source=source,
            language=language,
            output_syntax=output_syntax,
            args=args,
            stdin=stdin,
            mention_author=True,
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
        Type "./run" or "./help" for instructions"""
        await self.delete_last_output(ctx.author.id)

    @commands.command()
    async def run(self, ctx, *, source=None):
        """Run some code
        Type "./run" or "./help" for instructions"""
        if self.client.maintenance_mode:
            await ctx.send('Sorry - I am currently undergoing maintenance.')
            return
        banned_users = [
            #473160828502409217, # em
            501851143203454986
        ]
        if ctx.author.id in banned_users:
            await ctx.send('You have been banned from using I Run Code.')
            return
        try:
            await ctx.typing()
        except discord_errors.Forbidden:
            pass
        if not source and not ctx.message.attachments:
            await self.send_howto(ctx)
            return
        try:
            run_output, _ = await self.get_run_output(ctx)
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
    async def edit_last_run(self, ctx, *, content=None):
        """Run some edited code and edit previous message"""
        if self.client.maintenance_mode:
            return
        if (not content) or ctx.message.attachments:
            return
        try:
            msg_to_edit = self.run_IO_store[ctx.author.id].output
            run_output, _ = await self.get_run_output(ctx)
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

    @commands.command(hidden=True)
    async def size(self, ctx):
        if ctx.author.id != 98488345952256000:
            return False
        await ctx.send(
            f'```\nIO Cache {len(self.run_IO_store)} / {get_size(self.run_IO_store) // 1000} kb'
            f'\nMessage Cache {len(self.client.cached_messages)} / {get_size(self.client.cached_messages) // 1000} kb\n```')

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
                after.content = after.content.replace(f'{prefix}run', f'/edit_last_run', 1)
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
        languages = self.client.runner.get_languages()

        run_instructions = (
            '**Update: Discord changed their client to prevent sending messages**\n'
            '**that are preceeded by a slash (/)**\n'
            '**To run code you can use `"./run"` or `" /run"` until further notice**\n\n'
            '**Here are my supported languages:**\n'
            + ', '.join(languages) +
            '\n\n**You can run code like this:**\n'
            './run <language>\ncommand line parameters (optional) - 1 per line\n'
            '\\`\\`\\`\nyour code\n\\`\\`\\`\nstandard input (optional)\n'
            '\n**Provided by the Engineer Man Discord Server - visit:**\n'
            '• https://emkc.org/run to get it in your own server\n'
            '• https://discord.gg/engineerman for more info\n'
        )

        e = Embed(title='I can execute code right here in Discord! (click here for instructions)',
                  description=run_instructions,
                  url='https://github.com/engineer-man/piston-bot',
                  color=0x2ECC71)

        await ctx.send(embed=e)

    @commands.command(name='help')
    async def send_help(self, ctx):
        await self.send_howto(ctx)


async def setup(client):
    await client.add_cog(Run(client))
