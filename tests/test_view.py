import json
from pathlib import Path

import pytest

from bot_kikai import command, utils, view
from bot_kikai.bot import Bot
from bot_kikai.config import config


def _json_nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _json_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _json_nodes(child)


def _click_commands(message):
    nodes = _json_nodes(json.loads(message.to_json_str()))
    events = [node['clickEvent'] for node in nodes if 'clickEvent' in node]
    assert all(event['action'] == 'suggest_command' for event in events)
    return [event['value'] for event in events]


@pytest.mark.parametrize('online', [False, True])
@pytest.mark.parametrize('prefix', ['!!bk', '!!farm'])
def test_action_buttons_preserve_commands_and_online_controls(env, bot, online, prefix):
    config.prefix_short = prefix
    bot.is_online = online
    actions = ['kill', 'stop'] if online else ['spawn']
    actions += ['where', 'use', 'huse ', 'atk', 'hatk ']
    expected = [f'{prefix} SandBot {action}' for action in actions]

    assert _click_commands(view.render_bot_actions(bot)) == expected
    summary_actions = ['kill', 'use'] if online else ['spawn', 'use']
    assert _click_commands(view.render_bot_summary(bot)) == [
        *(f'{prefix} SandBot {action}' for action in summary_actions), f'{prefix} SandBot',
    ]
    assert _click_commands(view.render_bot_info(bot)) == [
        '[x:1, y:64, z:-3, name:SandBot, dim:minecraft:overworld]',
        *expected,
        f'{prefix} SandBot', f'{prefix} list',
    ]

    status = '\u5728\u7ebf' if online else '\u79bb\u7ebf'
    for renderer in (view.render_bot_info, view.render_bot_summary):
        assert status in renderer(bot).to_plain_text()
        nodes = _json_nodes(json.loads(renderer(bot).to_json_str()))
        assert {'text': status, 'color': 'green' if online else 'red'} in nodes


@pytest.mark.parametrize('renderer', [view.render_bot_info, view.render_bot_summary])
def test_panels_hide_identity_aliases_and_preserve_nickname_order(env, renderer):
    config.bot_name_prefix = 'b_'
    bot = Bot(env.server, 'SandBot',
              ['SANDBOT', 'b_SANDBOT', 'farm', '\u5237\u6c99\u673a'],
              'minecraft:overworld', [1.5, 64, -2.5], [180, 0])
    nicknames = bot.nicknames.copy()
    nodes = _json_nodes(json.loads(renderer(bot).to_json_str()))
    assert any(node.get('text') == 'farm\u3001\u5237\u6c99\u673a' for node in nodes)
    assert bot.nicknames == nicknames


def test_help_reads_current_prefix_and_preserves_templates(env):
    original = view.render_help()
    config.prefix_short = '!!farm'
    current = view.render_help()
    templates = [
        '', ' list [online|offline] [page]',
        ' list [online|offline] search <\u5173\u952e\u8bcd> [page]', ' reload',
        ' add <name> <kikai>', ' add <name> <kikai> <dim> <pos> <facing>',
        ' del <kikai>', ' <kikai> alias', ' <kikai> alias add <alias>', ' <kikai> alias del <alias>',
        ' <kikai>', ' <kikai> spawn', ' <kikai> kill',
        ' <kikai> where', ' <kikai> use', ' <kikai> huse [<interval>]',
        ' <kikai> atk', ' <kikai> hatk [<interval>]', ' <kikai> stop',
    ]

    assert _click_commands(original) == ['!!bk' + item for item in templates]
    assert _click_commands(current) == ['!!farm' + item for item in templates]
    assert current.to_plain_text().startswith(view.HELP_HEAD)
    assert utils.help_head == view.HELP_HEAD
    assert utils.get_help_body() == view.get_help_body()

    command.show_help(env.source)
    assert env.source.messages == [current.to_plain_text()]


def test_list_sorts_records_without_reordering_input(env, bot):
    other = Bot(env.server, 'OtherBot', [], 'minecraft:the_nether', [0, 70, 0], [0, 0])
    bots = [bot, other]
    result = view.render_bot_list(bots)

    rows = [line for line in result.to_plain_text().splitlines() if line.startswith('[\u79bb\u7ebf]')]
    assert rows == [view.render_bot_summary(other, name_width=48).to_plain_text(),
                    view.render_bot_summary(bot, name_width=48).to_plain_text()]
    assert bots == [bot, other]


