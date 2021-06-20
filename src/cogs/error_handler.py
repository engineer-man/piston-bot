"""This is a cog for a discord.py bot.
It will add error handling and inspecting commands

Commands:
    error               List unhandled errors
      - traceback       print traceback of stored error

"""
# pylint: disable=E0402
import traceback
import typing
from datetime import datetime, timezone
from asyncio import TimeoutError as AsyncTimeoutError
from discord import Embed, DMChannel, errors as discord_errors
from discord.ext import commands
from .utils.errors import PistonError


class ErrorHandler(commands.Cog, name='ErrorHandler'):
    def __init__(self, client):
        self.client = client

    # ----------------------------------------------
    # Error handler
    # ----------------------------------------------
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if not isinstance(ctx.channel, DMChannel):
            perms = ctx.channel.permissions_for(ctx.guild.get_member(self.client.user.id))
            try:
                if not perms.send_messages:
                    await ctx.author.send("I don't have permission to write in this channel.")
                    return
            except discord_errors.Forbidden:
                return

            if not perms.embed_links:
                await ctx.send("I don't have permission to post embeds in this channel.")
                return

        usr = ctx.author.mention

        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(error)
            return

        if isinstance(error, commands.MissingRequiredArgument):
            par = str(error.param)
            missing = par.split(": ")[0]
            if ':' in par:
                missing_type = ' (' + str(par).split(": ")[1] + ')'
            else:
                missing_type = ''
            await ctx.send(
                f'{usr} Missing parameter: `{missing}{missing_type}`'
            )
            return

        if isinstance(error, commands.CheckFailure):
            await ctx.send(f'Sorry {usr}, you are not allowed to run this command.')
            return

        if isinstance(error, commands.BadArgument):
            # It's in an embed to prevent mentions from working
            embed = Embed(
                title='Error',
                description=str(error),
                color=0x2ECC71
            )
            await ctx.send(usr, embed=embed)
            return

        if isinstance(error, commands.UnexpectedQuoteError):
            await ctx.send(f'{usr} Unexpected quote encountered')
            return

        if isinstance(error, commands.InvalidEndOfQuotedStringError):
            await ctx.send(f'{usr} Invalid character after quote')
            return

        if isinstance(error, commands.CommandInvokeError):
            if isinstance(error.original, PistonError):
                error_message = str(error.original)
                if error_message:
                    error_message = f'`{error_message}` '
                await ctx.send(f'{usr} API Error {error_message}- Please try again later')
                await self.client.log_error(error, ctx)
                return

            if isinstance(error.original, AsyncTimeoutError):
                await ctx.send(f'{usr} API Timeout - Please try again later')
                await self.client.log_error(error, ctx)
                return

        # In case of an unhandled error -> Save the error so it can be accessed later
        await ctx.send(f'{usr} {self.client.error_string}')
        await self.client.log_error(error, ctx)

        print(f'Ignoring exception in command {ctx.command}:', flush=True)
        traceback.print_exception(
            type(error), error, error.__traceback__
        )
        print('-------------------------------------------------------------', flush=True)

    # ----------------------------------------------
    # Error command Group
    # ----------------------------------------------
    @commands.group(
        invoke_without_command=True,
        name='error',
        hidden=True,
        aliases=['errors']
    )
    async def error(self, ctx, n: typing.Optional[int] = None):
        """Show a concise list of stored errors"""

        if n is not None:
            await self.print_traceback(ctx, n)
            return

        NUM_ERRORS_PER_PAGE = 10

        error_log = self.client.last_errors

        if not error_log:
            await ctx.send('Error log is empty')
            return

        response = [f'```css\nNumber of stored errors: {len(error_log)}']
        for i, exc_tuple in enumerate(error_log):
            exc, date, error_source, *_ = exc_tuple
            call_info = f'{"CMD:" + error_source.invoked_with if isinstance(error_source, commands.Context) else error_source}'
            response.append(
                f'{i}: ['
                + date.isoformat().split('.')[0]
                + '] - ['
                + call_info
                + f']\nException: {str(exc)[:200]}'
            )
            if i % NUM_ERRORS_PER_PAGE == NUM_ERRORS_PER_PAGE-1:
                response.append('```')
                await ctx.send('\n'.join(response))
                response = [f'```css']
        if len(response) > 1:
            response.append('```')
            await ctx.send('\n'.join(response))

    @error.command(
        name='clear',
        aliases=['delete'],
    )
    async def error_clear(self, ctx, n: int = None):
        """Clear error with index [n]"""
        if n is None:
            self.client.last_errors = []
            await ctx.send('Error log cleared')
        else:
            self.client.last_errors.pop(n)
            await ctx.send(f'Deleted error #{n}')
        await self.client.change_presence(
            activity=self.client.default_activity
        )

    @error.command(
        name='traceback',
        aliases=['tb'],
    )
    async def error_traceback(self, ctx, n: int = None):
        """Print the traceback of error [n] from the error log"""
        await self.print_traceback(ctx, n)

    async def print_traceback(self, ctx, n):
        error_log = self.client.last_errors

        if not error_log:
            await ctx.send('Error log is empty')
            return

        if n is None:
            await ctx.send('Please specify an error index')
            await self.client.get_command('error').invoke(ctx)
            return

        if n >= len(error_log) or n < 0:
            await ctx.send('Error index does not exist')
            return

        exc, date, error_source, orig_content, orig_attachment = error_log[n]
        delta = (datetime.now(tz=timezone.utc) - date).total_seconds()
        hours = int(delta // 3600)
        seconds = int(delta - (hours * 3600))
        delta_str = f'{hours} hours and {seconds} seconds ago'
        tb = ''.join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )
        response_header = [f'`Error occured {delta_str}`']
        response_error = []

        if isinstance(error_source, commands.Context):
            guild = error_source.guild
            channel = error_source.channel
            response_header.append(
                f'`Server:{guild.name} | Channel: {channel.name}`' if guild else '`In DMChannel`'
            )
            response_header.append(
                f'`User: {error_source.author.name}#{error_source.author.discriminator}`'
            )
            response_header.append(f'`Command: {error_source.invoked_with}`')
            response_header.append(error_source.message.jump_url)
            e = Embed(title='Full command that caused the error:',
                      description=orig_content)
            e.set_footer(text=error_source.author.display_name,
                         icon_url=error_source.author.avatar_url)
        else:
            response_header.append(f'`Error caught in {error_source}`')
            e = None

        for line in tb.split('\n'):
            while len(line) > 1800:
                response_error.append(line[:1800])
                line = line[1800:]
            response_error.append(line)

        to_send = '\n'.join(response_header) + '\n```python'

        for line in response_error:
            if len(to_send) + len(line) + 1 > 1800:
                await ctx.send(to_send + '\n```')
                to_send = '```python'
            to_send += '\n' + line
        await ctx.send(to_send + '\n```', embed=e)


        if orig_attachment:
            await ctx.send(
                'Attached file:',
                file=await orig_attachment.to_file()
            )

    # @commands.command()
    # async def error_mock(self, ctx, n=1):
    #     print('MOCKING')
    #     raise IndexError('Mocked Test Error'*n)

    # @commands.Cog.listener()
    # async def on_message_edit(self, before, after):
    #     if 'mock' in after.content:
    #         await self.client.process_commands(after)
    #         # ctx = await self.client.get_context(after)
    #         # await self.client.get_command('error_mock').invoke(ctx)


def setup(client):
    client.add_cog(ErrorHandler(client))
