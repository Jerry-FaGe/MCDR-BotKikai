from mcdreforged.api.types import ServerInterface

from bot_kikai.config import config


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
    f"§7{config.prefix_short}": "§r显示本帮助信息",
    f"§7{config.prefix_short} list §6[online§7|§6offline]": "§r显示假人列表，可筛选在线或离线",
    f"§7{config.prefix_short} reload": "§r重载插件配置",
    f"§7{config.prefix_short} add §6<name> <kikai>": "§r使用当前玩家参数添加一个名为 §6<name> §r用于 §6<kikai> §r的假人",
    f"§7{config.prefix_short} add §6<name> <kikai> <dim> <pos> <facing>": "§r使用自定义参数添加一个名为 §6<name> §r用于 §6<kikai> §r的假人",
    f"§7{config.prefix_short} del §6<kikai>": "§r删除用于 §6<kikai> §r的假人",
    f"§7{config.prefix_short} §6<kikai>": "§r输出用于 §6<kikai> §r的假人信息",
    f'§7{config.prefix_short} §6<kikai> §7spawn': "§r上线用于 §6<kikai> §r的假人",
    f"§7{config.prefix_short} §6<kikai> §7kill": "§r下线用于 §6<kikai> §r的假人",
    f"§7{config.prefix_short} §6<kikai> §7where": "§r假人发光两分钟并输出坐标",
    f"§7{config.prefix_short} §6<kikai> §7use": "§r假人右键一次",
    f"§7{config.prefix_short} §6<kikai> §7huse §6[<interval>]": "§r假人持续右键，后接正整数可控制间隔 gt",
    f"§7{config.prefix_short} §6<kikai> §7atk": "§r假人左键一次",
    f"§7{config.prefix_short} §6<kikai> §7hatk §6[<interval>]": "§r假人持续左键, 后接正整数可控制间隔 gt",
    f"§7{config.prefix_short} §6<kikai> §7stop": "§r假人停止一切动作",
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