def test_empty_list_keeps_navigation_and_explains_missing_records(env):
    expected = view.render_bot_list([]).to_plain_text()
    assert '\u5c1a\u672a\u767b\u8bb0\u5047\u4eba' in expected
    assert '[\u641c\u7d22]' in expected
    assert '[\u5e2e\u52a9]' in expected
    command.list_bots(env.source, env.manager)
    assert env.source.messages == [expected]


@pytest.mark.parametrize('status, expected_names', [
    ('all', ['SandBot', 'OtherBot']),
    ('online', ['SandBot']),
    ('offline', ['OtherBot']),
])
def test_list_command_keeps_status_filtering(env, bot, status, expected_names):
    other = Bot(env.server, 'OtherBot', [], 'minecraft:the_nether', [0, 70, 0], [0, 0])
    env.manager.add_bot(other)
    bot.is_online = True

    command.list_bots(env.source, env.manager, status)

    expected_bots = [env.manager.get_bot(name) for name in expected_names]
    assert env.source.messages == [view.render_bot_list(expected_bots, status=status).to_plain_text()]


@pytest.mark.parametrize('online', [False, True])
def test_rendering_does_not_change_bot_state_or_saved_data(env, bot, online):
    bot.is_online = online
    before = bot.to_dict()
    settings = config.to_dict()
    generation = env.manager.generation
    paths = [Path(config.config_path), Path(config.bots_path)]
    files = [path.read_bytes() for path in paths]

    view.render_help()
    view.render_bot_actions(bot)
    view.render_bot_info(bot, can_manage=True)
    view.render_alias_panel(bot)
    view.render_bot_summary(bot)
    view.render_bot_list([bot])
    env.source.permission = 0
    command.bot_action(env.source, {'nickname': 'farm'}, 'info', env.manager)

    assert bot.to_dict() == before
    assert bot.is_online is online
    assert config.to_dict() == settings
    assert env.manager.generation == generation
    assert [path.read_bytes() for path in paths] == files
    assert env.server.commands == []
    assert env.source.messages == [view.render_bot_info(bot, can_operate=False).to_plain_text()]


@pytest.mark.parametrize('online', [False, True])
@pytest.mark.parametrize('method, renderer', [
    ('_get_command_rtext', view.render_bot_actions),
    ('get_info_rtext', view.render_bot_info),
    ('get_simple_rtext', view.render_bot_summary),
])
def test_bot_render_methods_remain_compatible(env, bot, online, method, renderer):
    bot.is_online = online
    assert getattr(bot, method)().to_json_str() == renderer(bot).to_json_str()


@pytest.mark.parametrize('online', [False, True])
@pytest.mark.parametrize('confirmed', [False, True])
@pytest.mark.parametrize('renderer', [view.render_bot_info, view.render_bot_summary])
def test_player_name_shows_confirmation_only_while_unknown(env, online, confirmed, renderer):
    config.bot_name_prefix = 'b_'
    bot = Bot(env.server, 'SandBot', ['farm'], 'minecraft:overworld', [0, 64, 0], [0, 0])
    bot.is_online = online
    if confirmed:
        assert bot.confirm_name('b_SandBot')
    before = bot.to_dict()
    message = renderer(bot)
    text = json.dumps(json.loads(message.to_json_str()), ensure_ascii=False)

    assert '\u5047\u4eba\u540d:' in text
    assert ('b_SandBot' if confirmed else 'b_sandbot') in text
    assert ('\u5f85\u786e\u8ba4' in text) is not confirmed
    assert '\u4e0a\u6b21\u786e\u8ba4' not in text
    assert '\u5df2\u786e\u8ba4' not in text
    assert '\u57fa\u7840\u540d' not in text
    assert '\u6e38\u620f\u540d' not in text
    assert all(value in ('!!bk SandBot', '!!bk list') or value.startswith('!!bk SandBot ')
               for value in _click_commands(message) if value.startswith('!!bk'))
    assert bot.to_dict() == before


