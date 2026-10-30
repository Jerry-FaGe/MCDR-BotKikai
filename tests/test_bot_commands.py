import json
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from mcdreforged.api.command import CommandError

import bot_kikai
from bot_kikai import command, utils
from bot_kikai.bot import Bot
from bot_kikai.config import config
from bot_kikai.storage import write_json


def run_command(root, source, text):
    executions = root._entry_execute(source, text)
    # MCDR 2.12 executes callbacks inline; 2.16.2 returns scheduled callbacks.
    if executions is not None:
        from mcdreforged.command.builder.callback import DirectCallbackInvoker
        for execution in executions:
            execution.scheduled_callback.invoke(DirectCallbackInvoker())


def test_command_tree_add_list_delete(env):
    command.register_command_tree(env.server, env.manager)
    root = env.server.roots[0]
    run_command(root, env.source, '!!bk add NewBot new minecraft:overworld 1 64 2 90 0')
    assert env.manager.get_bot('NewBot') is not None
    run_command(root, env.source, '!!bk list')
    assert '[\u79bb\u7ebf] new ' in env.source.messages[-1]
    run_command(root, env.source, '!!bk del new')
    assert env.manager.get_bot('NewBot') is None


@pytest.mark.parametrize('action', ['huse', 'hatk'])
@pytest.mark.parametrize('interval', ['0', '-1'])
def test_command_tree_rejects_nonpositive_intervals(env, bot, action, interval):
    command.register_command_tree(env.server, env.manager)
    with pytest.raises(CommandError):
        run_command(env.server.roots[0], env.source, f'!!bk farm {action} {interval}')
    assert not env.server.commands


def test_spawn_timeout_does_not_send_followup_action(env, bot):
    config.spawn_max_wait_time = 0.03
    config.spawn_check_interval = 0.2
    start = time.monotonic()
    assert not bot.use()
    assert time.monotonic() - start < 1
    assert len(env.server.commands) == 1
    assert ' spawn at ' in env.server.commands[0]


def test_player_join_wakes_spawn_and_allows_action(env, bot):
    spawn_requested = threading.Event()
    env.server.on_execute = lambda text: spawn_requested.set()
    task = env.manager.submit(bot.use)
    try:
        assert spawn_requested.wait(2)
        env.manager.update_player_status(bot.real_name, True)
        assert task.result(timeout=2)
    finally:
        bot.cancel()
    assert env.server.commands[-1] == 'player sandbot use once'


def test_concurrent_actions_spawn_only_once(env, bot):
    spawn_requested = threading.Event()
    env.server.on_execute = lambda text: spawn_requested.set()
    tasks = [env.manager.submit(bot.use) for _ in range(2)]
    try:
        assert spawn_requested.wait(2)
        env.manager.update_player_status(bot.real_name, True)
        assert all(task.result(timeout=2) for task in tasks)
    finally:
        bot.cancel()
    assert sum(' spawn at ' in text for text in env.server.commands) == 1
    assert env.server.commands.count('player sandbot use once') == 2


@pytest.mark.parametrize('operation', ['reload', 'unload', 'delete', 'stop'])
def test_lifecycle_change_cancels_pending_actions(env, bot, operation):
    spawn_requested = threading.Event()
    env.server.on_execute = lambda text: spawn_requested.set()
    task = env.manager.submit(bot.use)
    try:
        assert spawn_requested.wait(2)
        if operation == 'reload':
            env.manager.reload_config()
        elif operation == 'unload':
            env.manager.shutdown()
        elif operation == 'delete':
            env.manager.remove_bot(bot.name)
        else:
            env.server.running = False
            env.manager.clear_all_online_status()
        assert not task.result(timeout=2)
    finally:
        bot.cancel()
    assert all(' use ' not in text for text in env.server.commands)


def test_bots_work_again_after_server_restart(env, bot):
    bot.is_online = True
    env.server.running = False
    env.manager.clear_all_online_status()
    current = env.manager.get_bot(bot.name)
    assert current is not bot
    assert not current.is_online
    assert not bot.stop()
    env.server.running = True
    env.server.on_execute = lambda text: env.manager.update_player_status(current.real_name, True)
    assert current.use()


