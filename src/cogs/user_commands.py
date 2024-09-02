import discord
from discord import app_commands, Interaction, Attachment
from discord.ext import commands
from .utils.errors import PistonError, NoLanguageFoundError
from asyncio import TimeoutError as AsyncTimeoutError
from io import BytesIO

class SourceCodeModal(discord.ui.Modal, title="Run Code"):
    def __init__(self, get_run_output, log_error, language):
        super().__init__()
        self.get_run_output = get_run_output
        self.log_error = log_error
        self.language = language

        self.lang = discord.ui.TextInput(
            label="Language",
            placeholder="The language",
            max_length=50,
            default=self.language or "",
        )

        self.code = discord.ui.TextInput(
            label="Code",
            style=discord.TextStyle.long,
            placeholder="The source code",
            max_length=1900,
        )

        self.add_item(self.lang)
        self.add_item(self.code)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        output = await self.get_run_output(
            guild=interaction.guild,
            author=interaction.user,
            content=self.code.value,
            input_lang=self.lang.value,
            output_syntax=None,
            args=None,
            stdin=None,
            mention_author=False,
        )

        if len(self.code.value) > 1000:
            file = discord.File(filename=f"source_code.{self.lang.value}", fp=BytesIO(self.code.value.encode('utf-8')))
            await interaction.followup.send("Here is your input:", file=file)
            await interaction.followup.send(output)
            return
        formatted_src = f"```{self.lang.value}\n{self.code.value}\n```"
        await interaction.followup.send("Here is your input:" + formatted_src)
        await interaction.followup.send(output)

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        await interaction.followup.send(
            "Oops! Something went wrong.", ephemeral=True
        )

        await self.log_error(error, error_source="SourceCodeModal")

class NoLang(discord.ui.Modal, title="Give language"):
    def __init__(self, get_api_params_with_codeblock, get_run_output, log_error, message):
        super().__init__()
        self.get_api_params_with_codeblock = get_api_params_with_codeblock
        self.get_run_output = get_run_output
        self.log_error = log_error
        self.message = message

    lang = discord.ui.TextInput(
        label="Language",
        placeholder="The language",
        max_length=50,
    )

    async def on_submit(self, interaction: discord.Interaction):
        source, language, output_syntax, args, stdin = await self.get_api_params_with_codeblock(
            guild=interaction.guild,
            author=interaction.user,
            content=self.message.content,
            mention_author=False,
            needs_strict_re=False,
            input_lang=self.lang.value,
            jump_url=self.message.jump_url,
        )

        await interaction.response.defer()
        output = await self.get_run_output(
            guild=interaction.guild,
            author=interaction.user,
            content=source,
            lang=language,
            output_syntax=output_syntax,
            args=args,
            stdin=stdin,
            mention_author=False,
        )
        await interaction.followup.send(output)

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        await interaction.followup.send(
            "Oops! Something went wrong.", ephemeral=True
        )

        await self.log_error(error, error_source="NoLangModal")


class UserCommands(commands.Cog, name="UserCommands"):
    def __init__(self, client):
        self.client = client
        self.ctx_menu = app_commands.ContextMenu(
            name="Run Code",
            callback=self.run_code_ctx_menu,
        )
        self.client.tree.add_command(self.ctx_menu)

    async def cog_app_command_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        if isinstance(error.original, PistonError):
            error_message = str(error.original)
            if error_message:
                error_message = f'`{error_message}` '
            await interaction.followup.send(f'API Error {error_message}- Please try again later', ephemeral=True)
            await self.client.log_error(error, Interaction)
            return

        if isinstance(error.original, AsyncTimeoutError):
            await interaction.followup.send(f'API Timeout - Please try again later', ephemeral=True)
            await self.client.log_error(error, Interaction)
            return
        await self.client.log_error(error, Interaction)
        await interaction.followup.send(f'{error.original}', ephemeral=True)

    @app_commands.command(name="run_code", description="Open a modal to input code")
    @app_commands.user_install()
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def run_code(self, interaction: Interaction, language: str = None):
        if language not in self.client.runner.get_languages(inlude_aliases=True):
            await interaction.response.send_modal(
                SourceCodeModal(
                    self.client.runner.get_run_output,
                    self.client.log_error,
                    "",
                )
            )
            return
        await interaction.response.send_modal(
            SourceCodeModal(
                self.client.runner.get_run_output,
                self.client.log_error,
                language,
            )
        )

    @run_code.autocomplete('language')
    async def autocomplete_callback(self, _: discord.Interaction, current: str):
        langs = self.client.runner.get_languages(inlude_aliases=True)
        if current:
            langs = [lang for lang in langs if lang.startswith(current)]
        return [app_commands.Choice(name=lang, value=lang) for lang in langs[:25]]

    @app_commands.command(name="run_file", description="Run a file")
    @app_commands.user_install()
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def run_file(
        self,
        interaction: Interaction,
        file: Attachment,
        language: str = "",
        output_syntax: str = "None",
        args: str = "",
        stdin: str = "",
    ):
        source, language, output_syntax, args, stdin = await self.client.runner.get_api_params_with_file(
            guild=interaction.guild,
            author=interaction.user,
            content="",
            file=file,
            input_language=language,
            output_syntax=output_syntax,
            args=args,
            stdin=stdin,
            mention_author=False,
        )
        await interaction.response.defer()
        output = await self.client.runner.get_run_output(
            guild=interaction.guild,
            author=interaction.user,
            content=source,
            lang=language,
            output_syntax=output_syntax,
            args=args,
            stdin=stdin,
            mention_author=False,
            jump_url=None,
        )


        if len(source) > 1000:
            output_file = discord.File(filename=file.filename, fp=BytesIO(source))
            await interaction.followup.send("Here is your input:", file=output_file)
            await interaction.followup.send(output)
            return

        formatted_src = f"```{language}\n{source}\n```"
        await interaction.followup.send("Here is your input:" + formatted_src)
        await interaction.followup.send(output)

    @app_commands.user_install()
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def run_code_ctx_menu(self, interaction: Interaction, message: discord.Message):
        try:
            if len(message.attachments) > 0:
                source, language, output_syntax, args, stdin = await self.client.runner.get_api_params_with_file(
                    content=message.content,
                    file=message.attachments[0],
                    input_language="",
                    output_syntax="",
                    args="",
                    stdin=""
                )
            else:
                source, language, output_syntax, args, stdin = await self.client.runner.get_api_params_with_codeblock(
                    content=message.content,
                    needs_strict_re=False,
                    input_lang=None,
                )
            await interaction.response.defer()
            output = await self.client.runner.get_run_output(
                guild=interaction.guild,
                author=interaction.user,
                content=source,
                lang=language,
                output_syntax=output_syntax,
                args=args,
                stdin=stdin,
                mention_author=False,
                jump_url=message.jump_url,
            )
            await interaction.followup.send(output)
        except NoLanguageFoundError:
            await interaction.response.send_modal(
                NoLang(
                    self.client.runner.get_api_params_with_codeblock,
                    self.client.runner.get_run_output,
                    self.client.log_error,
                    message,
                )
            )
        except commands.BadArgument as e:
            await interaction.followup.send(str(e), ephemeral=True)

async def setup(client):
    await client.add_cog(UserCommands(client))
