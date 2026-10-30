"""Read-only rendering for plugin help and bot panels."""

from __future__ import annotations

import math
import unicodedata
from typing import TYPE_CHECKING

from mcdreforged.api.rtext import RText, RTextList, RAction, RColor

from .config import config

if TYPE_CHECKING:
    from .bot import Bot


LIST_PAGE_SIZE = 10
LIST_NAME_LIMIT = 7
_LIST_STATUSES = {'all': '全部', 'online': '在线', 'offline': '离线'}

# Vanilla 1.21.4 bitmap advances include the one-pixel gap after each glyph.
# Most ASCII glyphs advance 6 pixels; CJK glyphs advance 9 and spaces 4.
_CHAT_GLYPH_WIDTHS = {
    char: width
    for width, chars in (
        (2, "!.,:;'i|"), (3, '`l'), (4, ' "()*I[]t{}'),
        (5, '<>fk'), (7, '@~'), (8, '…'),
    )
    for char in chars
}


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
        f"§7{config.prefix_short} list §6[online§7|§6offline] [page]": "§r分页查看假人，每页 10 条，可筛选在线或离线",
        f"§7{config.prefix_short} list §6[online§7|§6offline] §7search §6<关键词> [page]": "§r搜索登记名、假人名和别名，不区分大小写",
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


def _online_status(online: bool) -> RText:
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
        RText(' · ', RColor.gray), _online_status(bot.is_online), RText(' -----\n', RColor.gray),
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


def _short_label(text: str, width: int = 24) -> str:
    # Approximate chat width for search keywords without changing the query.
    widths = [2 if unicodedata.east_asian_width(char) in 'WF' else 1 for char in text]
    if sum(widths) <= width:
        return text
    used = 0
    for index, size in enumerate(widths):
        if used + size > width - 1:
            return text[:index] + '…'
        used += size
    return text


def _chat_text_width(text: str) -> int:
    # Estimate the unstyled default font, not resource packs or the uniform font.
    return sum(_CHAT_GLYPH_WIDTHS.get(char, 9 if unicodedata.east_asian_width(char) in 'WF' else 6)
               for char in text)


def _short_list_name(name: str) -> str:
    return name if len(name) <= LIST_NAME_LIMIT else name[:LIST_NAME_LIMIT] + '…'