@pytest.mark.parametrize('online', [False, True])
@pytest.mark.parametrize('renderer', [
    view.render_bot_actions, view.render_bot_info, view.render_bot_summary, view.render_alias_panel,
])
def test_panel_text_has_explicit_colors_including_hover_text(env, bot, online, renderer):
    bot.is_online = online
    nodes = list(_json_nodes(json.loads(renderer(bot).to_json_str())))
    text_nodes = [node for node in nodes if node.get('text', '').strip()]
    assert text_nodes
    assert all('color' in node for node in text_nodes)
    assert all('\u00a7' not in node['text'] for node in text_nodes)


def test_management_controls_have_semantic_colors_and_no_formatting_codes(env, bot):
    message = view.render_bot_info(bot, can_manage=True)
    nodes = list(_json_nodes(json.loads(message.to_json_str())))
    buttons = {node['text']: node for node in nodes if 'clickEvent' in node}

    assert buttons['[\u6dfb\u52a0\u522b\u540d]']['color'] == 'green'
    assert buttons['[\u79fb\u9664\u522b\u540d]']['color'] == 'aqua'
    assert buttons['[\u5220\u9664\u8bb0\u5f55]']['color'] == 'red'
    assert all('\u00a7' not in node.get('text', '') for node in nodes)
    assert all('\u00a7' not in value for value in _click_commands(message))


@pytest.mark.parametrize('aliases, title', [
    (['SANDBOT', 'b_SANDBOT', '\u5237\u6c99\u673a', 'farm'], '\u5237\u6c99\u673a'),
    (['SANDBOT', 'b_SANDBOT'], 'SandBot'),
    ([], 'SandBot'),
])
def test_details_title_uses_first_custom_alias_without_reordering(env, aliases, title):
    config.bot_name_prefix = 'b_'
    bot = Bot(env.server, 'SandBot', aliases, 'minecraft:overworld', [0, 64, 0], [0, 0])
    before = bot.to_dict()

    assert view.render_bot_info(bot).to_plain_text().splitlines()[0] == f'----- {title} \u00b7 \u79bb\u7ebf -----'
    assert bot.to_dict() == before


@pytest.mark.parametrize('dimension, label', [
    ('minecraft:overworld', '\u4e3b\u4e16\u754c'),
    ('minecraft:the_nether', '\u4e0b\u754c'),
    ('minecraft:the_end', '\u672b\u5730'),
    ('example:custom/room', 'example:custom/room'),
])
def test_position_display_keeps_full_precision_in_data_hover_and_coordinate_links(env, dimension, label):
    bot = Bot(env.server, 'SandBot', [], dimension, [12.3456789, 64.0001, -0.0049], [-0.00001, 91.99999])
    before = bot.to_dict()
    message = view.render_bot_info(bot)
    text = message.to_plain_text()
    serialized = message.to_json_str()

    assert f'\u767b\u8bb0\u4f4d\u7f6e: {label} (12.35, 64, 0)' in text
    assert '\u767b\u8bb0\u671d\u5411: 0 / 92' in text
    assert '-0' not in text
    assert str(bot.position) in serialized
    assert str(bot.facing) in serialized
    assert dimension in serialized
    assert _click_commands(message)[0] == f'[x:12, y:64, z:-1, name:SandBot, dim:{dimension}]'
    assert bot.to_dict() == before


@pytest.mark.parametrize('online', [False, True])
def test_action_hover_warns_about_auto_spawn_and_record_only_deletion(env, bot, online):
    bot.is_online = online
    message = view.render_bot_info(bot, can_manage=True)
    nodes = _json_nodes(json.loads(message.to_json_str()))
    buttons = {node['clickEvent']['value']: node for node in nodes if 'clickEvent' in node}

    for action in ['where', 'use', 'huse ', 'atk', 'hatk ']:
        hover = json.dumps(buttons[f'!!bk SandBot {action}']['hoverEvent'], ensure_ascii=False)
        assert '\u79bb\u7ebf\u65f6\u4f1a\u5148\u81ea\u52a8\u53ec\u5524' in hover
        assert 'yellow' in hover
    delete_hover = json.dumps(buttons['!!bk del SandBot']['hoverEvent'], ensure_ascii=False)
    assert '\u4e0d\u4f1a\u8ba9\u5728\u7ebf\u5047\u4eba\u4e0b\u7ebf' in delete_hover
    where_hover = json.dumps(buttons['!!bk SandBot where']['hoverEvent'], ensure_ascii=False)
    assert '\u4e0d\u662f\u5b9e\u65f6\u4f4d\u7f6e' in where_hover


