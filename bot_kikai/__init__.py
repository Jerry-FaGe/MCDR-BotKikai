from mcdreforged.api.types import PluginServerInterface, Info

from .storage import init_storage, storage_instance
from .command import register_command_tree


def on_load(server: PluginServerInterface, old):
    global storage_instance
    storage_instance = init_storage(server)
    
    # 在重载时保留在线列表
    if old is not None and hasattr(old, 'storage_instance') and old.storage_instance is not None:
        online_bots = old.storage_instance.get_online_bots()
        storage_instance.set_online_bots(online_bots)

    register_command_tree(server)

    server.register_help_message('!!bk', '假人器械映射插件')


def on_player_joined(server: PluginServerInterface, player: str, info: Info):
    bot_name = storage_instance.auth_player(player)
    if bot_name:
        storage_instance.set_bot_online(bot_name)


def on_player_left(server: PluginServerInterface, player: str):
    bot_name = storage_instance.auth_player(player)
    if bot_name:
        storage_instance.set_bot_offline(bot_name)


def on_server_stop(server: PluginServerInterface, return_code: int):
    if storage_instance:
        storage_instance.clear_online_bots()
