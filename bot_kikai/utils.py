from mcdreforged.api.types import ServerInterface

from . import view


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

# Compatibility exports for the previous help helpers.
help_head = view.HELP_HEAD


def get_help_body() -> dict[str, str]:
    return view.get_help_body()


def get_pos(server: ServerInterface, player_name: str):
    try:
        import minecraft_data_api as api
        data = api.get_player_info(player_name)
    except Exception as error:
        server.logger.warning(f'[BotKikai] 获取玩家位置失败: {error}')
        return None, None, None
    if not isinstance(data, dict):
        return None, None, None
    return data.get('Pos'), data.get('Dimension'), data.get('Rotation')
