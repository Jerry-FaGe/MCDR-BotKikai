from mcdreforged.api.command import Literal, Text, Float, Integer
from mcdreforged.api.types import PluginServerInterface, CommandSource, PlayerCommandSource

from .bot_manager import BotManager
from .config import config
from . import utils, view


def show_help(source: CommandSource):
    source.reply(view.render_help())

def list_bots(source: CommandSource, bot_manager: BotManager, status: str = 'all', *,
              query: str | None = None, page: int = 1):
    try:
        message = view.render_bot_list(
            bot_manager.get_all_bots(), status=status, query=query, page=page,
            can_operate=source.has_permission(config.permission['bot']),
        )
    except ValueError as error:
        source.reply(view.render_feedback(f'列表参数无效: {error}', kind='error'))
        return
    source.reply(message)

def reload_plugin(source: CommandSource, bot_manager: BotManager):
    try:
        bot_manager.reload_config()
    except (OSError, ValueError, RuntimeError) as error:
        source.reply(view.render_feedback(f'重载失败，原文件和当前状态已保留: {error}', kind='error'))
        return
    bot_manager.request_sync()
    source.reply(view.render_feedback('配置已重载', kind='success'))

def _save_bot(source: CommandSource, context: dict, bot_manager: BotManager,
              pos, dim, facing, generation: int | None = None):
    name, nickname = context['name'], context['nickname']
    try:
        added = bot_manager.upsert_bot(name, nickname, dim, pos, facing, generation)
    except (OSError, ValueError, RuntimeError) as error:
        source.reply(view.render_feedback(f'保存失败: {error}', bot=bot_manager.get_bot(name), kind='error'))
        return
    source.reply(view.render_feedback('已添加记录' if added else '已更新记录',
                                      bot=bot_manager.get_bot(name), kind='success'))
    bot_manager.request_sync()


def _add_bot_simple(source: PlayerCommandSource, context: dict, bot_manager: BotManager, generation: int):
    if not bot_manager.is_active(generation):
        return
    pos, dim, facing = utils.get_pos(source.get_server(), source.player)
    if not bot_manager.is_active(generation):
        return
    if pos is None or dim is None or facing is None:
        source.reply(view.render_feedback(
            '无法获取玩家位置，请确认玩家在线', kind='error', details='请检查 MinecraftDataAPI 的查询日志'))
        return
    if not source.has_permission(config.permission['list']):
        source.reply(view.render_feedback('权限不足', kind='error'))
        return
    _save_bot(source, context, bot_manager, pos, dim, facing, generation)

def add_bot_simple(source: CommandSource, context: dict, bot_manager: BotManager):
    if not isinstance(source, PlayerCommandSource):
        source.reply(view.render_feedback('该指令只能由玩家执行', kind='error'))
        return
    try:
        return bot_manager.submit(_add_bot_simple, source, context, bot_manager, bot_manager.generation)
    except RuntimeError as error:
        source.reply(view.render_feedback(str(error), kind='error'))

def add_bot_full(source: CommandSource, context: dict, bot_manager: BotManager):
    dim = utils.dimension_convert.get(context['dim'], context['dim'])
    pos = [context["pos_x"], context["pos_y"], context["pos_z"]]
    facing = [context["facing_y"], context["facing_p"]]
    
    _save_bot(source, context, bot_manager, pos, dim, facing)

def del_bot(source: CommandSource, context: dict, bot_manager: BotManager):
    nickname = context["nickname"]
    bot = None
    try:
        bot = bot_manager.get_bot_by_nickname(nickname)
        removed = bot is not None and bot_manager.remove_bot(bot.name)
    except (OSError, ValueError, RuntimeError) as error:
        source.reply(view.render_feedback(f'删除失败: {error}', bot=bot, kind='error'))
        return
    if removed:
        source.reply(view.render_feedback('已删除记录', bot=bot, kind='success', name_link=False,
                                          details='只删除插件记录，不会让假人下线'))
    else:
        source.reply(view.render_feedback(f'未找到假人「{nickname}」', kind='error'))

