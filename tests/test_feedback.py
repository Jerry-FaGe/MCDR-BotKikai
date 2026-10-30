import json
from pathlib import Path

import pytest

from bot_kikai import command, view
from bot_kikai.bot import Bot
from bot_kikai.config import config


def _nodes(value, *, visible=False):
    if isinstance(value, dict):
        yield value
        children = [value.get('extra', [])] if visible else value.values()
        for child in children:
            yield from _nodes(child, visible=visible)
    elif isinstance(value, list):
        for child in value:
            yield from _nodes(child, visible=visible)


def _visible(message):
    return [node for node in _nodes(json.loads(message.to_json_str()), visible=True) if node.get('text')]


def _commands(message):
    events = [node['clickEvent'] for node in _nodes(json.loads(message.to_json_str())) if 'clickEvent' in node]
    assert all(event['action'] == 'suggest_command' for event in events)
    return [event['value'] for event in events]


def _assert_rich_feedback(message):
    assert message.to_plain_text().startswith('[BK] ')
    assert '\n' not in message.to_plain_text()
    for node in _nodes(json.loads(message.to_json_str())):
        if node.get('text', '').strip():
            assert 'color' in node
            assert '\u00a7' not in node['text']
    _commands(message)


@pytest.mark.parametrize('prefix', ['!!bk', '!!farm'])
@pytest.mark.parametrize('confirmed', [False, True])
@pytest.mark.parametrize('aliases, label', [
    (['SANDBOT', 'b_SANDBOT', '\u5237\u6c99\u673a', '\u6c99\u573a'], '\u5237\u6c99\u673a'),
    (['SANDBOT', 'b_SANDBOT'], 'SandBot'),
    ([], 'SandBot'),
    (['long-machine-name', 'other'], 'long-machine-name'),
])
def test_feedback_uses_full_first_custom_alias_and_registered_name_link(env, prefix, confirmed, aliases, label):
    config.prefix_short = prefix
    config.bot_name_prefix = 'b_'
    bot = Bot(env.server, 'SandBot', aliases, 'minecraft:overworld', [0, 64, 0], [0, 0],
              confirmed_name='b_SandBot' if confirmed else None)
    before = bot.to_dict()
    message = view.render_feedback('sent', bot=bot, kind='request')

    assert message.to_plain_text() == f'[BK] {label} \u00b7 sent'
    name = next(node for node in _visible(message) if node.get('color') == 'gold')
    hover = json.dumps(name['hoverEvent'], ensure_ascii=False)
    assert label in hover
    assert 'SandBot' in hover
    assert ('b_SandBot' if confirmed else 'b_sandbot') in hover
    assert ('\u5f85\u786e\u8ba4' in hover) is not confirmed
    assert '\u767b\u8bb0\u540d:' in hover and '\u5047\u4eba\u540d:' in hover
    assert all(alias in hover for alias in view._custom_aliases(bot))
    assert _commands(message) == [f'{prefix} SandBot']
    assert bot.to_dict() == before
    assert env.server.commands == []
    _assert_rich_feedback(message)


@pytest.mark.parametrize('kind, color', [
    ('success', 'green'), ('request', 'white'), ('info', 'gray'), ('error', 'red'),
])
def test_feedback_colors_distinguish_confirmed_requests_no_ops_and_errors(env, bot, kind, color):
    message = view.render_feedback('result', bot=bot, kind=kind)
    assert next(node for node in _visible(message) if node['text'] == 'result')['color'] == color
    _assert_rich_feedback(message)


def test_feedback_keeps_multiline_causes_visible_and_full_text_in_hover():
    cause = 'save failed:\n  disk full\tplease retry'
    message = view.render_feedback(cause, kind='error', details='diagnostic context')
    assert message.to_plain_text() == '[BK] save failed: disk full please retry'
    body = _visible(message)[-1]
    hover = json.dumps(body['hoverEvent'])
    assert json.dumps(cause)[1:-1] in hover
    assert 'diagnostic context' in hover
    assert _commands(message) == []
    _assert_rich_feedback(message)


def test_feedback_rejects_unknown_status_kind():
    with pytest.raises(ValueError):
        view.render_feedback('result', kind='unknown')


