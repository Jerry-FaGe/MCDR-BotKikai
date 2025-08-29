from mcdreforged.api.types import PluginServerInterface, Info

from .config import config
from .bot_manager import BotManager
from .command import register_command_tree


bot_manager_instance: BotManager | None = None


def on_load(server: PluginServerInterface, old):
    # 初始化配置
    config.init(server)

    # 初始化假人管理器
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
    if bot_manager_instance:
        bot_name_from_config = bot_manager_instance.auth_player(player)
        if bot_name_from_config:
            bot_manager_instance.set_bot_online(bot_name_from_config)
            
            # 自动将假人的真实名字加入昵称列表
            bot = bot_manager_instance.get_bot(bot_name_from_config)
            if bot and player not in bot.nicknames:
                bot.nicknames.append(player)
                bot_manager_instance.save()


def on_player_left(server: PluginServerInterface, player: str):
    if bot_manager_instance:
        bot_name_from_config = bot_manager_instance.auth_player(player)
        if bot_name_from_config:
            bot_manager_instance.set_bot_offline(bot_name_from_config)


def on_server_stop(server: PluginServerInterface, return_code: int):
    if bot_manager_instance:
        bot_manager_instance.clear_all_online_status()
