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
    assert _click_commands(view.render_bot_summary(bot)) == expected
    assert _click_commands(view.render_bot_info(bot)) == [
        '[x:1, y:64, z:-3, name:SandBot, dim:minecraft:overworld]',
        *expected,
    ]

    status = '\u00a7a\u5728\u7ebf' if online else '\u00a74\u79bb\u7ebf'
    for renderer in (view.render_bot_info, view.render_bot_summary):
        assert status in renderer(bot).to_plain_text()


@pytest.mark.parametrize('renderer', [view.render_bot_info, view.render_bot_summary])
def test_panels_hide_identity_aliases_and_preserve_nickname_order(env, renderer):
    config.bot_name_prefix = 'b_'
    bot = Bot(env.server, 'SandBot',
              ['SANDBOT', 'b_SANDBOT', 'farm', '\u5237\u6c99\u673a'],
              'minecraft:overworld', [1.5, 64, -2.5], [180, 0])
    nicknames = bot.nicknames.copy()
    text = renderer(bot).to_plain_text()
    aliases = next(line for line in text.splitlines() if '\u7528\u4e8e:' in line)

    assert 'farm, \u5237\u6c99\u673a' in aliases
    assert 'SANDBOT' not in aliases
    assert 'b_sandbot' not in aliases.lower()
    assert bot.nicknames == nicknames


def test_help_reads_current_prefix_and_preserves_templates(env):
    original = view.render_help()
    config.prefix_short = '!!farm'
    current = view.render_help()
    templates = [
        '', ' list [online|offline]', ' reload',
        ' add <name> <kikai>', ' add <name> <kikai> <dim> <pos> <facing>',
        ' del <kikai>', ' <kikai>', ' <kikai> spawn', ' <kikai> kill',
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


def test_list_preserves_input_order_and_separators(env, bot):
    other = Bot(env.server, 'OtherBot', [], 'minecraft:the_nether', [0, 70, 0], [0, 0])
    bots = [other, bot]
    result = view.render_bot_list(bots)

    assert result.to_plain_text() == (
        view.render_bot_summary(other).to_plain_text() + '\n'
        + view.render_bot_summary(bot).to_plain_text() + '\n'
    )
    assert bots == [other, bot]


def test_empty_list_keeps_existing_reply(env):
    expected = '\u00a7b[BotKikai] \u00a77\u6ca1\u6709\u627e\u5230\u7b26\u5408\u6761\u4ef6\u7684\u5047\u4eba'
    assert view.render_bot_list([]) == expected
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
    assert env.source.messages == [view.render_bot_list(expected_bots).to_plain_text()]


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
    view.render_bot_info(bot)
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
    assert env.source.messages == [view.render_bot_info(bot).to_plain_text()]


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
    assert all(command.startswith('!!bk SandBot ') for command in _click_commands(message)
               if command.startswith('!!bk'))
    assert bot.to_dict() == before
