import time

from mcdreforged.api.decorator import new_thread
from mcdreforged.api.command import Literal, Text, Float
from mcdreforged.api.types import PluginServerInterface, CommandSource
from mcdreforged.api.rtext import RTextList, RText, RAction

from . import storage
from . import utils


def show_help(source: CommandSource):
    head = [utils.help_head]
    body = [RText(f'{k} {v}\n').c(
        RAction.suggest_command, k.replace('§b', '')).h(v)
        for k, v in utils.help_body.items()]
    source.reply(RTextList(*(head + body)))

def list_bots(source: CommandSource):
    msg_list = []
    all_bots = storage.storage_instance.get_all_bots()
    online_bots = storage.storage_instance.get_online_bots()
    for name, bot_info in all_bots.items():
        if name in online_bots:
            bot_msg = RTextList(
                '\n'
                f'§7----------- §6{name} §a在线 §7 -----------\n',
                f'§7此假人用于:§6 {bot_info["nick"][1]}\n',
                RText('§b[点击下线]  ').c(RAction.suggest_command, f'{utils.prefix_short} {bot_info["nick"][1]} kill').h(f'下线§6{name}'),
                RText('§b[右键一次]  ').c(RAction.suggest_command, f'{utils.prefix_short} {bot_info["nick"][1]} use').h(f'§6{name}§7右键一次'),
                RText('§b[持续使用]  ').c(RAction.suggest_command, f'{utils.prefix_short} {bot_info["nick"][1]} huse').h(f'§6{name}§7持续使用'),
                RText('§b[间隔12gt攻击]  ').c(RAction.suggest_command, f'{utils.prefix_short} {bot_info["nick"][1]} hatk').h(f'§6{name}§7间隔12gt攻击'),
                RText('§b[停止动作]  ').c(RAction.suggest_command, f'{utils.prefix_short} {bot_info["nick"][1]} stop').h(f'§6{name}§7停止动作'),
                RText('§b[发光两分钟]  ').c(RAction.suggest_command, f'{utils.prefix_short} {bot_info["nick"][1]} glowing').h(f'§6{name}§7发光两分钟'),
                RText(f'§a{name}').h(
                    f'§7描述:§6 {bot_info["nick"][1]}\n',
                    f'§7维度:§6 {bot_info["dim"]}\n',
                    f'§7坐标:§6 {bot_info["pos"]}\n',
                    f'§7朝向:§6 {bot_info["facing"]}'
                )
            )
        else:
            bot_msg = RTextList(
                '\n'
                f'§7----------- §6{name} §4离线 §7 -----------\n',
                f'§7此假人用于:§6 {bot_info["nick"][1]}\n',
                RText('§d[点击上线]  ').c(RAction.suggest_command, f'{utils.prefix_short} {bot_info["nick"][1]} spawn').h(f'召唤§6{name}'),
                RText('§d[点击use]  ').c(RAction.suggest_command, f'{utils.prefix_short} {bot_info["nick"][1]} use').h(f'召唤§6{name}§r并右键一次'),
                RText('§d[查看详情]  ').c(RAction.suggest_command, f'{utils.prefix_short} {bot_info["nick"][1]}').h(f'显示§6{name}§r的详细信息')
            )
        msg_list.append(bot_msg)
    source.reply(RTextList(*msg_list))

def reload_plugin(source: CommandSource):
    try:
        storage.storage_instance.load()
        actor = f"玩家§d{source.player}" if source.is_player else "控制台"
        source.get_server().say(f'§b[BotKikai]§a由{actor}§a发起的BotKikai重载成功')
    except Exception as e:
        actor = f"玩家§d{source.player}" if source.is_player else "控制台"
        source.get_server().say(f'§b[BotKikai]§4由{actor}§4发起的BotKikai重载失败：{e}')