def test_failed_action_does_not_reply_success(env, bot):
    config.spawn_max_wait_time = 0.01
    task = command.bot_action(env.source, {'nickname': 'farm'}, 'use', env.manager)
    task.result(timeout=2)
    assert '\u64cd\u4f5c\u672a\u5b8c\u6210' in env.source.messages[-1]
    assert '\u5df2\u53d1\u9001' not in env.source.messages[-1]
    assert all(' use ' not in text for text in env.server.commands)


def test_action_without_ack_only_reports_request_sent(env, bot):
    bot.is_online = True
    task = command.bot_action(env.source, {'nickname': 'farm'}, 'kill', env.manager)
    task.result(timeout=2)
    assert '\u5df2\u53d1\u9001' in env.source.messages[-1]
    assert bot.is_online


def test_kill_is_not_blocked_by_an_incomplete_online_cache(env, bot):
    assert not bot.is_online
    task = command.bot_action(env.source, {'nickname': 'farm'}, 'kill', env.manager)
    task.result(timeout=2)
    assert env.server.commands == ['player sandbot kill']


def test_guest_cannot_schedule_bot_actions(env, bot):
    env.source.permission = 0
    assert command.bot_action(env.source, {'nickname': 'farm'}, 'use', env.manager) is None
    assert not env.server.commands
    assert '\u6743\u9650' in env.source.messages[-1]


def test_prefix_change_requires_plugin_reload_without_partial_apply(env, bot):
    command.register_command_tree(env.server, env.manager)
    write_json(config.config_path, {'prefix_short': '!!farm', 'permission': {'bot': 3}})
    command.reload_plugin(env.source, env.manager)
    assert config.prefix_short == '!!bk'
    assert config.permission['bot'] == 1
    assert env.server.roots[0].literals == {'!!bk'}
    assert '!!MCDR plugin reload bot_kikai' in env.source.messages[-1]
    assert '!!farm' not in bot.get_info_rtext().to_json_str()


def test_initial_custom_prefix_matches_help_registration_and_buttons(env, bot):
    write_json(config.config_path, {'prefix_short': '!!farm'})
    bot_kikai.on_load(env.server, None)
    assert env.server.roots[-1].literals == {'!!farm'}
    assert env.server.help_messages[-1][0] == '!!farm'
    command.show_help(env.source)
    assert '!!farm' in env.source.messages[-1]
    assert '!!bk' not in env.source.messages[-1]
    assert '!!farm' in bot_kikai.bot_manager_instance.get_bot(bot.name).get_info_rtext().to_json_str()


def test_plugin_reload_preserves_online_names_after_unload(env, bot):
    bot.is_online = True
    previous = SimpleNamespace(bot_manager_instance=env.manager)
    env.manager.shutdown()
    bot_kikai.on_load(env.server, previous)
    assert bot_kikai.bot_manager_instance.get_bot(bot.name).is_online


def test_coordinates_use_suggest_instead_of_non_slash_run_command(env, bot):
    data = json.loads(bot.get_info_rtext().to_json_str())
    serialized = json.dumps(data)
    assert 'run_command' not in serialized
    assert 'suggest_command' in serialized
    assert 'z:-3' in serialized


def test_add_queries_one_consistent_player_snapshot(env, monkeypatch):
    queries = []

    def query(*args):
        queries.append(args)
        return {'Pos': [1, 64, 2], 'Dimension': 'minecraft:overworld', 'Rotation': [90, 0]}

    monkeypatch.setitem(sys.modules, 'minecraft_data_api', SimpleNamespace(get_player_info=query))
    task = command.add_bot_simple(env.player, {'name': 'NewBot', 'nickname': 'new'}, env.manager)
    task.result(timeout=2)
    assert queries == [('Tester',)]
    assert env.manager.get_bot('NewBot').position == [1, 64, 2]