def test_feedback_does_not_collapse_spaces_inside_error_paths():
    cause = 'save failed:\nC:/my  world/bots.json\npermission denied'
    message = view.render_feedback(cause, kind='error')
    assert message.to_plain_text() == '[BK] save failed: C:/my  world/bots.json permission denied'
    _assert_rich_feedback(message)


_ACTION_CASES = [
    ('spawn', 0, '\u5df2\u786e\u8ba4\u4e0a\u7ebf', None),
    ('kill', 0, '\u4e0b\u7ebf\u8bf7\u6c42\u5df2\u53d1\u9001', 'player sandbot kill'),
    ('use', 0, '\u53f3\u952e\u8bf7\u6c42\u5df2\u53d1\u9001', 'player sandbot use once'),
    ('huse', 0, '\u6301\u7eed\u53f3\u952e\u8bf7\u6c42\u5df2\u53d1\u9001', 'player sandbot use continuous'),
    ('huse', 10, '\u6bcf 10 gt \u53f3\u952e\u8bf7\u6c42\u5df2\u53d1\u9001', 'player sandbot use interval 10'),
    ('atk', 0, '\u5de6\u952e\u8bf7\u6c42\u5df2\u53d1\u9001', 'player sandbot attack once'),
    ('hatk', 0, '\u6301\u7eed\u5de6\u952e\u8bf7\u6c42\u5df2\u53d1\u9001', 'player sandbot attack continuous'),
    ('hatk', 10, '\u6bcf 10 gt \u5de6\u952e\u8bf7\u6c42\u5df2\u53d1\u9001', 'player sandbot attack interval 10'),
    ('stop', 0, '\u505c\u6b62\u52a8\u4f5c\u8bf7\u6c42\u5df2\u53d1\u9001', 'player sandbot stop'),
    ('where', 0, '\u53d1\u5149\u8bf7\u6c42\u5df2\u53d1\u9001\uff082 \u5206\u949f\uff09',
     'effect give sandbot glowing 120 0'),
]


@pytest.mark.parametrize('action, interval, label', [(a, i, text) for a, i, text, _ in _ACTION_CASES])
def test_action_feedback_is_read_only_and_does_not_claim_unacknowledged_success(env, bot, action, interval, label):
    message = view.render_action_feedback(bot, action, interval=interval)
    assert message.to_plain_text().startswith(f'[BK] farm \u00b7 {label}')
    body = next(node for node in _visible(message) if node['text'] == label)
    assert body['color'] == ('green' if action == 'spawn' else 'white')
    if action != 'spawn':
        assert '\u8bf7\u6c42\u5df2\u53d1\u9001' in label
        assert '\u5b9e\u9645\u52a8\u4f5c' in json.dumps(body['hoverEvent'], ensure_ascii=False)
    assert env.server.commands == []
    _assert_rich_feedback(message)


@pytest.mark.parametrize('dimension, label', [
    ('minecraft:overworld', '\u4e3b\u4e16\u754c'),
    ('minecraft:the_nether', '\u4e0b\u754c'),
    ('minecraft:the_end', '\u672b\u5730'),
    ('example:custom/room', 'example:custom/room'),
])
def test_where_feedback_keeps_dimension_record_coordinates_and_safe_coordinate_link(env, dimension, label):
    bot = Bot(env.server, 'SandBot', ['farm'], dimension, [12.3456789, 64.0001, -0.0049], [180, 0])
    before = bot.to_dict()
    message = view.render_action_feedback(bot, 'where')
    assert f'\u767b\u8bb0\u4f4d\u7f6e: {label} (12, 64, -1)' in message.to_plain_text()
    assert str(bot.position) in message.to_json_str()
    assert '\u4e0d\u662f\u5b9e\u65f6\u4f4d\u7f6e' in message.to_json_str()
    assert _commands(message) == [
        '!!bk SandBot', f'[x:12, y:64, z:-1, name:SandBot, dim:{dimension}]',
    ]
    assert bot.to_dict() == before
    assert env.server.commands == []
    _assert_rich_feedback(message)