def _list_name_padding(name: str, width: int) -> str:
    space_width = _CHAT_GLYPH_WIDTHS[' ']
    remaining = width - _chat_text_width(name)
    # Round to the nearest ordinary space; the button keeps its own separator.
    return ' ' * max(0, (remaining + space_width // 2) // space_width)


def render_bot_summary(bot: Bot, *, can_operate: bool = True, online: bool | None = None,
                       name_width: int = 0) -> RTextList:
    online = bot.is_online if online is None else online
    prefix = f'{config.prefix_short} {bot.name}'
    name = _display_name(bot)
    short_name = _short_list_name(name)
    hover = RTextList(
        RText(name, RColor.gold), RText(f'\n登记名: {bot.name}\n', RColor.gray),
        _record_details(bot),
        RText('\n这是登记的召唤位置，不是实时位置', RColor.yellow),
    )
    result = RTextList(
        RText('[', RColor.gray), _online_status(online), RText('] ', RColor.gray),
        RText(short_name, RColor.gold).h(hover),
        _list_name_padding(short_name, name_width),
    )
    if can_operate:
        if online:
            result.append(' ', _button('下线', f'{prefix} kill', '请求让假人下线，保留插件记录', color=RColor.red))
        else:
            result.append(' ', _button('上线', f'{prefix} spawn', '在登记位置召唤假人', color=RColor.green))
        result.append(' ', _button('右键', f'{prefix} use', '右键一次', warning='离线时会先自动召唤假人'))
    result.append(' ', _button('详情', prefix, '查看详情与可用的管理入口'))
    return result


def _list_command(status: str = 'all', query: str | None = None, page: int = 1) -> str:
    command = f'{config.prefix_short} list'
    if status != 'all':
        command += f' {status}'
    if query is not None:
        command += f' search {query}'
    if page != 1:
        command += f' {page}'
    return command


def render_bot_list(bots: list[Bot], *, status: str = 'all', query: str | None = None,
                    page: int = 1, can_operate: bool = True) -> RTextList:
    if status not in _LIST_STATUSES:
        raise ValueError('未知的列表筛选条件')
    if type(page) is not int or page < 1:
        raise ValueError('页码必须为正整数')
    if query is not None and (not query or any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in query)):
        raise ValueError('搜索关键词不能为空，也不能包含空白或控制字符')

    # Read each online flag once so filtering, row status and controls agree.
    rows = [(bot, bot.is_online) for bot in bots]
    if status != 'all':
        rows = [(bot, online) for bot, online in rows if online == (status == 'online')]
    if query is not None:
        needle = query.casefold()
        rows = [(bot, online) for bot, online in rows if any(
            needle in name.casefold() for name in (bot.name, bot.real_name, *bot.nicknames))]
    rows.sort(key=lambda row: (row[0].name.casefold(), row[0].name))
    total = len(rows)
    pages = max(1, (total + LIST_PAGE_SIZE - 1) // LIST_PAGE_SIZE)
    requested_page = page
    page = min(page, pages)

    result = RTextList(
        RText('假人列表', RColor.gold), RText(' · ', RColor.gray), RText(_LIST_STATUSES[status], RColor.white),
        RText(' · 第 ', RColor.gray), RText(f'{page}/{pages}', RColor.white), RText(' 页 · 共 ', RColor.gray),
        RText(str(total), RColor.white), RText(' 个', RColor.gray),
    )
    if query is not None:
        result.append(
            RText('\n搜索: ', RColor.gray), RText(_short_label(query), RColor.white).h(RText(query, RColor.white)),
        )
    result.append('\n')
    for mode, label in _LIST_STATUSES.items():
        if mode == status:
            result.append(RText(f'[{label}]', RColor.gold).h(RText(f'当前筛选: {label}', RColor.gray)))
        else:
            result.append(_button(label, _list_command(mode, query), f'查看{label}假人，保留搜索并回到第一页'))
        result.append(' ')
    result.append(_button('搜索', _list_command(status) + ' search ', '填写一个关键词，搜索登记名、假人名或别名'))
    if query is not None:
        result.append(' ', _button('清除搜索', _list_command(status), '清除关键词，保留状态筛选并回到第一页'))

    result.append('\n')
    if requested_page > pages:
        result.append(RText('\n页码超出范围，已显示最后一页', RColor.yellow))
    if total:
        start = (page - 1) * LIST_PAGE_SIZE
        page_rows = rows[start:start + LIST_PAGE_SIZE]
        # Only names actually shown on this page should determine its column width.
        name_width = max(_chat_text_width(_short_list_name(_display_name(bot))) for bot, _ in page_rows)
        for bot, online in page_rows:
            result.append('\n', render_bot_summary(
                bot, can_operate=can_operate, online=online, name_width=name_width))
    elif not bots:
        result.append(RText('\n尚未登记假人，可查看帮助了解添加方式', RColor.gray))
    elif query is not None:
        result.append(RText('\n没有找到符合条件的假人\n可换个关键词、清除搜索或切换状态筛选', RColor.gray))
    else:
        result.append(RText(f'\n没有{_LIST_STATUSES[status]}假人，可切换到「全部」查看记录', RColor.gray))

    previous = (_button('上一页', _list_command(status, query, page - 1), '查看上一页，保留筛选和搜索') if page > 1 else
                RText('[上一页]', RColor.gray).h(RText('已经是第一页', RColor.gray)))
    following = (_button('下一页', _list_command(status, query, page + 1), '查看下一页，保留筛选和搜索') if page < pages else
                 RText('[下一页]', RColor.gray).h(RText('已经是最后一页', RColor.gray)))
    result.append(
        '\n\n', previous, ' ', following,
        ' ', _button('刷新', _list_command(status, query, page), '重新显示当前页，读取插件内存中的最新状态，不主动查询服务器'),
    )
    if not bots:
        result.append(' ', _button('帮助', config.prefix_short, '查看添加假人的命令和权限要求'))
    if not can_operate:
        result.append(RText('\n当前无假人操作权限', RColor.gray))
    result.append(RText('\n悬浮名称查看信息；点击按钮填入命令，回车执行', RColor.gray))
    return result