def test_unload_during_player_query_cannot_write_data(env, monkeypatch):
    entered = threading.Event()
    release = threading.Event()

    def query(*args):
        entered.set()
        assert release.wait(3)
        return {'Pos': [1, 64, 2], 'Dimension': 'minecraft:overworld', 'Rotation': [0, 0]}

    monkeypatch.setitem(sys.modules, 'minecraft_data_api', SimpleNamespace(get_player_info=query))
    task = command.add_bot_simple(env.player, {'name': 'NewBot', 'nickname': 'new'}, env.manager)
    try:
        assert entered.wait(2)
        env.manager.shutdown()
    finally:
        release.set()
        task.result(timeout=3)
    assert json.loads(Path(config.bots_path).read_text(encoding='utf8')) == {}


@pytest.mark.parametrize('data', [None, [], {'Pos': [1, 2, 3]}])
def test_unavailable_or_incomplete_player_data_is_not_saved(env, monkeypatch, data):
    monkeypatch.setitem(sys.modules, 'minecraft_data_api', SimpleNamespace(get_player_info=lambda *args: data))
    task = command.add_bot_simple(env.player, {'name': 'NewBot', 'nickname': 'new'}, env.manager)
    task.result(timeout=2)
    assert not env.manager.bots
    assert '\u65e0\u6cd5' in env.player.messages[-1]


def test_get_pos_handles_api_failure(env, monkeypatch):
    def fail(*args):
        raise RuntimeError('query unavailable')

    monkeypatch.setitem(sys.modules, 'minecraft_data_api', SimpleNamespace(get_player_info=fail))
    assert utils.get_pos(env.server, 'Tester') == (None, None, None)


@pytest.mark.parametrize('source_name', ['source', 'player'])
@pytest.mark.parametrize('prefix', ['!!bk', '!!farm'])
def test_alias_commands_work_without_minecraft_queries_or_bot_actions(env, bot, monkeypatch, source_name, prefix):
    source = getattr(env, source_name)
    config.prefix_short = prefix
    env.server.running = False
    command.register_command_tree(env.server, env.manager)
    root = env.server.roots[0]

    def fail(*args):
        raise AssertionError('alias edits must not query Minecraft')

    monkeypatch.setattr(utils, 'get_pos', fail)
    monkeypatch.setattr(env.manager, 'request_sync', fail)
    run_command(root, source, f'{prefix} farm alias add \u6c99\u573a')
    assert env.manager.get_bot_by_nickname('\u6c99\u573a') is bot
    assert '\u5df2\u6dfb\u52a0\u522b\u540d' in source.messages[-1]
    run_command(root, source, f'{prefix} \u6c99\u573a alias del FARM')
    assert env.manager.get_bot_by_nickname('farm') is None
    assert bot.position == [1.5, 64, -2.5]
    assert not env.server.commands


@pytest.mark.parametrize('remove', [False, True])
@pytest.mark.parametrize('permission', [0, 1, 2])
def test_alias_commands_require_management_permission(env, bot, permission, remove):
    env.source.permission = permission
    command.register_command_tree(env.server, env.manager)
    operation = 'del' if remove else 'add'
    before = Path(config.bots_path).read_bytes()
    with pytest.raises(CommandError):
        run_command(env.server.roots[0], env.source, f'!!bk farm alias {operation} new')
    command.edit_alias(env.source, {'nickname': 'farm', 'alias': 'new'}, env.manager, remove=remove)
    assert '\u6743\u9650' in env.source.messages[-1]
    assert Path(config.bots_path).read_bytes() == before


def test_alias_command_permissions_follow_current_config(env, bot):
    env.source.permission = 2
    command.register_command_tree(env.server, env.manager)
    config.permission['list'] = 2
    run_command(env.server.roots[0], env.source, '!!bk farm alias add new')
    assert env.manager.get_bot_by_nickname('new') is bot
    config.permission['list'] = 3
    with pytest.raises(CommandError):
        run_command(env.server.roots[0], env.source, '!!bk farm alias del new')
    assert env.manager.get_bot_by_nickname('new') is bot


