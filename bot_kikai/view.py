"""Read-only rendering for plugin help and bot panels."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from mcdreforged.api.rtext import RText, RTextList, RAction, RColor

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
        f"§7{config.prefix_short} §6<kikai> §7alias": "§r打开别名管理面板",
        f"§7{config.prefix_short} §6<kikai> §7alias add §6<alias>": "§r添加别名，不改变登记位置和朝向",
        f"§7{config.prefix_short} §6<kikai> §7alias del §6<alias>": "§r移除别名，不删除假人记录或下线假人",
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


def _button(label: str, command: str, description: str, *,
            color: RColor = RColor.aqua, warning: str | None = None) -> RText:
    hover = RTextList(RText(description, RColor.white))
    if warning:
        hover.append('\n', RText(warning, RColor.yellow))
    hover.append('\n', RText('点击填入命令，检查后按回车执行', RColor.gray))
    return RText(f'[{label}]', color).c(RAction.suggest_command, command).h(hover)


def _custom_aliases(bot: Bot) -> list[str]:
    identities = {bot.name.casefold(), bot.real_name.casefold()}
    return [nick for nick in bot.nicknames if nick.casefold() not in identities]


def _display_name(bot: Bot) -> str:
    aliases = _custom_aliases(bot)
    return aliases[0] if aliases else bot.name


def _display_nicknames(bot: Bot) -> RText:
    aliases = _custom_aliases(bot)
    return RText('、'.join(aliases) if aliases else '无自定义别名',
                 RColor.white if aliases else RColor.gray)


def _online_status(bot: Bot) -> RText:
    online = bot.is_online
    return RText('在线' if online else '离线', RColor.green if online else RColor.red)


def _display_player_name(bot: Bot) -> RTextList:
    confirmed_name = bot.confirmed_name
    result = RTextList(
        RText('假人名: ', RColor.gray),
        RText(confirmed_name or bot.expected_name, RColor.white).h(
            RText(f'登记名: {bot.name}', RColor.gray),
            RText('\n命令按钮始终使用登记名定位这条记录', RColor.gray),
        ),
    )
    if confirmed_name is None:
        result.append(RText('（待确认）', RColor.yellow).h(
            RText('暂用配置推算的名称；收到服务端名称后自动保存', RColor.gray)))
    return result


def _number(value: float) -> str:
    text = f'{value:.2f}'.rstrip('0').rstrip('.')
    return '0' if text == '-0' else text


def _record_details(bot: Bot, *, coordinate_link: bool = False) -> RTextList:
    dimension = {
        'minecraft:overworld': '主世界',
        'minecraft:the_nether': '下界',
        'minecraft:the_end': '末地',
    }.get(bot.dimension, bot.dimension)
    position = RText(f'{dimension} ({", ".join(_number(v) for v in bot.position)})',
                     RColor.aqua if coordinate_link else RColor.white)
    if coordinate_link:
        # Share the original block position, never the rounded display coordinates.
        x, y, z = (math.floor(v) for v in bot.position)
        position.c(RAction.suggest_command, f'[x:{x}, y:{y}, z:{z}, name:{bot.name}, dim:{bot.dimension}]').h(
            RText(f'维度 ID: {bot.dimension}\n原始坐标: {bot.position}', RColor.white),
            RText('\n这是登记的召唤位置，不是实时位置', RColor.yellow),
            RText('\n点击填入方块坐标点，按回车发送', RColor.gray),
        )
    facing = RText(' / '.join(_number(v) for v in bot.facing), RColor.white).h(
        RText(f'水平角 (yaw) / 俯仰角 (pitch)\n原始朝向: {bot.facing}', RColor.white))
    return RTextList(
        _display_player_name(bot),
        RText('\n别名: ', RColor.gray), _display_nicknames(bot),
        RText('\n登记位置: ', RColor.gray), position,
        RText('\n登记朝向: ', RColor.gray), facing,
    )


def render_bot_actions(bot: Bot) -> RTextList:
    prefix = f'{config.prefix_short} {bot.name}'
    actions = RTextList()
    if bot.is_online:
        actions.append(
            _button('下线', f'{prefix} kill', '请求让假人下线，保留插件记录', color=RColor.red),
            ' ', _button('停止', f'{prefix} stop', '停止假人的所有动作，不让假人下线'),
        )
    else:
        actions.append(_button('上线', f'{prefix} spawn', '在登记位置召唤假人', color=RColor.green))
    auto_spawn = '离线时会先自动召唤假人'
    actions.append(
        ' ', _button('报点/发光', f'{prefix} where', '发光两分钟，并输出登记坐标（不是实时位置）', warning=auto_spawn),
        '\n', _button('右键', f'{prefix} use', '右键一次', warning=auto_spawn),
        ' ', _button('持续右键', f'{prefix} huse ', '持续右键；可在末尾填写正整数间隔（gt）', warning=auto_spawn),
        ' ', _button('左键', f'{prefix} atk', '左键一次', warning=auto_spawn),
        ' ', _button('持续左键', f'{prefix} hatk ', '持续左键；可在末尾填写正整数间隔（gt）', warning=auto_spawn),
    )
    return actions


def render_bot_info(bot: Bot, *, can_operate: bool = True, can_manage: bool = False) -> RTextList:
    prefix = f'{config.prefix_short} {bot.name}'
    result = RTextList(
        RText('----- ', RColor.gray), RText(_display_name(bot), RColor.gold),
        RText(' · ', RColor.gray), _online_status(bot), RText(' -----\n', RColor.gray),
        _record_details(bot, coordinate_link=True), '\n\n',
    )
    if can_operate:
        result.append(render_bot_actions(bot))
    else:
        result.append(RText('当前无假人操作权限', RColor.gray))
    if can_manage:
        aliases = _custom_aliases(bot)
        remove = (_button('移除别名', f'{prefix} alias', '打开别名列表，选择要移除的别名') if aliases else
                  RText('[移除别名]', RColor.gray).h(RText('当前没有可移除的自定义别名', RColor.gray)))
        result.append(
            RText('\n\n管理: ', RColor.gray),
            _button('添加别名', f'{prefix} alias add ', '在末尾填写新别名；不改变位置、朝向或动作', color=RColor.green),
            ' ', remove,
            ' ', _button('删除记录', f'{config.prefix_short} del {bot.name}', '删除这条假人记录',
                         color=RColor.red, warning='只删除插件记录，不会让在线假人下线'),
        )
    result.append(
        '\n\n', _button('刷新', prefix, '重新显示当前详情'),
        ' ', _button('假人列表', f'{config.prefix_short} list', '查看已登记的假人'),
        RText('\n点击按钮填入命令，按回车执行', RColor.gray),
    )
    return result


def render_alias_panel(bot: Bot) -> RTextList:
    prefix = f'{config.prefix_short} {bot.name}'
    aliases = _custom_aliases(bot)
    result = RTextList(
        RText('----- ', RColor.gray), RText(_display_name(bot), RColor.gold),
        RText(' · 别名管理 -----\n', RColor.gray),
        _display_player_name(bot),
        RText('\n登记名: ', RColor.gray), RText(bot.name, RColor.white),
        RText('\n登记名和假人名始终可查找，不可移除\n', RColor.gray),
    )
    if aliases:
        for alias in aliases:
            result.append(
                '\n', RText(alias, RColor.white), ' ',
                _button('移除', f'{prefix} alias del {alias}', f'移除别名「{alias}」',
                        color=RColor.red, warning='只移除别名，不删除记录或下线假人'),
            )
    else:
        result.append('\n', RText('无自定义别名', RColor.gray))
    result.append(
        '\n\n', _button('添加别名', f'{prefix} alias add ', '在末尾填写新别名', color=RColor.green),
        ' ', _button('返回详情', prefix, '返回假人详情面板'),
        RText('\n点击按钮填入命令，按回车执行', RColor.gray),
    )
    return result


def render_bot_summary(bot: Bot, *, can_operate: bool = True) -> RTextList:
    result = RTextList(
        RText('\n----- ', RColor.gray), RText(bot.name, RColor.gold).h(_record_details(bot)),
        RText(' · ', RColor.gray), _online_status(bot), RText(' -----\n', RColor.gray),
        RText('别名: ', RColor.gray), _display_nicknames(bot), '\n',
    )
    if can_operate:
        result.append(render_bot_actions(bot), '\n')
    result.append(_button('详情', f'{config.prefix_short} {bot.name}', '查看详情与可用的管理入口'))
    return result


def render_bot_list(bots: list[Bot], *, can_operate: bool = True) -> RTextList | str:
    if not bots:
        return "§b[BotKikai] §7没有找到符合条件的假人"

    messages: list[RTextList] = []
    for bot in bots:
        messages.append(render_bot_summary(bot, can_operate=can_operate))
        messages.append(RTextList("\n"))
    return RTextList(*messages)