def _add_bot_simple_logic(source: CommandSource, context: dict):
    if not source.is_player:
        source.reply("§c该指令只能由玩家执行")
        return
    name, nickname = context["name"], context["nickname"]
    bot_info = storage.storage_instance.get_bot_info(name)
    nick_ls = bot_info.get('nick', []) if bot_info else []
    if name not in nick_ls: nick_ls.append(name)
    if nickname != name and nickname not in nick_ls: nick_ls.append(nickname)
    pos, dim, facing = utils.get_pos(source.get_server(), source.player)
    if pos is None:
        source.reply("§c错误：无法获取玩家位置信息。依赖插件 minecraft_data_api 是否加载？")
        return
    storage.storage_instance.add_bot(name, {'nick': nick_ls, 'dim': dim, 'pos': pos, 'facing': f'{facing[0]} {facing[1]}'})
    source.reply(f'§b[BotKikai]§a已添加假人 {name}')

def add_bot_simple(source: CommandSource, context: dict):
    new_thread("botkikai_add")(_add_bot_simple_logic)(source, context)

def add_bot_full(source: CommandSource, context: dict):
    name, nickname, dim_str = context["name"], context["nickname"], context["dim"]
    if dim_str not in utils.dimension_convert:
        source.reply('§b[BotKikai]§4无法识别的维度')
        return
    dim = utils.dimension_convert[dim_str]
    pos = [context["pos_x"], context["pos_y"], context["pos_z"]]
    facing = f'{context["facing_y"]} {context["facing_p"]}'
    bot_info = storage.storage_instance.get_bot_info(name)
    nick_ls = bot_info.get('nick', []) if bot_info else []
    if name not in nick_ls: nick_ls.append(name)
    if nickname != name and nickname not in nick_ls: nick_ls.append(nickname)
    storage.storage_instance.add_bot(name, {'nick': nick_ls, 'dim': dim, 'pos': pos, 'facing': facing})
    source.reply(f'§b[BotKikai]§a已添加假人 {name}')

def del_bot(source: CommandSource, context: dict):
    nickname = context["nickname"]
    name = storage.storage_instance.search_by_nickname(nickname)
    if name and storage.storage_instance.del_bot(name):
        storage.storage_instance.set_bot_offline(name)
        source.reply(f'§b[BotKikai]§a已删除机器人 {name}')
    else:
        source.reply(f"§b[BotKikai]§4未查询到 §d{nickname} §4对应的假人")