@pytest.mark.parametrize('arguments', ['alias add', 'alias del', 'alias add new extra'])
def test_incomplete_or_extra_alias_arguments_do_not_modify_data(env, bot, arguments):
    command.register_command_tree(env.server, env.manager)
    before = Path(config.bots_path).read_bytes()
    with pytest.raises(CommandError):
        run_command(env.server.roots[0], env.source, f'!!bk farm {arguments}')
    assert Path(config.bots_path).read_bytes() == before


def test_alias_command_replies_distinguish_no_ops_and_errors(env, bot):
    command.register_command_tree(env.server, env.manager)
    root = env.server.roots[0]
    before = Path(config.bots_path).read_bytes()
    run_command(root, env.source, '!!bk farm alias add FARM')
    assert '\u65e0\u9700\u91cd\u590d\u6dfb\u52a0' in env.source.messages[-1]
    run_command(root, env.source, '!!bk farm alias del missing')
    assert '\u672a\u4f5c\u4fee\u6539' in env.source.messages[-1]
    run_command(root, env.source, '!!bk farm alias del SandBot')
    assert '\u522b\u540d\u4fee\u6539\u5931\u8d25' in env.source.messages[-1]
    run_command(root, env.source, '!!bk missing alias add new')
    assert '\u672a\u67e5\u8be2\u5230' in env.source.messages[-1]
    run_command(root, env.source, '!!bk farm alias add list')
    assert '\u51b2\u7a81' in env.source.messages[-1]
    assert Path(config.bots_path).read_bytes() == before


def test_alias_commands_do_not_reserve_a_new_top_level_name(env):
    env.manager.upsert_bot('alias', 'farm', 'minecraft:overworld', [0, 64, 0], [0, 0])
    command.register_command_tree(env.server, env.manager)
    root = env.server.roots[0]
    run_command(root, env.source, '!!bk alias')
    assert 'alias' in env.source.messages[-1]
    run_command(root, env.source, '!!bk alias alias add new')
    assert env.manager.get_bot_by_nickname('new') is env.manager.get_bot('alias')
    run_command(root, env.source, '!!bk alias alias del new')
    assert env.manager.get_bot_by_nickname('new') is None


def test_failed_alias_save_does_not_reply_success(env, bot, monkeypatch):
    import bot_kikai.bot_manager as manager_module

    def fail(*args):
        raise OSError('disk full')

    monkeypatch.setattr(manager_module, 'write_json', fail)
    command.register_command_tree(env.server, env.manager)
    run_command(env.server.roots[0], env.source, '!!bk farm alias add new')
    assert 'disk full' in env.source.messages[-1]
    assert '\u522b\u540d\u4fee\u6539\u5931\u8d25' in env.source.messages[-1]
    assert '\u5df2\u6dfb\u52a0\u522b\u540d' not in env.source.messages[-1]
    assert env.manager.get_bot_by_nickname('new') is None


@pytest.mark.parametrize('source_name', ['source', 'player'])
@pytest.mark.parametrize('prefix', ['!!bk', '!!farm'])
def test_alias_panel_is_read_only_and_works_with_server_stopped(env, bot, monkeypatch, source_name, prefix):
    config.prefix_short = prefix
    env.server.running = False
    source = getattr(env, source_name)
    command.register_command_tree(env.server, env.manager)
    before = {path: path.read_bytes() for path in env.path.iterdir()}
    saved_bot = bot.to_dict()
    generation = env.manager.generation

    def fail(*args, **kwargs):
        raise AssertionError('rendering must not schedule actions or query Minecraft')

    monkeypatch.setattr(env.manager, 'submit', fail)
    monkeypatch.setattr(utils, 'get_pos', fail)
    monkeypatch.setattr(env.manager, 'request_sync', fail)
    run_command(env.server.roots[0], source, f'{prefix} farm alias')

    assert '\u522b\u540d\u7ba1\u7406' in source.messages[-1]
    assert '[\u79fb\u9664]' in source.messages[-1]
    assert env.manager.generation == generation
    assert env.manager.get_bot('SandBot') is bot
    assert bot.to_dict() == saved_bot
    assert {path: path.read_bytes() for path in env.path.iterdir()} == before
    assert env.server.commands == []


