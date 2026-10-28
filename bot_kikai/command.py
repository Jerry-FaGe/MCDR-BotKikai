import math

from mcdreforged.api.command import Literal, Text, Float, Integer
from mcdreforged.api.types import PluginServerInterface, CommandSource, PlayerCommandSource

from .bot_manager import BotManager
from .bot import Bot
from .config import config
from . import utils, view


def show_help(source: CommandSource):
    source.reply(view.render_help())

def list_bots(source: CommandSource, bot_manager: BotManager, status: str = 'all'):
    bots_to_show: list[Bot] = []
    if status == 'online':
        bots_to_show = bot_manager.get_online_bots()
    elif status == 'offline':
        bots_to_show = bot_manager.get_offline_bots()
    else:
        bots_to_show = bot_manager.get_all_bots()

    source.reply(view.render_bot_list(bots_to_show))

def reload_plugin(source: CommandSource, bot_manager: BotManager):
    try:
        bot_manager.reload_config()
    except (OSError, ValueError, RuntimeError) as error:
        source.reply(f'§b[BotKikai] §c重载失败，原文件和当前状态已保留: {error}')
        return
    bot_manager.request_sync()
    if isinstance(source, PlayerCommandSource):
        source.reply(f'§b[BotKikai] §a由{source.player}§a发起的配置文件重载成功')
    else:
        source.reply('§b[BotKikai] §a由控制台发起的配置文件重载成功')

def _save_bot(source: CommandSource, context: dict, bot_manager: BotManager,
              pos, dim, facing, generation: int | None = None):
    name, nickname = context['name'], context['nickname']
    try:
        added = bot_manager.upsert_bot(name, nickname, dim, pos, facing, generation)
    except (OSError, ValueError, RuntimeError) as error:
        source.reply(f'§b[BotKikai] §c保存失败: {error}')
        return
    source.reply(f'§b[BotKikai] §a已{"添加" if added else "修改"}假人 §6{name} §d({nickname})')
    bot_manager.request_sync()


def _add_bot_simple(source: PlayerCommandSource, context: dict, bot_manager: BotManager, generation: int):
    if not bot_manager.is_active(generation):
        return
    pos, dim, facing = utils.get_pos(source.get_server(), source.player)
    if not bot_manager.is_active(generation):
        return
    if pos is None or dim is None or facing is None:
        source.reply('§b[BotKikai] §c无法获取玩家位置；请检查玩家是否在线及 MinecraftDataAPI 的查询日志')
        return
    if not source.has_permission(config.permission['list']):
        source.reply('§b[BotKikai] §c权限不足')
        return
    _save_bot(source, context, bot_manager, pos, dim, facing, generation)

def add_bot_simple(source: CommandSource, context: dict, bot_manager: BotManager):
    if not isinstance(source, PlayerCommandSource):
        source.reply("§b[BotKikai] §c该指令只能由玩家执行")
        return
    try:
        return bot_manager.submit(_add_bot_simple, source, context, bot_manager, bot_manager.generation)
    except RuntimeError as error:
        source.reply(f'§b[BotKikai] §c{error}')

def add_bot_full(source: CommandSource, context: dict, bot_manager: BotManager):
    dim = utils.dimension_convert.get(context['dim'], context['dim'])
    pos = [context["pos_x"], context["pos_y"], context["pos_z"]]
    facing = [context["facing_y"], context["facing_p"]]
    
    _save_bot(source, context, bot_manager, pos, dim, facing)

def del_bot(source: CommandSource, context: dict, bot_manager: BotManager):
    nickname = context["nickname"]
    bot = bot_manager.get_bot_by_nickname(nickname)
    try:
        removed = bot is not None and bot_manager.remove_bot(bot.name)
    except (OSError, ValueError, RuntimeError) as error:
        source.reply(f'§b[BotKikai] §c删除失败: {error}')
        return
    if removed:
        source.reply(f'§b[BotKikai] §a已删除假人 §6{bot.name}')
    else:
        source.reply(f"§b[BotKikai] §4未查询到 §6{nickname} §4对应的假人")

