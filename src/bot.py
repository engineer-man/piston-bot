"""PistonBot

"""
import json
import sys
import traceback
from datetime import datetime
from os import path, listdir
from discord.ext.commands import Bot
from discord import Activity, Message
from aiohttp import ClientSession


class PistonBot(Bot):
    def __init__(self, *args, **options):
        super().__init__(*args, **options)
        self.session = None
        with open('../state/config.json') as conffile:
            self.config = json.load(conffile)
        self.last_errors = []

    async def start(self, *args, **kwargs):
        self.session = ClientSession()
        await super().start(self.config["bot_key"], *args, **kwargs)

    async def close(self):
        await self.session.close()
        await super().close()

    def user_is_admin(self, user):
        return user.id in self.config['admins']

client = PistonBot(
    command_prefix=('/'),
    description='Hello, I can run code!',
    max_messages=15000
)

client.default_activity = Activity(name='emkc.org/run | /run', type=0)
client.error_activity = Activity(name='!emkc.org/run | /run', type=0)

STARTUP_EXTENSIONS = []
for file in listdir(path.join(path.dirname(__file__), 'cogs/')):
    filename, ext = path.splitext(file)
    if '.py' in ext:
        STARTUP_EXTENSIONS.append(f'cogs.{filename}')

for extension in reversed(STARTUP_EXTENSIONS):
    try:
        client.load_extension(f'{extension}')
    except Exception as e:
        client.last_errors.append((e, datetime.utcnow(), None, None))
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
    # Saving the error if it resulted from a message edit
    if len(args) > 1:
        a1, a2,*_ = args
        if isinstance(a1, Message) and isinstance(a2, Message):
            client.last_errors.append((sys.exc_info()[1], datetime.utcnow(), a2, a2.content))
        await client.change_presence(activity=client.error_activity)

client.remove_command('help')

client.run()
print('PistonBot has exited')