@pytest.mark.parametrize('permission', [0, 1, 2])
def test_alias_panel_requires_permission_in_tree_and_callback(env, bot, permission):
    env.source.permission = permission
    command.register_command_tree(env.server, env.manager)
    before = Path(config.bots_path).read_bytes()
    with pytest.raises(CommandError):
        run_command(env.server.roots[0], env.source, '!!bk farm alias')
    command.bot_action(env.source, {'nickname': 'farm'}, 'alias', env.manager)
    assert '\u6743\u9650\u4e0d\u8db3' in env.source.messages[-1]
    assert Path(config.bots_path).read_bytes() == before


def test_alias_panel_handles_missing_record_and_changed_permission(env, bot):
    command.register_command_tree(env.server, env.manager)
    root = env.server.roots[0]
    run_command(root, env.source, '!!bk missing alias')
    assert '\u672a\u627e\u5230\u5047\u4eba' in env.source.messages[-1]

    env.source.permission = 2
    config.permission['list'] = 2
    run_command(root, env.source, '!!bk farm alias')
    assert '\u522b\u540d\u7ba1\u7406' in env.source.messages[-1]
    config.permission['list'] = 3
    with pytest.raises(CommandError):
        run_command(root, env.source, '!!bk farm alias')
    assert env.manager.get_bot('SandBot') is bot


def test_panel_commands_round_trip_and_old_panels_cannot_bypass_permissions(env, bot, monkeypatch):
    def clicks(value):
        if isinstance(value, dict):
            if 'clickEvent' in value:
                yield value['text'], value['clickEvent']['value']
            for child in value.values():
                yield from clicks(child)
        elif isinstance(value, list):
            for child in value:
                yield from clicks(child)

    config.prefix_short = '!!farm'
    bot.is_online = True
    messages = []
    monkeypatch.setattr(env.source, 'reply', messages.append)
    command.register_command_tree(env.server, env.manager)
    root = env.server.roots[0]

    run_command(root, env.source, '!!farm farm')
    detail = dict(clicks(json.loads(messages[-1].to_json_str())))
    run_command(root, env.source, detail['[\u79fb\u9664\u522b\u540d]'])
    alias_clicks = list(clicks(json.loads(messages[-1].to_json_str())))
    remove_farm = next(value for label, value in alias_clicks if value.endswith(' alias del farm'))
    run_command(root, env.source, remove_farm)
    assert env.manager.get_bot_by_nickname('farm') is None

    back = next(value for label, value in alias_clicks if label == '[\u8fd4\u56de\u8be6\u60c5]')
    run_command(root, env.source, back)
    assert '\u5047\u4eba\u540d:' in messages[-1].to_plain_text()
    assert env.manager.get_bot('SandBot') is bot

    env.source.permission = 0
    for label in ['[\u79fb\u9664\u522b\u540d]', '[\u5220\u9664\u8bb0\u5f55]']:
        with pytest.raises(CommandError):
            run_command(root, env.source, detail[label])
    with pytest.raises(CommandError):
        run_command(root, env.source, remove_farm)
    run_command(root, env.source, detail['[\u53f3\u952e]'])
    assert '\u6743\u9650\u4e0d\u8db3' in messages[-1].to_plain_text()
    assert env.manager.get_bot('SandBot') is bot
    assert env.server.commands == []


