from mcdreforged.api.decorator import new_thread
from mcdreforged.api.command import Literal, Text, Float, Integer
from mcdreforged.api.types import PluginServerInterface, CommandSource, PlayerCommandSource, ConsoleCommandSource
from mcdreforged.api.rtext import RTextList, RText, RAction

from .bot_manager import BotManager
from .bot import Bot
from . import utils


def show_help(source: CommandSource):
    head = [utils.help_head]
    body = [RText(f'{k}: {v}\n').c(
        RAction.suggest_command, k.replace('§7', '')).h(v)
        for k, v in utils.help_body.items()]
    source.reply(RTextList(*(head + body)))

def list_bots(source: CommandSource, bot_manager: BotManager, status: str = 'all'):
    bots_to_show: list[Bot] = []
    if status == 'online':
        bots_to_show = bot_manager.get_online_bots()
    elif status == 'offline':
        bots_to_show = bot_manager.get_offline_bots()
    else:
        bots_to_show = bot_manager.get_all_bots()

    if not bots_to_show:
        source.reply("§b[BotKikai] §7没有找到符合条件的假人")
        return

    msg_list: list[RTextList] = []
    for bot in bots_to_show:
        msg_list.append(bot.get_simple_rtext())
        msg_list.append(RTextList("\n"))
    source.reply(RTextList(*msg_list))

def reload_plugin(source: CommandSource, bot_manager: BotManager):
    bot_manager.load()
    if isinstance(source, PlayerCommandSource):
        source.reply(f'§b[BotKikai] §a由{source.player}§a发起的配置文件重载成功')
    else:
        source.reply('§b[BotKikai] §a由控制台发起的配置文件重载成功')

def _add_bot_simple(source: PlayerCommandSource, context: dict, bot_manager: BotManager):
    name, nickname = context["name"], context["nickname"]
    
    pos, dim, facing = utils.get_pos(source.get_server(), source.player)
    if pos is None or dim is None or facing is None:
        source.reply("§b[BotKikai] §c错误：无法获取玩家位置信息。请检查依赖插件 minecraft_data_api 是否加载")
        return

    bot = bot_manager.get_bot(name)
    if bot:
        if nickname not in bot.nicknames:
            bot.nicknames.append(nickname)
        bot.position = pos
        bot.dimension = dim
        bot.facing = facing
    else:
        nick_ls = [name]
        if nickname != name:
            nick_ls.append(nickname)
        bot = Bot(source.get_server(), name, nick_ls, dim, pos, facing)
        bot_manager.add_bot(bot)
        source.reply(f'§b[BotKikai] §a已添加假人 §6{name}')

def add_bot_simple(source: CommandSource, context: dict, bot_manager: BotManager):
    if not isinstance(source, PlayerCommandSource):
        source.reply("§b[BotKikai] §c该指令只能由玩家执行")
        return
    new_thread("botkikai_add")(_add_bot_simple)(source, context, bot_manager)

def add_bot_full(source: CommandSource, context: dict, bot_manager: BotManager):
    name, nickname, dim_str = context["name"], context["nickname"], context["dim"]
    if dim_str not in utils.dimension_convert:
        source.reply('§b[BotKikai] §4无法识别的维度')
        return
    dim = utils.dimension_convert[dim_str]
    pos = [context["pos_x"], context["pos_y"], context["pos_z"]]
    facing = [context["facing_y"], context["facing_p"]]
    
    bot = bot_manager.get_bot(name)
    if bot:
        if nickname not in bot.nicknames:
            bot.nicknames.append(nickname)
        bot.dimension = dim
        bot.position = pos
        bot.facing = facing
    else:
        nick_ls = [name]
        if nickname != name:
            nick_ls.append(nickname)
        bot = Bot(source.get_server(), name, nick_ls, dim, pos, facing)
        bot_manager.add_bot(bot)
        source.reply(f'§b[BotKikai] §a已添加假人 {name}')

def del_bot(source: CommandSource, context: dict, bot_manager: BotManager):
    nickname = context["nickname"]
    bot = bot_manager.get_bot_by_nickname(nickname)
    if bot and bot_manager.remove_bot(bot.name):
        bot.is_online = False
        source.reply(f'§b[BotKikai] §a已删除假人 §6{bot.name}')
    else:
        source.reply(f"§b[BotKikai] §4未查询到 §6{nickname} §4对应的假人")

