from mcdreforged.api.types import ServerInterface

prefix_short = '!!bk'

# 操作假人(spawn,use,kill)的最低权限  guest: 0, user: 1, helper: 2, admin: 3, owner: 4
permission_bot = 1

# 操作假人列表(add,remove)的最低权限  guest: 0, user: 1, helper: 2, admin: 3, owner: 4
permission_list = 3

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
§6欢迎使用由 @Jerry-FaGe 开发的假人器械映射插件！
§6你可以在 Github 搜索 MCDR-BotKikai 找到本项目！
§7「君は道具ではなく、その名が似合う人になろんだ」
===========================================
"""

help_body = {
    f"§7{prefix_short}": "§r显示本帮助信息",
    f"§7{prefix_short} list": "§r显示假人列表",
    f"§7{prefix_short} reload": "§r重载插件配置",
    f"§7{prefix_short} add <name> <kikai>": "§r使用当前玩家参数添加一个名为<name>用于<kikai>的假人",
    f"§7{prefix_short} add <name> <kikai> <dim> <pos> <facing>": "§r使用自定义参数添加一个名为<name>用于<kikai>的假人",
    f"§7{prefix_short} del <kikai>": "§r从假人列表移除用于<kikai>的假人",
    f"§7{prefix_short} <kikai>": "§r输出一个可点击的界面，自动根据假人是否在线改变选项",
    f'§7{prefix_short} <kikai> spawn': "§r召唤一个用于<kikai>的假人",
    f"§7{prefix_short} <kikai> kill": "§r干掉用于<kikai>的假人",
    f"§7{prefix_short} <kikai> where": "§r假人发光两分钟并输出坐标",
    f"§7{prefix_short} <kikai> use": "§r假人右键一次",
    f"§7{prefix_short} <kikai> huse <interval>": "§r假人持续右键，后接正整数可控制间隔 gt",
    f"§7{prefix_short} <kikai> atk": "§r假人左键一次",
    f"§7{prefix_short} <kikai> hatk <interval>": "§r假人持续左键, 后接正整数可控制间隔 gt",
    f"§7{prefix_short} <kikai> stop": "§r假人停止一切动作",
}


def get_pos(server: ServerInterface, player_name: str):
    try:
        import minecraft_data_api as api
    except ImportError:
        server.logger.error("依赖 MinecraftDataAPI 未安装，请安装后重试")
        return None, None, None
    pos = api.get_player_info(player_name, 'Pos')
    dim = api.get_player_info(player_name, 'Dimension')
    facing = api.get_player_info(player_name, 'Rotation')
    return pos, dim, facing