def bot_action(source: CommandSource, context: dict, action: str):
    nickname = context['nickname']
    name = storage.storage_instance.search_by_nickname(nickname)
    if not name:
        source.reply(f"§b[BotKikai]§4未查询到 §d{nickname} §4对应的假人")
        return
    
    server = source.get_server()
    is_online = storage.storage_instance.is_bot_online(name)

    if action == 'info':
        bot_info = storage.storage_instance.get_bot_info(name)
        if not bot_info: return
        if not is_online:
            msg = RTextList(
                f'§7----------- §6{name} §4离线 §7-----------', 
                f'\n§7此假人用于:§6 {bot_info["nick"][1]}', 
                f'\n§7维度:§6 {bot_info["dim"]}', 
                RText(f'\n§7坐标:§6 {bot_info["pos"]}').c(RAction.run_command, f'[x:{int(bot_info["pos"][0])}, y:{int(bot_info["pos"][1])}, z:{int(bot_info["pos"][2])}, name:{name}, dim:{bot_info["dim"]}]').h('点击显示可识别坐标点'), 
                f'\n§7朝向:§6 {bot_info["facing"]}', 
                RText('\n§d[点击上线]  ').c(RAction.suggest_command, f'{utils.prefix_short} {nickname} spawn').h(f'召唤§6{name}'), 
                RText('§d[点击use]  ').c(RAction.suggest_command, f'{utils.prefix_short} {nickname} use ').h(f'召唤§6{name}§7并右键一次')
            )
        else:
            msg = RTextList(
                f'§7----------- §6{name} §a在线 §7-----------', 
                f'\n§7此假人用于:§6 {bot_info["nick"][1]}', 
                f'\n§7维度:§6 {bot_info["dim"]}', 
                RText(f'\n§7坐标:§6 {bot_info["pos"]}').c(RAction.run_command, f'[x:{int(bot_info["pos"][0])}, y:{int(bot_info["pos"][1])}, z:{int(bot_info["pos"][2])}, name:{name}, dim:{bot_info["dim"]}]').h('点击显示可识别坐标点'), 
                f'\n§7朝向:§6 {bot_info["facing"]}', RText('\n§d[点击use]  ').c(RAction.suggest_command, f'{utils.prefix_short} {nickname} use').h(f'§6{name}§7右键一次'), 
                RText('§d[点击下线]  ').c(RAction.suggest_command, f'{utils.prefix_short} {nickname} kill ').h(f'下线§6{name}'))
        source.reply(msg)
        return

    if not source.has_permission(utils.permission_bot):
        source.reply('§c权限不足')
        return

    if action == 'spawn':
        if not is_online:
            base_cmd = utils.spawn_cmd(name)
            if base_cmd:
                if source.is_player:
                    server.execute(f'execute as {source.player} run {base_cmd}')
                else:
                    server.execute(base_cmd)
                source.reply(f"§b[BotKikai]§a已创建假人§d{name}§6（{nickname}）")
        else:
            source.reply(f"§b[BotKikai]§4假人§d{name}§6（{nickname}）§4已经在线")
    elif action == 'kill':
        if is_online:
            server.execute(utils.kill(name))
            source.reply(f"§b[BotKikai]§a假人§d{name}§6（{nickname}）§a已被下线")
    elif action in ["use", "huse", "hatk"]:
        if not is_online:
            base_cmd = utils.spawn_cmd(name)
            if base_cmd:
                if source.is_player:
                    server.execute(f'execute as {source.player} run {base_cmd}')
                else:
                    server.execute(base_cmd)
                source.reply(f"§b[BotKikai]§a已自动创建假人§d{name}§6（{nickname}）")
                time.sleep(2)
            else:
                return
        if action == "use": server.execute(utils.use(name)); source.reply(f"§b[BotKikai]§a假人§d{name}§6（{nickname}）§a右键一次")
        elif action == "huse": server.execute(utils.hold_use(name)); source.reply(f"§b[BotKikai]§a假人§d{name}§6（{nickname}）§a持续右键")
        elif action == "hatk": server.execute(utils.hold_attack(name)); source.reply(f"§b[BotKikai]§a假人§d{name}§6（{nickname}）§a持续左键")
    elif action == 'glowing': server.execute(utils.glowing(name))
    elif action == 'stop': server.execute(utils.stop(name))


def register_command_tree(server: PluginServerInterface):
    action_node = Text('nickname').runs(lambda src, ctx: bot_action(src, ctx, 'info')).then(
        Literal('spawn').runs(lambda src, ctx: bot_action(src, ctx, 'spawn'))
    ).then(
        Literal('kill').runs(lambda src, ctx: bot_action(src, ctx, 'kill'))
    ).then(
        Literal('use').runs(lambda src, ctx: bot_action(src, ctx, 'use'))
    ).then(
        Literal('huse').runs(lambda src, ctx: bot_action(src, ctx, 'huse'))
    ).then(
        Literal('hatk').runs(lambda src, ctx: bot_action(src, ctx, 'hatk'))
    ).then(
        Literal('glowing').runs(lambda src, ctx: bot_action(src, ctx, 'glowing'))
    ).then(
        Literal('stop').runs(lambda src, ctx: bot_action(src, ctx, 'stop'))
    )

    add_node = Literal('add').requires(lambda src: src.has_permission(utils.permission_list)).then(
        Text('name').then(
            Text('nickname').runs(add_bot_simple).then(
                Text('dim').then(
                    Float('pos_x').then(
                        Float('pos_y').then(
                            Float('pos_z').then(
                                Float('facing_y').then(
                                    Float('facing_p').runs(add_bot_full)
                                )
                            )
                        )
                    )
                )
            )
        )
    )

    del_node = Literal('del').requires(lambda src: src.has_permission(utils.permission_list)).then(
        Text('nickname').runs(del_bot)
    )

    root = Literal(utils.prefix_short).runs(show_help).then(
        Literal('list').runs(list_bots)
    ).then(
        Literal('reload').requires(lambda src: src.has_permission(utils.permission_list)).runs(reload_plugin)
    ).then(
        add_node
    ).then(
        del_node
    ).then(
        action_node
    )

    server.register_command(root)