def bot_action(source: CommandSource, context: dict, action: str, bot_manager: BotManager):
    nickname = context['nickname']
    bot = bot_manager.get_bot_by_nickname(nickname)
    if not bot:
        source.reply(f"§b[BotKikai] §4未查询到 §6{nickname} §4对应的假人")
        return

    if action == 'info':
        source.reply(bot.get_info_rtext())
        return

    if not source.has_permission(utils.permission_bot):
        source.reply('§b[BotKikai] §c权限不足')
        return
    
    executor = source.player if isinstance(source, PlayerCommandSource) else None

    if action == 'spawn':
        if not bot.is_online:
            if bot.spawn(executor=executor): 
                source.reply(f"§b[BotKikai] §a已创建假人 §6{bot.name} §d({nickname})")
        else:
            source.reply(f"§b[BotKikai] §4假人 §6{bot.name} §d({nickname}) §4已经在线")

    elif action == 'kill':
        if bot.is_online:
            if bot.kill(): 
                source.reply(f"§b[BotKikai] §a已下线假人 §6{bot.name} §d({nickname})")
        else:
            source.reply(f"§b[BotKikai] §4假人 §6{bot.name} §d({nickname}) §4已经离线，无法被下线")

    elif action == 'where':
        bot.glowing(executor=executor)
        source.reply(f"§b[BotKikai] §7已高亮 §6{bot.name} §d({nickname}) §7两分钟，坐标：§6{[int(i) for i in bot.position]}")

    elif action == "use":
        bot.use(executor=executor)
        source.reply(f"§b[BotKikai] §a假人 §6{bot.name} §d({nickname}) §a右键一次")

    elif action == "atk":
        bot.attack(executor=executor)
        source.reply(f"§b[BotKikai] §a假人 §6{bot.name} §d({nickname}) §a左键一次")

    elif action == 'huse':
        use_interval = context.get('use_interval', 0)
        bot.use(continuous=True, interval=use_interval, executor=executor)
        msg = f", 间隔 {use_interval} gt" if use_interval > 0 else ", 使用默认间隔"
        source.reply(f"§b[BotKikai] §a假人 §6{bot.name} §d({nickname}) §a持续右键{msg}")

    elif action == "hatk":
        atk_interval = context.get('atk_interval', 0)
        bot.attack(continuous=True, interval=atk_interval, executor=executor)
        msg = f", 间隔 {atk_interval} gt" if atk_interval > 0 else ", 使用默认间隔"
        source.reply(f"§b[BotKikai] §a假人 §6{bot.name} §d({nickname}) §a持续左键{msg}")

    elif action == 'stop':
        bot.stop()
        source.reply(f"§b[BotKikai] §a假人 §6{bot.name} §d({nickname}) §a停止所有动作")


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
            Integer('use_interval').runs(lambda src, ctx: bot_action(src, ctx, 'huse', bot_manager))
        )
    ).then(
        Literal('atk').runs(lambda src, ctx: bot_action(src, ctx, 'atk', bot_manager))
    ).then(
        Literal('hatk').runs(lambda src, ctx: bot_action(src, ctx, 'hatk', bot_manager)
        ).then(
            Integer('atk_interval').runs(lambda src, ctx: bot_action(src, ctx, 'hatk', bot_manager))
        )
    ).then(
        Literal('where').runs(lambda src, ctx: bot_action(src, ctx, 'where', bot_manager))
    ).then(
        Literal('stop').runs(lambda src, ctx: bot_action(src, ctx, 'stop', bot_manager))
    )

    add_node = Literal('add').requires(lambda src: src.has_permission(utils.permission_list)).then(
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

    del_node = Literal('del').requires(lambda src: src.has_permission(utils.permission_list)).then(
        Text('nickname').runs(lambda src, ctx: del_bot(src, ctx, bot_manager))
    )

    list_node = Literal('list').runs(
        lambda src: list_bots(src, bot_manager, 'all')
    ).then(
        Literal('online').runs(lambda src: list_bots(src, bot_manager, 'online'))
    ).then(
        Literal('offline').runs(lambda src: list_bots(src, bot_manager, 'offline'))
    )

    root = Literal(utils.prefix_short).runs(show_help).then(
        list_node
    ).then(
        Literal('reload').requires(lambda src: src.has_permission(utils.permission_list)).runs(lambda src: reload_plugin(src, bot_manager))
    ).then(
        add_node
    ).then(
        del_node
    ).then(
        action_node
    )

    server.register_command(root)
