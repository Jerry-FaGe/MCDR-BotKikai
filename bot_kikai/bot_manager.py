import os
import re
import json

from mcdreforged.api.types import PluginServerInterface

from .bot import Bot
from .config import config


class BotManager:
    def __init__(self, server: PluginServerInterface):
        self.server = server
        self.bots = {}  # type: dict[str, Bot]
        self.load()

    def load(self):
        if not config.bots_path or not os.path.isfile(config.bots_path):
            self.save()
            return

        with open(config.bots_path, 'r', encoding='utf8') as f:
            try:
                bots_data = json.load(f)
            except json.JSONDecodeError:
                bots_data = {}

        
        for name, data in bots_data.items():
            self.bots[name] = Bot.from_dict(self.server, name, data)

    def save(self):
        if not config.bots_path:
            return

        bots_data = {name: bot.to_dict() for name, bot in self.bots.items()}
        json_text = json.dumps(bots_data, ensure_ascii=False, indent=4)

        pattern = re.compile(r'\[\s*([^\[\]]*?)\s*\]', flags=re.DOTALL)

        def compact_array(m):
            inner = re.sub(r'\s+', ' ', m.group(1)).strip()
            return f'[{inner}]'

        json_compact = pattern.sub(compact_array, json_text)

        with open(config.bots_path, 'w', encoding='utf8') as f:
            f.write(json_compact)

    def add_bot(self, bot: Bot):
        self.bots[bot.name] = bot
        self.save()

    def remove_bot(self, name: str) -> bool:
        if name in self.bots:
            del self.bots[name]
            self.save()
            return True
        return False

    def get_bot(self, name: str) -> Bot | None:
        return self.bots.get(name)

    def get_bot_by_nickname(self, nickname: str) -> Bot | None:
        for bot in self.bots.values():
            if nickname in bot.nicknames:
                return bot
        return None

    def get_all_bots(self) -> list[Bot]:
        return list(self.bots.values())

    def get_online_bots(self) -> list[Bot]:
        return [bot for bot in self.bots.values() if bot.is_online]

    def get_offline_bots(self) -> list[Bot]:
        return [bot for bot in self.bots.values() if not bot.is_online]

    def set_bot_online(self, name: str):
        bot = self.get_bot(name)
        if bot:
            bot.is_online = True

    def set_bot_offline(self, name: str):
        bot = self.get_bot(name)
        if bot:
            bot.is_online = False

    def clear_all_online_status(self):
        for bot in self.bots.values():
            bot.is_online = False

    def auth_player(self, player_name: str) -> str | None:
        """检查一个玩家名是否属于已配置的假人，返回其主名"""
        lower_name = player_name.lower()
        for bot in self.bots.values():
            if bot.name.lower() == lower_name:
                return bot.name
        return None