def _bot_action(source: CommandSource, context: dict, action: str, bot_manager: BotManager, generation: int | None = None):
    nickname = context['nickname']
    try:
        bot = bot_manager.get_bot_by_nickname(nickname, generation=generation)
    except RuntimeError:
        return
    if not bot:
        source.reply(f"§b[BotKikai] §4未查询到 §6{nickname} §4对应的假人")
        return

    if action == 'info':
        source.reply(view.render_bot_info(bot))
        return

    if not source.has_permission(config.permission['bot']):
        source.reply('§b[BotKikai] §c权限不足')
        return
    
    executor = source.player if isinstance(source, PlayerCommandSource) else None

    try:
        if action == 'spawn':
            ok = bot.spawn(executor=executor)
            message = '已确认上线'
        elif action == 'kill':
            ok = bot.kill()
            message = '已发送下线请求'
        elif action == 'where':
            ok = bot.glowing(executor=executor)
            message = f'已发送发光两分钟请求，记录坐标：{[math.floor(i) for i in bot.position]}'
        elif action in ('use', 'huse', 'atk', 'hatk'):
            use = action in ('use', 'huse')
            interval = context.get('use_interval' if use else 'atk_interval', 0)
            method = bot.use if use else bot.attack
            ok = method(continuous=action in ('huse', 'hatk'), interval=interval, executor=executor)
            mode = f'每 {interval} gt' if interval else ('持续' if action.startswith('h') else '一次')
            message = f'已发送{mode}{"右键" if use else "左键"}请求'
        elif action == 'stop':
            ok = bot.stop()
            message = '已发送停止动作请求'
        else:
            raise ValueError(f'未知动作: {action}')
    except (OSError, ValueError, RuntimeError) as error:
        source.reply(f'§b[BotKikai] §c操作失败: {error}')
        return
    if not bot_manager.is_active(generation):
        return
    if ok:
        source.reply(f'§b[BotKikai] §a假人 §6{bot.name} §d({nickname}) §a{message}')
    else:
        source.reply(f'§b[BotKikai] §c假人 {bot.name} 操作失败或已取消；请检查服务器状态、召唤超时及 Carpet 日志')

def bot_action(source: CommandSource, context: dict, action: str, bot_manager: BotManager):
    if action == 'info':
        return _bot_action(source, context, action, bot_manager, bot_manager.generation)
    if not source.has_permission(config.permission['bot']):
        source.reply('§b[BotKikai] §c权限不足')
        return None
    try:
        return bot_manager.submit(_bot_action, source, context, action, bot_manager, bot_manager.generation)
    except RuntimeError as error:
        source.reply(f'§b[BotKikai] §c{error}')


def register_command_tree(server: PluginServerInterface, bot_manager: BotManager):
    action_node = Text('nickname').runs(
        lambda src, ctx: bot_action(src, ctx, 'info', bot_manager)
    ).then(
        Literal('spawn').runs(lambda src, ctx: bot_action(src, ctx, 'spawn', bot_manager))
    ).then(
        Literal('kill').runs(lambda src, ctx: bot_action(src, ctx, 'kill', bot_manager))
    ).then(
        Literal('use').runs(lambda src, ctx: bot_action(src, ctx, 'use', bot_manager))
    ).then(
        Literal('huse').runs(lambda src, ctx: bot_action(src, ctx, 'huse', bot_manager)
        ).then(
            Integer('use_interval').at_min(1).runs(lambda src, ctx: bot_action(src, ctx, 'huse', bot_manager))
        )
    ).then(
        Literal('atk').runs(lambda src, ctx: bot_action(src, ctx, 'atk', bot_manager))
    ).then(
        Literal('hatk').runs(lambda src, ctx: bot_action(src, ctx, 'hatk', bot_manager)
        ).then(
            Integer('atk_interval').at_min(1).runs(lambda src, ctx: bot_action(src, ctx, 'hatk', bot_manager))
        )
    ).then(
        Literal('where').runs(lambda src, ctx: bot_action(src, ctx, 'where', bot_manager))
    ).then(
        Literal('stop').runs(lambda src, ctx: bot_action(src, ctx, 'stop', bot_manager))
    )

    add_node = Literal('add').requires(lambda src: src.has_permission(config.permission['list'])).then(
        Text('name').then(
            Text('nickname').runs(lambda src, ctx: add_bot_simple(src, ctx, bot_manager)).then(
                Text('dim').then(
                    Float('pos_x').then(
                        Float('pos_y').then(
                            Float('pos_z').then(
                                Float('facing_y').then(
                                    Float('facing_p').runs(lambda src, ctx: add_bot_full(src, ctx, bot_manager))
                                )
                            )
                        )
                    )
                )
            )
        )
    )

    del_node = Literal('del').requires(lambda src: src.has_permission(config.permission['list'])).then(
        Text('nickname').runs(lambda src, ctx: del_bot(src, ctx, bot_manager))
    )

    list_node = Literal('list').runs(
        lambda src: list_bots(src, bot_manager, 'all')
    ).then(
        Literal('online').runs(lambda src: list_bots(src, bot_manager, 'online'))
    ).then(
        Literal('offline').runs(lambda src: list_bots(src, bot_manager, 'offline'))
    )

    root = Literal(config.prefix_short).runs(show_help).then(
        list_node
    ).then(
        Literal('reload').requires(lambda src: src.has_permission(config.permission['list'])).runs(lambda src: reload_plugin(src, bot_manager))
    ).then(
        add_node
    ).then(
        del_node
    ).then(
        action_node
    )

    server.register_command(root)