@pytest.mark.parametrize('arguments, status, query, page', [
    ('', 'all', None, 1), ('1', 'all', None, 1), ('2', 'all', None, 2),
    ('online', 'online', None, 1), ('online 2', 'online', None, 2),
    ('offline', 'offline', None, 1), ('offline 3', 'offline', None, 3),
    ('search FARM', 'all', 'FARM', 1), ('search FARM 2', 'all', 'FARM', 2),
    ('online search \u5237\u6c99\u673a', 'online', '\u5237\u6c99\u673a', 1),
    ('online search farm 2', 'online', 'farm', 2), ('offline search farm 3', 'offline', 'farm', 3),
    ('search 2', 'all', '2', 1), ('search 2 3', 'all', '2', 3),
    ('search -1', 'all', '-1', 1), ('search list', 'all', 'list', 1),
    ('search online', 'all', 'online', 1), ('search offline', 'all', 'offline', 1),
    ('offline search search', 'offline', 'search', 1),
])
def test_list_command_tree_parses_filter_search_and_page(env, monkeypatch, arguments, status, query, page):
    calls = []

    def capture(source, manager, mode, *, query=None, page=1):
        calls.append((source, manager, mode, query, page))

    monkeypatch.setattr(command, 'list_bots', capture)
    env.source.permission = 0
    command.register_command_tree(env.server, env.manager)
    run_command(env.server.roots[0], env.source, ('!!bk list ' + arguments).rstrip())
    assert calls == [(env.source, env.manager, status, query, page)]


@pytest.mark.parametrize('arguments', [
    '0', '-1', '1.5', 'all', 'online 0', 'offline -1', 'online nope',
    'search', 'online search', 'offline search', 'search farm 0', 'search farm -1',
    'search farm 1.5', 'search farm extra', 'search farm 2 extra',
    'online search farm 2 extra', 'online offline', '2 online', '2 search farm',
])
def test_invalid_list_syntax_never_runs_callbacks(env, bot, monkeypatch, arguments):
    before = Path(config.bots_path).read_bytes()

    def fail(*args, **kwargs):
        raise AssertionError('invalid syntax must not run a callback')

    monkeypatch.setattr(command, 'list_bots', fail)
    monkeypatch.setattr(command, 'bot_action', fail)
    command.register_command_tree(env.server, env.manager)
    with pytest.raises(CommandError):
        run_command(env.server.roots[0], env.source, '!!bk list ' + arguments)
    assert Path(config.bots_path).read_bytes() == before
    assert env.server.commands == []


@pytest.mark.parametrize('source_name', ['source', 'player'])
@pytest.mark.parametrize('permission', [0, 4])
def test_list_commands_are_read_only_with_server_stopped(env, bot, monkeypatch, source_name, permission):
    source = getattr(env, source_name)
    source.permission = permission
    env.server.running = False
    before = {path: path.read_bytes() for path in env.path.iterdir()}
    saved = bot.to_dict()
    settings = config.to_dict()
    generation = env.manager.generation

    def fail(*args, **kwargs):
        raise AssertionError('list commands must not write, query Minecraft or schedule actions')

    monkeypatch.setattr(env.manager, 'submit', fail)
    monkeypatch.setattr(env.manager, 'request_sync', fail)
    monkeypatch.setattr(env.manager, 'save', fail)
    monkeypatch.setattr(utils, 'get_pos', fail)
    monkeypatch.setitem(sys.modules, 'minecraft_data_api', SimpleNamespace(get_server_player_list=fail))
    command.register_command_tree(env.server, env.manager)
    for arguments in ['', '2', 'online', 'offline 2', 'search FARM', 'online search \u6c99 2']:
        run_command(env.server.roots[0], source, ('!!bk list ' + arguments).rstrip())
        assert '\u5047\u4eba\u5217\u8868' in source.messages[-1]
    assert bot.to_dict() == saved
    assert not bot.is_online
    assert env.manager.generation == generation
    assert env.manager.get_bot('SandBot') is bot
    assert config.to_dict() == settings
    assert {path: path.read_bytes() for path in env.path.iterdir()} == before
    assert env.server.commands == []


def _panel_buttons(message):
    def visit(value):
        if isinstance(value, dict):
            if 'clickEvent' in value:
                assert value['clickEvent']['action'] == 'suggest_command'
                yield value['text'], value['clickEvent']['value']
            for child in value.values():
                yield from visit(child)
        elif isinstance(value, list):
            for child in value:
                yield from visit(child)

    return dict(visit(json.loads(message.to_json_str())))