@pytest.mark.parametrize('target', ['SandBot', 'farm', '\u5237\u6c99\u673a'])
@pytest.mark.parametrize('action, interval, label, server_command', _ACTION_CASES)
def test_action_commands_reply_once_with_primary_alias_and_preserve_execution(
        env, bot, monkeypatch, target, action, interval, label, server_command):
    bot.is_online = True
    messages = []
    monkeypatch.setattr(env.source, 'reply', messages.append)
    context = {'nickname': target, 'use_interval': interval, 'atk_interval': interval}
    task = command.bot_action(env.source, context, action, env.manager)
    task.result(timeout=2)

    assert len(messages) == 1
    assert messages[0].to_plain_text().startswith(f'[BK] farm \u00b7 {label}')
    assert _commands(messages[0])[0] == '!!bk SandBot'
    assert env.server.commands == ([server_command] if server_command else [])
    assert bot.is_online
    _assert_rich_feedback(messages[0])


@pytest.mark.parametrize('known_cause', [False, True])
def test_action_failures_keep_known_causes_but_do_not_guess_unknown_ones(env, bot, monkeypatch, known_cause):
    def fail(**kwargs):
        if known_cause:
            raise RuntimeError('specific server error\ncheck the log')
        return False

    messages = []
    monkeypatch.setattr(bot, 'use', fail)
    monkeypatch.setattr(env.source, 'reply', messages.append)
    command.bot_action(env.source, {'nickname': 'farm'}, 'use', env.manager).result(timeout=2)
    assert len(messages) == 1
    message = messages[0]
    body = _visible(message)[-1]
    assert body['color'] == 'red'
    assert '\u5df2\u53d1\u9001' not in message.to_plain_text()
    if known_cause:
        assert 'specific server error check the log' in message.to_plain_text()
    else:
        assert '\u64cd\u4f5c\u672a\u5b8c\u6210' in message.to_plain_text()
        assert '\u8d85\u65f6' not in message.to_plain_text()
        assert '\u53d6\u6d88' not in message.to_plain_text()
        assert 'Carpet' in message.to_json_str()
    assert env.server.commands == []
    _assert_rich_feedback(message)


@pytest.mark.parametrize('aliases, target, alias, remove, label', [
    ([], 'SandBot', 'first', False, 'first'),
    (['first'], 'first', 'second', False, 'first'),
    (['first', 'second'], 'first', 'first', True, 'second'),
    (['first'], 'first', 'first', True, 'SandBot'),
])
def test_alias_feedback_uses_post_edit_name_and_survives_removing_the_invoking_alias(
        env, monkeypatch, aliases, target, alias, remove, label):
    bot = Bot(env.server, 'SandBot', aliases, 'minecraft:overworld', [0, 64, 0], [0, 0])
    env.manager.add_bot(bot)
    env.server.running = False
    messages = []
    monkeypatch.setattr(env.source, 'reply', messages.append)
    command.edit_alias(env.source, {'nickname': target, 'alias': alias}, env.manager, remove=remove)
    assert len(messages) == 1
    message = messages[0]
    verb = '\u79fb\u9664' if remove else '\u6dfb\u52a0'
    assert message.to_plain_text() == f'[BK] {label} \u00b7 \u5df2{verb}\u522b\u540d\u300c{alias}\u300d'
    assert _commands(message) == ['!!bk SandBot']
    assert _visible(message)[-1]['color'] == 'green'
    assert env.manager.get_bot('SandBot') is bot
    assert env.server.commands == []
    _assert_rich_feedback(message)


@pytest.mark.parametrize('remove, alias', [(False, 'FARM'), (True, 'missing')])
def test_no_op_alias_feedback_is_neutral_and_does_not_write(env, bot, monkeypatch, remove, alias):
    before = Path(config.bots_path).read_bytes()
    messages = []
    monkeypatch.setattr(env.source, 'reply', messages.append)
    command.edit_alias(env.source, {'nickname': 'farm', 'alias': alias}, env.manager, remove=remove)
    assert len(messages) == 1
    assert _visible(messages[0])[-1]['color'] == 'gray'
    assert Path(config.bots_path).read_bytes() == before
    assert env.server.commands == []
    _assert_rich_feedback(messages[0])


