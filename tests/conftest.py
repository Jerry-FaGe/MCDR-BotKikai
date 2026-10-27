import logging
from types import SimpleNamespace

import pytest
from mcdreforged.api.types import CommandSource, PlayerCommandSource

import bot_kikai
from bot_kikai.bot import Bot
from bot_kikai.bot_manager import BotManager
from bot_kikai.config import Config, config


class FakeServer:
    def __init__(self, path):
        self.path = path
        self.logger = logging.getLogger('botkikai-tests')
        self.commands = []
        self.roots = []
        self.help_messages = []
        self.running = True
        self.startup = False
        self.on_execute = None

    def get_data_folder(self):
        return str(self.path)

    def is_server_running(self):
        return self.running

    def is_server_startup(self):
        return self.startup

    def execute(self, command):
        self.commands.append(command)
        if self.on_execute:
            self.on_execute(command)

    def register_command(self, root):
        self.roots.append(root)

    def register_help_message(self, *args):
        self.help_messages.append(args)


class Source(CommandSource):
    def __init__(self, server, permission=4):
        self.server = server
        self.permission = permission
        self.messages = []

    def get_server(self):
        return self.server

    def get_permission_level(self):
        return self.permission

    def reply(self, message, **kwargs):
        self.messages.append(message.to_plain_text() if hasattr(message, 'to_plain_text') else str(message))


class PlayerSource(Source, PlayerCommandSource):
    @property
    def player(self):
        return 'Tester'


@pytest.fixture
def env(tmp_path):
    old_config = config.__dict__.copy()
    old_manager = bot_kikai.bot_manager_instance
    config.__dict__.clear()
    config.__dict__.update(Config().__dict__)
    server = FakeServer(tmp_path)
    config.init(server)
    manager = BotManager(server)
    try:
        yield SimpleNamespace(
            server=server, source=Source(server), player=PlayerSource(server),
            manager=manager, path=tmp_path,
        )
    finally:
        manager.shutdown()
        if bot_kikai.bot_manager_instance is not None and bot_kikai.bot_manager_instance is not old_manager:
            bot_kikai.bot_manager_instance.shutdown()
        bot_kikai.bot_manager_instance = old_manager
        config.__dict__.clear()
        config.__dict__.update(old_config)


@pytest.fixture
def bot(env):
    value = Bot(env.server, 'SandBot', ['SandBot', 'farm', '\u5237\u6c99\u673a'],
                'minecraft:overworld', [1.5, 64, -2.5], [180, 0])
    env.manager.add_bot(value)
    return value