def test_navigation_commands_round_trip_with_filters_search_and_custom_prefix(env, monkeypatch):
    config.prefix_short = '!!farm'
    bots = [Bot(env.server, f'Bot{i:02}', [f'farm-{i:02}'],
                'minecraft:overworld', [0, 64, 0], [0, 0]) for i in range(45)]
    for index, bot in enumerate(bots):
        bot.is_online = index % 2 == 0
    snapshots = []

    def snapshot():
        snapshots.append(True)
        return bots.copy()

    monkeypatch.setattr(env.manager, 'get_all_bots', snapshot)
    messages = []
    monkeypatch.setattr(env.source, 'reply', messages.append)
    command.register_command_tree(env.server, env.manager)

    def show(text, status, page, pages, total, query='FaRm'):
        before = len(snapshots)
        run_command(env.server.roots[0], env.source, text)
        assert len(snapshots) == before + 1
        plain = messages[-1].to_plain_text()
        assert plain.startswith(f'\u5047\u4eba\u5217\u8868 \u00b7 {status} \u00b7 \u7b2c {page}/{pages} \u9875 \u00b7 \u5171 {total} \u4e2a')
        assert ('\u641c\u7d22: ' in plain) is (query is not None)
        if query is not None:
            assert '\u641c\u7d22: ' + query in plain
        return _panel_buttons(messages[-1])

    buttons = show('!!farm list online search FaRm 2', '\u5728\u7ebf', 2, 3, 23)
    buttons = show(buttons['[\u4e0b\u4e00\u9875]'], '\u5728\u7ebf', 3, 3, 23)
    buttons = show(buttons['[\u4e0a\u4e00\u9875]'], '\u5728\u7ebf', 2, 3, 23)
    buttons = show(buttons['[\u79bb\u7ebf]'], '\u79bb\u7ebf', 1, 3, 22)
    buttons = show(buttons['[\u4e0b\u4e00\u9875]'], '\u79bb\u7ebf', 2, 3, 22)
    buttons = show(buttons['[\u5237\u65b0]'], '\u79bb\u7ebf', 2, 3, 22)
    buttons = show(buttons['[\u6e05\u9664\u641c\u7d22]'], '\u79bb\u7ebf', 1, 3, 22, query=None)
    buttons = show(buttons['[\u5168\u90e8]'], '\u5168\u90e8', 1, 5, 45, query=None)
    show(buttons['[\u641c\u7d22]'] + '20', '\u5168\u90e8', 1, 1, 1, query='20')
    assert env.server.commands == []


def test_old_page_links_recover_after_records_disappear(env, monkeypatch):
    bots = [Bot(env.server, f'Bot{i:02}', [], 'minecraft:overworld', [0, 64, 0], [0, 0]) for i in range(21)]
    monkeypatch.setattr(env.manager, 'get_all_bots', lambda: bots.copy())
    messages = []
    monkeypatch.setattr(env.source, 'reply', messages.append)
    command.register_command_tree(env.server, env.manager)
    root = env.server.roots[0]
    run_command(root, env.source, '!!bk list 3')
    refresh = _panel_buttons(messages[-1])['[\u5237\u65b0]']
    del bots[10:]
    run_command(root, env.source, refresh)
    assert '\u7b2c 1/1 \u9875' in messages[-1].to_plain_text()
    assert '\u9875\u7801\u8d85\u51fa\u8303\u56f4' in messages[-1].to_plain_text()
    assert _panel_buttons(messages[-1])['[\u5237\u65b0]'] == '!!bk list'


