#!/usr/bin/python3
# -*-coding:utf-8-*-
"""
Created on 2021/1/4

@author: Jerry_FaGe
"""
import os
import json
import time
from utils import rtext as r
from imp import load_source

PlayerInfoAPI = load_source('PlayerInfoAPI', './plugins/PlayerInfoAPI.py')
config_path = './config/BotKikai.json'
prefix_short = '!!bk'
prefix = '!!botkikai'
permission_bot = 1  # 操作假人(spawn,use,kill)的最低权限  guest: 0, user: 1, helper: 2, admin: 3, owner: 4
permission_list = 3  # 操作假人列表(add,remove)的最低权限  guest: 0, user: 1, helper: 2, admin: 3, owner: 4
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
bot_dic = {}
bot_list = []
help_msg = '''
================== §bBotKikai §r==================
§6欢迎使用由@Jerry-FaGe开发的假人器械映射插件！
§6你可以在Github搜索MCDR-BotKikai找到本项目！
「君は道具ではなく、その名が似合う人になろんだ」
本插件中§d{prefix_short}§r与§d{prefix}§r效果相同，两者可以互相替换
§b{prefix_short} §r显示本帮助信息
§b{prefix_short} list §r显示假人列表
§b{prefix_short} reload §r重载插件配置
§b{prefix_short} add <name> <kikai> §r使用当前玩家参数添加一个名为<name>用于<kikai>的假人
§b{prefix_short} add <name> <kikai> <dim> <pos> <facing> §r使用自定义参数添加一个名为<name>用于<kikai>的假人
§b{prefix_short} del <kikai> §r从机器人列表移除用于<kikai>的假人
§b{prefix_short} <kikai> §r输出一个可点击的界面，自动根据假人是否在线改变选项
§b{prefix_short} <kikai> spawn §r召唤一个用于<kikai>的假人
§b{prefix_short} <kikai> kill §r干掉用于<kikai>的假人
§b{prefix_short} <kikai> use §r假人右键一次§r（执行此条前无需执行spawn，如假人不在线会自动上线）
'''.format(prefix=prefix, prefix_short=prefix_short)
help_head = """
================== §bBotKikai §r==================
§6欢迎使用由@Jerry-FaGe开发的假人器械映射插件！
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
    f"§b{prefix_short} del <kikai>": "§r从机器人列表移除用于<kikai>的假人",
    f"§b{prefix_short} <kikai>": "§r输出一个可点击的界面，自动根据假人是否在线改变选项",
    f'§b{prefix_short} <kikai> spawn': "§r召唤一个用于<kikai>的假人",
    f"§b{prefix_short} <kikai> kill": "§r干掉用于<kikai>的假人",
    f"§b{prefix_short} <kikai> use": "§r假人右键一次§r（执行此条前无需执行spawn，如假人不在线会自动上线）",
}


def read():
    global bot_dic
    with open(config_path, encoding='utf8') as f:
        bot_dic = json.load(f)


def save():
    with open(config_path, 'w', encoding='utf8') as f:
        json.dump(bot_dic, f, indent=4, ensure_ascii=False)


def search(kikai):
    for k, v in bot_dic.items():
        if kikai in v['nick']:
            return k


def get_pos(server, info):
    PlayerInfoAPI = server.get_plugin_instance('PlayerInfoAPI')
    pos = PlayerInfoAPI.getPlayerInfo(server, info.player, 'Pos')
    dim = PlayerInfoAPI.getPlayerInfo(server, info.player, 'Dimension')
    facing = PlayerInfoAPI.getPlayerInfo(server, info.player, 'Rotation')
    return pos, dim, facing


def spawn_cmd(server, info, name):
    if info.is_player:
        dim = bot_dic[name]['dim']
        pos = ' '.join([str(i) for i in bot_dic[name]['pos']])
        facing = bot_dic[name]['facing']
        cmd = f'/player {name} spawn at {pos} facing {facing} in {dim}'
        return cmd
    else:
        return f'/player {name} spawn'


def spawn(server, info, name):
    return spawn_cmd(server, info, name)


def kill(name):
    return f'/player {name} kill'


def use(name):
    return f'/player {name} use'


def on_load(server, old):
    global bot_list
    server.add_help_message(f'{prefix_short}', r.RText(
        '假人器械映射').c(r.RAction.run_command, f'{prefix_short}').h('点击查看帮助'))
    if old is not None and old.bot_list is not None:
        bot_list = old.bot_list
    else:
        bot_list = []
    if not os.path.isfile(config_path):
        save()
    else:
        try:
            read()
        except Exception as e:
            server.say('§b[BotKikai]§4配置加载失败，请确认配置路径是否正确：{}'.format(e))


test = {
    "Fallen_Breath": {
        "nick": ["伪和平", "主世界伪和平"],
        "dim": "minecraft:overworld",
        "pos": [0, 70, 0],
        "facing": "0 0"
    }
}


def on_info(server, info):
    if info.is_user:
        if info.content.startswith(prefix) or info.content.startswith(prefix_short):
            args = info.content.split(' ')
            operate_bot(server, info, args)


def operate_bot(server, info, args):
    global bot_dic, bot_list
    permission = server.get_permission_level(info)
    if len(args) == 1:
        # server.reply(info, help_msg)
        head = [help_head]
        body = [r.RText(f'{k} {v}\n').c(
            r.RAction.suggest_command, k.replace('§b', '')).h(v)
                for k, v in help_body.items()]
        server.reply(info, r.RTextList(*(head + body)))

    elif len(args) == 2:
        if args[1] == "list":
            c = ['']
            for name, bot_info in bot_dic.items():
                if name in bot_list:
                    bot_msg = r.RTextList(
                        '\n'
                        f'§7----------- §6{name} §a在线 §7 -----------\n',
                        f'§7此假人用于:§6 {bot_info["nick"]}\n',
                        # f'§7Dimension:§6 {bot_info["dim"]}\n',
                        # r.RText(
                        #     f'§7Position:§6 {bot_info["pos"]}\n', ).c(
                        #     r.RAction.run_command,
                        #     '[x:{}, y:{}, z:{}, name:{}, dim{}]'.format(
                        #         *[int(i) for i in bot_info['pos']], name, bot_info['dim'])).h(
                        #     '点击显示可识别坐标点'),
                        # f'§7Facing:§6 {bot_info["facing"]}\n',
                        r.RText('§d[点击use]  ').c(
                            r.RAction.run_command, f'{prefix_short} {name} use').h(f'§6{name}§7右键一次'),
                        r.RText('§d[点击下线]  ').c(
                            r.RAction.run_command, f'{prefix_short} {name} kill ').h(f'下线§6{name}'),
                        r.RText('§d[查看详情]  ').c(
                            r.RAction.run_command, f'{prefix_short} {name}').h(f'显示§6{name}§r的详细信息')
                    )
                else:
                    bot_msg = r.RTextList(
                        '\n'
                        f'§7----------- §6{name} §4离线 §7 -----------\n',
                        f'§7此假人用于:§6 {bot_info["nick"]}\n',
                        # f'§7Dimension:§6 {bot_info["dim"]}\n',
                        # r.RText(
                        #     f'§7Position:§6 {bot_info["pos"]}\n', ).c(
                        #     r.RAction.run_command,
                        #     '[x:{}, y:{}, z:{}, name:{}, dim{}]'.format(
                        #         *[int(i) for i in bot_info['pos']], name, bot_info['dim'])).h(
                        #     '点击显示可识别坐标点'),
                        # f'§7Facing:§6 {bot_info["facing"]}\n',
                        r.RText('§d[点击召唤]  ').c(
                            r.RAction.run_command, f'{prefix_short} {name} spawn').h(f'召唤§6{name}'),
                        r.RText('§d[点击use]  ').c(
                            r.RAction.run_command, f'{prefix_short} {name} use ').h(f'召唤§6{name}§r并右键一次'),
                        r.RText('§d[查看详情]  ').c(
                            r.RAction.run_command, f'{prefix_short} {name}').h(f'显示§6{name}§r的详细信息')
                    )
                c.append(bot_msg)
            server.reply(info, r.RTextList(*c))

        elif args[1] == "reload":
            try:
                read()
                server.say('§b[BotKikai]§a由玩家§d{}§a发起的BotKikai重载成功'.format(info.player))
            except Exception as e:
                server.say('§b[BotKikai]§4由玩家§d{}§4发起的BotKikai重载失败：{}'.format(info.player, e))

        elif search(args[1]):
            name = search(args[1])
            if name not in bot_list:
                msg = r.RTextList(
                    '\n'
                    f'§7----------- §6{name} §4离线 §7-----------\n',
                    f'§7此假人用于:§6 {bot_dic.get(name)["nick"]}\n',
                    f'§7维度:§6 {bot_dic.get(name)["dim"]}\n',
                    r.RText(
                        f'§7坐标:§6 {bot_dic.get(name)["pos"]}\n', ).c(
                        r.RAction.run_command,
                        '[x:{}, y:{}, z:{}, name:{}, dim{}]'.format(
                            *[int(i) for i in bot_dic.get(name)['pos']], name, bot_dic.get(name)['dim'])).h(
                        '点击显示可识别坐标点'),
                    f'§7朝向:§6 {bot_dic.get(name)["facing"]}\n',
                    r.RText('§d[点击召唤]  ').c(
                        r.RAction.run_command, f'{prefix_short} {name} spawn').h(f'召唤§6{name}'),
                    r.RText('§d[点击use]  ').c(
                        r.RAction.run_command, f'{prefix_short} {name} use ').h(f'召唤§6{name}并右键一次')
                )
            else:
                msg = r.RTextList(
                    '\n'
                    f'§7----------- §6{name} §a在线 §7-----------\n',
                    f'§7此假人用于:§6 {bot_dic.get(name)["nick"]}\n',
                    f'§7维度:§6 {bot_dic.get(name)["dim"]}\n',
                    r.RText(
                        f'§7坐标:§6 {bot_dic.get(name)["pos"]}\n', ).c(
                        r.RAction.run_command,
                        '[x:{}, y:{}, z:{}, name:{}, dim{}]'.format(
                            *[int(i) for i in bot_dic.get(name)['pos']], name, bot_dic.get(name)['dim'])).h(
                        '点击显示可识别坐标点'),
                    f'§7朝向:§6 {bot_dic.get(name)["facing"]}\n',
                    r.RText('§d[点击use]  ').c(
                        r.RAction.run_command, f'{prefix_short} {name} use').h(f'§6{name}§7右键一次'),
                    r.RText('§d[点击下线]  ').c(
                        r.RAction.run_command, f'{prefix_short} {name} kill ').h(f'下线§6{name}')
                )
            server.reply(info, msg)

        else:
            server.reply(info, f"§b[BotKikai]§4未查询到§d{args[1]}§4对应的假人")

    elif len(args) == 3:
        if args[1] == "del" and permission >= permission_list:
            name = search(args[2])
            if name:
                del bot_dic[name]
                bot_list.remove(name) if name in bot_list else bot_list
                save()
                server.reply(info, f'§b[BotKikai]§a已删除机器人{name}')
            else:
                server.reply(info, f"§b[BotKikai]§4未查询到§d{args[1]}§4对应的假人")

        else:
            name = search(args[1])
            if name:
                if args[2] == "spawn" and permission >= permission_bot:
                    if name not in bot_list:
                        server.execute(spawn(server, info, name))
                        bot_list.append(name)
                    else:
                        server.reply(info, f"§b[BotKikai]§4假人§d{name}§6（{args[1]}）§4已经在线")

                elif args[2] == "kill" and permission >= permission_bot:
                    if name in bot_list:
                        server.execute(kill(name))
                        bot_list.remove(name)
                        server.reply(info, f"§b[BotKikai]§a假人§d{name}§6（{args[1]}）§a已被下线")

                elif args[2] == "use" and permission >= permission_bot:
                    if name not in bot_list:
                        server.execute(spawn(server, info, name))
                        bot_list.append(name)
                        server.reply(info, f"§b[BotKikai]§a已自动创建假人§d{name}§6（{args[1]}）")
                        time.sleep(2)
                    server.execute(use(name))
                    server.reply(info, f"§b[BotKikai]§a假人§d{name}§6（{args[1]}）§a右键一次")

                else:
                    server.reply(info, f"§b[BotKikai]§4参数输入错误，输入§6{prefix_short}§4查看帮助信息")
            else:
                server.reply(info, f"§b[BotKikai]§4未查询到§d{args[1]}§4对应的假人")
    elif len(args) == 4:
        if args[1] == 'add' and permission >= permission_list:
            nick_ls = [] if bot_dic.get(args[2], None) is None else bot_dic.get(args[2])['nick']
            if args[2] not in nick_ls:
                nick_ls.append(args[2])
            nick_ls.append(args[3]) if args[3] != args[2] else nick_ls
            pos, dim, facing = get_pos(server, info)
            bot_dic[args[2]] = {
                'nick': nick_ls,
                'dim': dim,
                'pos': pos,
                'facing': f'{facing[0]} {facing[1]}'
            }
            save()
            server.reply(info, f'§b[BotKikai]§a已添加机器人{args[2]}')
        else:
            server.reply(info, '§b[BotKikai]§4命令格式不正确或权限不足')
    elif len(args) == 10:
        if args[1] == 'add' and permission >= permission_list:
            if args[4] in dimension_convert.keys():
                dim = dimension_convert[args[4]]
                pos = [int(i) for i in [args[5], args[6], args[7]]]
                facing = f'{args[8]} {args[9]}'
                nick_ls = [] if bot_dic.get(args[2], None) is None else bot_dic.get(args[2])['nick']
                if args[2] not in nick_ls:
                    nick_ls.append(args[2])
                nick_ls.append(args[3]) if args[3] != args[2] else nick_ls
                bot_dic[args[2]] = {
                    'nick': nick_ls,
                    'dim': dim,
                    'pos': pos,
                    'facing': facing
                }
                save()
                server.reply(info, f'§b[BotKikai]§a已添加机器人{args[2]}')
            else:
                server.reply(info, '§b[BotKikai]§4无法识别的维度')
        else:
            server.reply(info, '§b[BotKikai]§4命令格式不正确或权限不足')


def on_server_stop(server, return_code):
    global bot_list
    bot_list = []