def edit_alias(source: CommandSource, context: dict, bot_manager: BotManager, *, remove: bool = False):
    if not source.has_permission(config.permission['list']):
        source.reply(view.render_feedback('权限不足', kind='error'))
        return
    target, alias = context['nickname'], context['alias']
    method = bot_manager.remove_alias if remove else bot_manager.add_alias
    bot = None
    try:
        bot = bot_manager.get_bot_by_nickname(target)
        # Pin the resolved record even if its invoking alias is changed concurrently.
        changed = method(bot.name if bot is not None else target, alias)
    except (OSError, ValueError, RuntimeError) as error:
        source.reply(view.render_feedback(f'别名修改失败: {error}', bot=bot, kind='error'))
        return
    # The alias used to invoke this command may just have been removed.
    bot = bot_manager.get_bot(bot.name) if bot is not None else None
    if changed:
        source.reply(view.render_feedback(f'已{"移除" if remove else "添加"}别名「{alias}」', bot=bot, kind='success'))
    elif remove:
        source.reply(view.render_feedback(f'没有别名「{alias}」，未作修改', bot=bot))
    else:
        source.reply(view.render_feedback(f'已可通过「{alias}」查找，无需重复添加', bot=bot))

def _bot_action(source: CommandSource, context: dict, action: str, bot_manager: BotManager, generation: int | None = None):
    if action == 'alias' and not source.has_permission(config.permission['list']):
        source.reply(view.render_feedback('权限不足', kind='error'))
        return
    nickname = context['nickname']
    try:
        bot = bot_manager.get_bot_by_nickname(nickname, generation=generation)
    except RuntimeError:
        return
    if not bot:
        source.reply(view.render_feedback(f'未找到假人「{nickname}」', kind='error'))
        return

    if action == 'info':
        source.reply(view.render_bot_info(
            bot,
            can_operate=source.has_permission(config.permission['bot']),
            can_manage=source.has_permission(config.permission['list']),
        ))
        return
    if action == 'alias':
        source.reply(view.render_alias_panel(bot))
        return

    if not source.has_permission(config.permission['bot']):
        source.reply(view.render_feedback('权限不足', kind='error'))
        return
    
    executor = source.player if isinstance(source, PlayerCommandSource) else None
    interval = 0

    try:
        if action == 'spawn':
            ok = bot.spawn(executor=executor)
        elif action == 'kill':
            ok = bot.kill()
        elif action == 'where':
            ok = bot.glowing(executor=executor)
        elif action in ('use', 'huse', 'atk', 'hatk'):
            use = action in ('use', 'huse')
            interval = context.get('use_interval' if use else 'atk_interval', 0)
            method = bot.use if use else bot.attack
            ok = method(continuous=action in ('huse', 'hatk'), interval=interval, executor=executor)
        elif action == 'stop':
            ok = bot.stop()
        else:
            raise ValueError(f'未知动作: {action}')
    except (OSError, ValueError, RuntimeError) as error:
        source.reply(view.render_feedback(f'操作失败: {error}', bot=bot, kind='error'))
        return
    if not bot_manager.is_active(generation):
        return
    if ok:
        source.reply(view.render_action_feedback(bot, action, interval=interval))
    else:
        source.reply(view.render_feedback(
            '操作未完成；请检查状态或日志', bot=bot, kind='error',
            details='动作接口未返回具体原因，无法区分服务器未运行、上线未确认或取消；请检查 MCDR / Carpet 日志',
        ))

def bot_action(source: CommandSource, context: dict, action: str, bot_manager: BotManager):
    if action in ('info', 'alias'):
        return _bot_action(source, context, action, bot_manager, bot_manager.generation)
    if not source.has_permission(config.permission['bot']):
        source.reply(view.render_feedback('权限不足', kind='error'))
        return None
    try:
        return bot_manager.submit(_bot_action, source, context, action, bot_manager, bot_manager.generation)
    except RuntimeError as error:
        source.reply(view.render_feedback(str(error), kind='error'))


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
    ).then(
        Literal('alias').requires(lambda src: src.has_permission(config.permission['list'])).runs(
            lambda src, ctx: bot_action(src, ctx, 'alias', bot_manager)
        ).then(
            Literal('add').then(
                Text('alias').runs(lambda src, ctx: edit_alias(src, ctx, bot_manager))
            )
        ).then(
            Literal('del').then(
                Text('alias').runs(lambda src, ctx: edit_alias(src, ctx, bot_manager, remove=True))
            )
        )
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

    def list_branch(literal: str, status: str) -> Literal:
        def show(src, ctx):
            return list_bots(src, bot_manager, status, query=ctx.get('query'), page=ctx.get('page', 1))

        return Literal(literal).runs(show).then(
            Integer('page').at_min(1).runs(show)
        ).then(
            Literal('search').then(
                Text('query').runs(show).then(Integer('page').at_min(1).runs(show))
            )
        )

    list_node = list_branch('list', 'all').then(
        list_branch('online', 'online')
    ).then(list_branch('offline', 'offline'))

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
