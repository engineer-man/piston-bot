"""PistonBot

"""
import json
import sys
import traceback
from datetime import datetime, timezone
from os import path, listdir
from discord.ext.commands import Bot, Context
from discord import Activity
from aiohttp import ClientSession


class PistonBot(Bot):
    def __init__(self, *args, **options):
        super().__init__(*args, **options)
        self.session = None
        with open('../state/config.json') as conffile:
            self.config = json.load(conffile)
        self.last_errors = []
        self.default_activity = Activity(name='emkc.org/run | /run', type=0)
        self.error_activity = Activity(name='!emkc.org/run | /run', type=0)
        self.error_string = 'Sorry, something went wrong. We will look into it.'

    async def start(self, *args, **kwargs):
        self.session = ClientSession()
        await super().start(self.config["bot_key"], *args, **kwargs)

    async def close(self):
        await self.session.close()
        await super().close()

    def user_is_admin(self, user):
        return user.id in self.config['admins']

    async def log_error(self, error, error_source=None):
        self.last_errors.append((
            error,
            datetime.now(tz=timezone.utc),
            error_source,
            error_source.message.content if isinstance(error_source, Context) else None
        ))
        await client.change_presence(activity=self.error_activity)


client = PistonBot(
    command_prefix=('/'),
    description='Hello, I can run code!',
    max_messages=15000
)
client.remove_command('help')

STARTUP_EXTENSIONS = []
for file in listdir(path.join(path.dirname(__file__), 'cogs/')):
    filename, ext = path.splitext(file)
    if '.py' in ext:
        STARTUP_EXTENSIONS.append(f'cogs.{filename}')

for extension in reversed(STARTUP_EXTENSIONS):
    try:
        client.load_extension(f'{extension}')
    except Exception as e:
        client.last_errors.append((e, datetime.now(tz=timezone.utc), 'Cog INIT', None))
        exc = f'{type(e).__name__}: {e}'
        print(f'Failed to load extension {extension}\n{exc}')


@client.event
async def on_ready():
    print('PistonBot started successfully')
    return True


@client.event
async def on_error(event_method, *args, **kwargs):
    """|coro|

    The default error handler provided by the client.

    By default this prints to :data:`sys.stderr` however it could be
    overridden to have a different implementation.
    Check :func:`~discord.on_error` for more details.
    """
    print('Default Handler: Ignoring exception in {}'.format(event_method), file=sys.stderr)
    traceback.print_exc()
    # --------------- custom code below -------------------------------
    # Saving the error to be inspected later
    await client.log_error(sys.exc_info()[1], 'DEFAULT HANDLER:' + event_method)


client.run()
print('PistonBot has exited')
