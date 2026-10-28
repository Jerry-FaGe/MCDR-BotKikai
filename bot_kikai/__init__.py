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
    
    # 保留已知状态；旧版推算的名字不能当作服务端确认。
    if old is not None and hasattr(old, 'bot_manager_instance') and old.bot_manager_instance is not None:
        for bot in old.bot_manager_instance.get_all_bots():
            confirmed_name = getattr(bot, 'confirmed_name', None)
            bot_manager_instance.update_player_status(
                confirmed_name or bot.real_name, bot.is_online, confirm=confirmed_name is not None,
            )

    register_command_tree(server, bot_manager_instance)

    server.register_help_message(config.prefix_short, '假人器械映射插件')
    bot_manager_instance.request_sync()


def on_unload(server: PluginServerInterface):
    if bot_manager_instance:
        bot_manager_instance.shutdown()


def on_server_startup(server: PluginServerInterface):
    if bot_manager_instance:
        bot_manager_instance.request_sync()


def on_player_joined(server: PluginServerInterface, player: str, info: Info):
    if bot_manager_instance:
        bot_manager_instance.update_player_status(player, True)


def on_player_left(server: PluginServerInterface, player: str):
    if bot_manager_instance:
        bot_manager_instance.update_player_status(player, False)


def on_server_stop(server: PluginServerInterface, return_code: int):
    if bot_manager_instance:
        bot_manager_instance.clear_all_online_status()
