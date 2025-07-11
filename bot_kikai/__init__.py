from mcdreforged.api.types import PluginServerInterface, Info

from .bot_manager import BotManager
from .command import register_command_tree


bot_manager_instance: BotManager | None = None


def on_load(server: PluginServerInterface, old):
    global bot_manager_instance
    bot_manager_instance = BotManager(server)
    
    # 在重载时保留在线列表
    if old is not None and hasattr(old, 'bot_manager_instance') and old.bot_manager_instance is not None:
        online_bots_name = [bot.name for bot in old.bot_manager_instance.get_online_bots()]
        for bot_name in online_bots_name:
            bot_manager_instance.set_bot_online(bot_name)

    register_command_tree(server, bot_manager_instance)

    server.register_help_message('!!bk', '假人器械映射插件')


def on_player_joined(server: PluginServerInterface, player: str, info: Info):
    if bot_manager_instance and bot_manager_instance.auth_player(player):
        bot_manager_instance.set_bot_online(player)


def on_player_left(server: PluginServerInterface, player: str):
    if bot_manager_instance and bot_manager_instance.auth_player(player):
        bot_manager_instance.set_bot_offline(player)


def on_server_stop(server: PluginServerInterface, return_code: int):
    if bot_manager_instance:
        bot_manager_instance.clear_all_online_status()