@pytest.mark.parametrize('can_operate', [False, True])
@pytest.mark.parametrize('can_manage', [False, True])
@pytest.mark.parametrize('prefix', ['!!bk', '!!farm'])
def test_details_control_and_management_permissions_are_independent(env, bot, can_operate, can_manage, prefix):
    config.prefix_short = prefix
    message = view.render_bot_info(bot, can_operate=can_operate, can_manage=can_manage)
    commands = _click_commands(message)
    assert (f'{prefix} SandBot spawn' in commands) is can_operate
    assert (f'{prefix} SandBot use' in commands) is can_operate
    assert (f'{prefix} SandBot alias add ' in commands) is can_manage
    assert (f'{prefix} SandBot alias' in commands) is can_manage
    assert (f'{prefix} del SandBot' in commands) is can_manage
    assert f'{prefix} SandBot' in commands
    assert f'{prefix} list' in commands
    assert ('\u7ba1\u7406:' in message.to_plain_text()) is can_manage


@pytest.mark.parametrize('permission', range(5))
@pytest.mark.parametrize('operate_level, manage_level', [(1, 3), (4, 1), (0, 4)])
def test_command_views_use_current_source_permissions(env, bot, monkeypatch, permission, operate_level, manage_level):
    env.source.permission = permission
    config.permission = {'bot': operate_level, 'list': manage_level}
    messages = []
    monkeypatch.setattr(env.source, 'reply', messages.append)

    command.bot_action(env.source, {'nickname': 'farm'}, 'info', env.manager)
    assert messages[-1].to_json_str() == view.render_bot_info(
        bot, can_operate=permission >= operate_level, can_manage=permission >= manage_level).to_json_str()

    command.list_bots(env.source, env.manager)
    assert messages[-1].to_json_str() == view.render_bot_list(
        [bot], can_operate=permission >= operate_level).to_json_str()
    assert '!!bk SandBot alias' not in _click_commands(messages[-1])
    assert env.server.commands == []


@pytest.mark.parametrize('prefix', ['!!bk', '!!farm'])
def test_alias_picker_only_removes_custom_aliases_with_exact_names(env, prefix):
    config.prefix_short = prefix
    config.bot_name_prefix = 'b_'
    bot = Bot(env.server, 'SandBot', ['SANDBOT', 'b_SANDBOT', '\u5237\u6c99\u673a', 'Farm'],
              'minecraft:overworld', [0, 64, 0], [0, 0], confirmed_name='b_SandBot')
    message = view.render_alias_panel(bot)
    assert _click_commands(message) == [
        f'{prefix} SandBot alias del \u5237\u6c99\u673a',
        f'{prefix} SandBot alias del Farm',
        f'{prefix} SandBot alias add ',
        f'{prefix} SandBot',
    ]
    nodes = _json_nodes(json.loads(message.to_json_str()))
    removals = [node for node in nodes if node.get('text') == '[\u79fb\u9664]']
    assert len(removals) == 2
    assert all(node['color'] == 'red' for node in removals)


def test_empty_aliases_are_explained_and_remove_control_is_not_clickable(env):
    bot = Bot(env.server, 'SandBot', ['SANDBOT'], 'minecraft:overworld', [0, 64, 0], [0, 0])
    message = view.render_bot_info(bot, can_manage=True)
    assert '\u65e0\u81ea\u5b9a\u4e49\u522b\u540d' in message.to_plain_text()
    assert '!!bk SandBot alias' not in _click_commands(message)
    nodes = _json_nodes(json.loads(message.to_json_str()))
    remove = next(node for node in nodes if node.get('text') == '[\u79fb\u9664\u522b\u540d]')
    assert remove['color'] == 'gray'
    assert 'clickEvent' not in remove

    picker = view.render_alias_panel(bot)
    assert '\u65e0\u81ea\u5b9a\u4e49\u522b\u540d' in picker.to_plain_text()
    assert _click_commands(picker) == ['!!bk SandBot alias add ', '!!bk SandBot']