@pytest.mark.parametrize('online', [False, True])
def test_list_actions_target_exact_records_and_recheck_current_permissions(env, bot, monkeypatch, online):
    bot.is_online = online
    messages = []
    monkeypatch.setattr(env.source, 'reply', messages.append)
    command.register_command_tree(env.server, env.manager)
    root = env.server.roots[0]
    run_command(root, env.source, '!!bk list search Sand')
    buttons = _panel_buttons(messages[-1])
    assert buttons['[\u8be6\u60c5]'] == '!!bk SandBot'
    assert env.server.commands == []

    assert env.manager.remove_alias('SandBot', 'farm')
    run_command(root, env.source, buttons['[\u8be6\u60c5]'])
    assert '\u5047\u4eba\u540d:' in messages[-1].to_plain_text()
    actions = []
    monkeypatch.setattr(env.manager, 'submit', lambda callback, *args: callback(*args))
    for method in ('spawn', 'use', 'kill'):
        def capture(*args, _method=method, **kwargs):
            actions.append(_method)
            return True
        monkeypatch.setattr(bot, method, capture)
    labels = ['[\u4e0b\u7ebf]' if online else '[\u4e0a\u7ebf]', '[\u53f3\u952e]']
    for label in labels:
        assert buttons[label].startswith('!!bk SandBot ')
        run_command(root, env.source, buttons[label])
    expected = ['kill', 'use'] if online else ['spawn', 'use']
    assert actions == expected

    run_command(root, env.source, '!!bk Sand use')
    assert '\u672a\u627e\u5230\u5047\u4eba' in messages[-1].to_plain_text()
    assert actions == expected
    config.permission['bot'] = 4
    env.source.permission = 3
    for label in labels:
        run_command(root, env.source, buttons[label])
        assert '\u6743\u9650\u4e0d\u8db3' in messages[-1].to_plain_text()
    assert actions == expected
    assert env.server.commands == []


@pytest.mark.parametrize('acknowledge_spawn', [False, True])
def test_offline_list_use_waits_for_spawn_confirmation(env, bot, monkeypatch, acknowledge_spawn):
    messages = []
    tasks = []
    submit = env.manager.submit
    monkeypatch.setattr(env.source, 'reply', messages.append)

    def capture_task(*args, **kwargs):
        task = submit(*args, **kwargs)
        tasks.append(task)
        return task

    def acknowledge(text):
        if acknowledge_spawn and ' spawn at ' in text:
            env.manager.update_player_status(bot.real_name, True, confirm=False)

    monkeypatch.setattr(env.manager, 'submit', capture_task)
    env.server.on_execute = acknowledge
    config.spawn_max_wait_time = 0.03
    config.spawn_check_interval = 0.01
    command.register_command_tree(env.server, env.manager)
    root = env.server.roots[0]
    run_command(root, env.source, '!!bk list offline')
    buttons = _panel_buttons(messages[-1])
    assert buttons['[\u53f3\u952e]'] == '!!bk SandBot use'
    assert not tasks
    assert env.server.commands == []

    run_command(root, env.source, buttons['[\u53f3\u952e]'])
    assert len(tasks) == 1
    tasks[0].result(timeout=2)
    assert env.server.commands[0].startswith('player sandbot spawn at ')
    assert bot.is_online is acknowledge_spawn
    if acknowledge_spawn:
        assert len(env.server.commands) == 2
        assert env.server.commands[1] == 'player sandbot use once'
        assert '\u53f3\u952e\u8bf7\u6c42\u5df2\u53d1\u9001' in messages[-1].to_plain_text()
    else:
        assert len(env.server.commands) == 1
        assert '\u64cd\u4f5c\u672a\u5b8c\u6210' in messages[-1].to_plain_text()


@pytest.mark.parametrize('name', ['search', 'online', 'offline'])
def test_new_list_syntax_does_not_reserve_top_level_names(env, name):
    env.manager.upsert_bot(name, 'farm', 'minecraft:overworld', [0, 64, 0], [0, 0])
    command.register_command_tree(env.server, env.manager)
    run_command(env.server.roots[0], env.source, f'!!bk {name}')
    assert '\u5047\u4eba\u540d:' in env.source.messages[-1]
    assert env.manager.get_bot(name) is not None


def test_list_reports_invalid_query_without_scheduling_work(env, monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError('invalid queries must not schedule work')

    monkeypatch.setattr(env.manager, 'submit', fail)
    command.list_bots(env.source, env.manager, query='two words')
    assert '\u5217\u8868\u53c2\u6570\u65e0\u6548' in env.source.messages[-1]