def test_alias_feedback_cannot_be_attributed_to_a_rebound_invoking_alias(env, bot, monkeypatch):
    other = Bot(env.server, 'OtherBot', ['other'], 'minecraft:overworld', [0, 64, 0], [0, 0])
    env.manager.add_bot(other)
    add_alias = env.manager.add_alias

    def rebind_then_edit(target, alias):
        assert target == 'SandBot'
        assert env.manager.remove_alias('SandBot', 'farm')
        assert add_alias('OtherBot', 'farm')
        return add_alias(target, alias)

    messages = []
    monkeypatch.setattr(env.manager, 'add_alias', rebind_then_edit)
    monkeypatch.setattr(env.source, 'reply', messages.append)
    command.edit_alias(env.source, {'nickname': 'farm', 'alias': 'new'}, env.manager)
    assert env.manager.get_bot_by_nickname('new') is bot
    assert env.manager.get_bot_by_nickname('farm') is other
    assert messages[0].to_plain_text().startswith('[BK] \u5237\u6c99\u673a \u00b7 ')
    assert _commands(messages[0]) == ['!!bk SandBot']
    assert env.server.commands == []


def test_deleted_record_feedback_keeps_identity_but_has_no_dead_details_link(env, bot, monkeypatch):
    bot.is_online = True
    messages = []
    monkeypatch.setattr(env.source, 'reply', messages.append)
    command.del_bot(env.source, {'nickname': '\u5237\u6c99\u673a'}, env.manager)
    assert len(messages) == 1
    message = messages[0]
    assert message.to_plain_text() == '[BK] farm \u00b7 \u5df2\u5220\u9664\u8bb0\u5f55'
    assert 'SandBot' in message.to_json_str()
    assert '\u4e0d\u4f1a\u8ba9\u5047\u4eba\u4e0b\u7ebf' in message.to_json_str()
    assert _commands(message) == []
    assert env.manager.get_bot('SandBot') is None
    assert env.server.commands == []
    _assert_rich_feedback(message)


def test_add_update_and_reload_feedback_use_the_same_compact_style(env, monkeypatch):
    messages = []
    monkeypatch.setattr(env.source, 'reply', messages.append)
    context = {'name': 'SandBot', 'nickname': 'first', 'dim': 'overworld',
               'pos_x': 1, 'pos_y': 64, 'pos_z': 2, 'facing_y': 180, 'facing_p': 0}
    command.add_bot_full(env.source, context, env.manager)
    assert messages[-1].to_plain_text() == '[BK] first \u00b7 \u5df2\u6dfb\u52a0\u8bb0\u5f55'
    context['nickname'] = 'second'
    command.add_bot_full(env.source, context, env.manager)
    assert messages[-1].to_plain_text() == '[BK] first \u00b7 \u5df2\u66f4\u65b0\u8bb0\u5f55'
    assert _commands(messages[-1]) == ['!!bk SandBot']
    command.reload_plugin(env.source, env.manager)
    assert messages[-1].to_plain_text() == '[BK] \u914d\u7f6e\u5df2\u91cd\u8f7d'
    assert _commands(messages[-1]) == []
    assert len(messages) == 3
    assert env.server.commands == []
    for message in messages:
        _assert_rich_feedback(message)


@pytest.mark.parametrize('case', ['permission', 'missing', 'list', 'player_only', 'queue'])
def test_command_precondition_errors_use_rich_feedback_without_actions(env, bot, monkeypatch, case):
    messages = []
    monkeypatch.setattr(env.source, 'reply', messages.append)
    if case == 'permission':
        env.source.permission = 0
        command.bot_action(env.source, {'nickname': 'farm'}, 'use', env.manager)
    elif case == 'missing':
        command.bot_action(env.source, {'nickname': 'missing'}, 'info', env.manager)
    elif case == 'list':
        command.list_bots(env.source, env.manager, page=0)
    elif case == 'player_only':
        command.add_bot_simple(env.source, {'name': 'NewBot', 'nickname': 'new'}, env.manager)
    else:
        def full(*args):
            raise RuntimeError('queue is full')

        monkeypatch.setattr(env.manager, 'submit', full)
        command.bot_action(env.source, {'nickname': 'farm'}, 'use', env.manager)
    assert len(messages) == 1
    assert _visible(messages[0])[-1]['color'] == 'red'
    assert _commands(messages[0]) == []
    assert env.server.commands == []
    _assert_rich_feedback(messages[0])
