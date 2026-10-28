"""Read-only rendering for plugin help and bot panels."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from mcdreforged.api.rtext import RText, RTextList, RAction

from .config import config

if TYPE_CHECKING:
    from .bot import Bot


HELP_HEAD = """
================== §bBotKikai §r==================
§6欢迎使用由 @Jerry-FaGe 开发的假人器械映射插件！
§6你可以在 Github 搜索 MCDR-BotKikai 找到本项目！
§7「君は道具ではなく、その名が似合う人になろんだ」
===========================================
"""


def get_help_body() -> dict[str, str]:
    return {
        f"§7{config.prefix_short}": "§r显示本帮助信息",
        f"§7{config.prefix_short} list §6[online§7|§6offline]": "§r显示假人列表，可筛选在线或离线",
        f"§7{config.prefix_short} reload": "§r重载插件配置",
        f"§7{config.prefix_short} add §6<name> <kikai>": "§r使用当前玩家参数添加一个名为 §6<name> §r用于 §6<kikai> §r的假人",
        f"§7{config.prefix_short} add §6<name> <kikai> <dim> <pos> <facing>": "§r使用自定义参数添加一个名为 §6<name> §r用于 §6<kikai> §r的假人",
        f"§7{config.prefix_short} del §6<kikai>": "§r删除用于 §6<kikai> §r的假人记录（不会下线）",
        f"§7{config.prefix_short} §6<kikai>": "§r输出用于 §6<kikai> §r的假人信息",
        f'§7{config.prefix_short} §6<kikai> §7spawn': "§r上线用于 §6<kikai> §r的假人",
        f"§7{config.prefix_short} §6<kikai> §7kill": "§r下线用于 §6<kikai> §r的假人",
        f"§7{config.prefix_short} §6<kikai> §7where": "§r假人发光两分钟并输出记录坐标",
        f"§7{config.prefix_short} §6<kikai> §7use": "§r假人右键一次",
        f"§7{config.prefix_short} §6<kikai> §7huse §6[<interval>]": "§r假人持续右键，后接正整数可控制间隔 gt",
        f"§7{config.prefix_short} §6<kikai> §7atk": "§r假人左键一次",
        f"§7{config.prefix_short} §6<kikai> §7hatk §6[<interval>]": "§r假人持续左键，后接正整数可控制间隔 gt",
        f"§7{config.prefix_short} §6<kikai> §7stop": "§r假人停止一切动作",
    }


def render_help() -> RTextList:
    body = [RText(f'{key}§7: {text}\n').c(
        RAction.suggest_command, key.replace('§7', '').replace('§6', '')).h(text)
        for key, text in get_help_body().items()]
    return RTextList(HELP_HEAD, *body)


def render_bot_actions(bot: Bot) -> RTextList:
    special_rtext = RTextList()
    if bot.is_online:
        special_rtext.append(
            RText('§4[下线] ').c(RAction.suggest_command, f'{config.prefix_short} {bot.name} kill').h(f'下线 §6{bot.name}'),
            RText('§b[停止] ').c(RAction.suggest_command, f'{config.prefix_short} {bot.name} stop').h(f'§6{bot.name} §7停止所有动作'),
        )
    else:
        special_rtext.append(
            RText('§a[上线] ').c(RAction.suggest_command, f'{config.prefix_short} {bot.name} spawn').h(f'召唤 §6{bot.name}'),
        )

    return RTextList(
        special_rtext,
        RText('§b[报点] ').c(RAction.suggest_command, f'{config.prefix_short} {bot.name} where').h(f'§6{bot.name} §7发光两分钟并输出坐标'),
        RText('§b[右键] ').c(RAction.suggest_command, f'{config.prefix_short} {bot.name} use').h(f'§6{bot.name} §7右键一次'),
        RText('§b[持续右键] ').c(RAction.suggest_command, f'{config.prefix_short} {bot.name} huse ').h(f'§6{bot.name} §7持续右键，后接正整数可控制间隔 gt'),
        RText('§b[左键] ').c(RAction.suggest_command, f'{config.prefix_short} {bot.name} atk').h(f'§6{bot.name} §7左键一次'),
        RText('§b[持续左键] ').c(RAction.suggest_command, f'{config.prefix_short} {bot.name} hatk ').h(f'§6{bot.name} §7持续左键，后接正整数可控制间隔 gt'),
    )


def _display_nicknames(bot: Bot) -> str:
    return ", ".join(nick for nick in bot.nicknames
                     if nick.lower() not in [bot.name.lower(), bot.real_name.lower()])


def render_bot_info(bot: Bot) -> RTextList:
    nickname = _display_nicknames(bot)
    online_status = '§a在线' if bot.is_online else '§4离线'
    return RTextList(
        f'§7----------- §6{bot.name} {online_status} §7-----------',
        f'\n§7用于:§d {nickname}',
        f'\n§7维度:§d {bot.dimension}',
        RText(f'\n§7坐标:§d {bot.position}').c(RAction.suggest_command, f'[x:{math.floor(bot.position[0])}, y:{math.floor(bot.position[1])}, z:{math.floor(bot.position[2])}, name:{bot.name}, dim:{bot.dimension}]').h('点击填入坐标点，按回车发送'),
        f'\n§7朝向:§d {bot.facing}\n',
        render_bot_actions(bot),
    )


def render_bot_summary(bot: Bot) -> RTextList:
    nickname = _display_nicknames(bot)
    online_status = '§a在线' if bot.is_online else '§4离线'
    return RTextList(
        '\n§7----------- ',
        RText(f'§6{bot.name}').h(
            f'§7用于:§d {nickname}\n',
            f'§7维度:§d {bot.dimension}\n',
            f'§7坐标:§d {bot.position}\n',
            f'§7朝向:§d {bot.facing}'
        ),
        f' {online_status} §7-----------\n',
        f'§7此假人用于:§d {nickname}\n',
        render_bot_actions(bot),
    )


def render_bot_list(bots: list[Bot]) -> RTextList | str:
    if not bots:
        return "§b[BotKikai] §7没有找到符合条件的假人"

    messages: list[RTextList] = []
    for bot in bots:
        messages.append(render_bot_summary(bot))
        messages.append(RTextList("\n"))
    return RTextList(*messages)
