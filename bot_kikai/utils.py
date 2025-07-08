from mcdreforged.api.types import PluginServerInterface, ServerInterface, Info

from . import storage


prefix_short = '!!bk'
prefix = '!!botkikai'

# 操作假人(spawn,use,kill)的最低权限  guest: 0, user: 1, helper: 2, admin: 3, owner: 4
permission_bot = 0

# 操作假人列表(add,remove)的最低权限  guest: 0, user: 1, helper: 2, admin: 3, owner: 4
permission_list = 0

dimension_convert = {
    '0': 'minecraft:overworld',
    '-1': 'minecraft:the_nether',
    '1': 'minecraft:the_end',
    'overworld': 'minecraft:overworld',
    'the_nether': 'minecraft:the_nether',
    'the_end': 'minecraft:the_end',
    'nether': 'minecraft:the_nether',
    'end': 'minecraft:the_end',
    'minecraft:overworld': 'minecraft:overworld',
    'minecraft:the_nether': 'minecraft:the_nether',
    'minecraft:the_end': 'minecraft:the_end',
    'zhushijie': 'minecraft:overworld',
    'diyu': 'minecraft:the_nether',
    'xiajie': 'minecraft:the_nether',
    'modi': 'minecraft:the_end'
}
help_head = """
================== §bBotKikai §r==================
§6欢迎使用由@Jerry-FaGe开发RayanceKing二改的假人器械映射插件！
§6你可以在Github搜索MCDR-BotKikai找到本项目！
「君は道具ではなく、その名が似合う人になろんだ」
本插件中§d{prefix_short}§r与§d{prefix}§r效果相同，两者可以互相替换
""".format(prefix=prefix, prefix_short=prefix_short)
help_body = {
    f"§b{prefix_short}": "§r显示本帮助信息",
    f"§b{prefix_short} list": "§r显示假人列表",
    f"§b{prefix_short} reload": "§r重载插件配置",
    f"§b{prefix_short} add <name> <kikai>": "§r使用当前玩家参数添加一个名为<name>用于<kikai>的假人",
    f"§b{prefix_short} add <name> <kikai> <dim> <pos> <facing>": "§r使用自定义参数添加一个名为<name>用于<kikai>的假人",
    f"§b{prefix_short} del <kikai>": "§r从假人列表移除用于<kikai>的假人",
    f"§b{prefix_short} <kikai>": "§r输出一个可点击的界面，自动根据假人是否在线改变选项",
    f'§b{prefix_short} <kikai> spawn': "§r召唤一个用于<kikai>的假人",
    f"§b{prefix_short} <kikai> kill": "§r干掉用于<kikai>的假人",
    f"§b{prefix_short} <kikai> use": "§r假人右键一次§r（执行此条前无需执行spawn，如假人不在线会自动上线）",
    f"§b{prefix_short} <kikai> huse": "§r假人持续右键§r（执行此条前无需执行spawn，如假人不在线会自动上线）",
    f"§b{prefix_short} <kikai> hatk": "§r假人持续左键§r（执行此条前无需执行spawn，如假人不在线会自动上线）",
    f"§b{prefix_short} <kikai> glowing": "§r假人发光两分钟",
    f"§b{prefix_short} <kikai> stop": "§r假人停止一切动作",
}


def get_pos(server: ServerInterface, player_name: str)
    try:
        import minecraft_data_api as api
    except ImportError:
        server.logger.error("依赖 MinecraftDataAPI 未安装，请安装后重试")
        return None, None, None
    pos = api.get_player_info(player_name, 'Pos')
    dim = api.get_player_info(player_name, 'Dimension')
    facing = api.get_player_info(player_name, 'Rotation')
    return pos, dim, facing

def spawn_cmd(name: str):
    bot_info = storage.storage_instance.get_bot_info(name)
    if not bot_info:
        return None
    dim = bot_info['dim']
    pos = ' '.join([str(i) for i in bot_info['pos']])
    facing = bot_info['facing']
    return f'player {name} spawn at {pos} facing {facing} in {dim}'

def kill(name: str):
    return f'/player {name} kill'

def use(name: str):
    return f'/player {name} use once'

def hold_attack(name: str):
    return f'/player {name} attack continuous'

def attack_12gt(name: str):
    return f'/player {name} attack interval 12'

def hold_use(name: str):
    return f'/player {name} use continuous'

def glowing(name: str):
    return f'/effect give {name} glowing 120'

def stop(name: str):
    return f'/player {name} stop'
