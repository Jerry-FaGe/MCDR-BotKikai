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
    assert 'NewBot' in env.source.messages[-1]
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
    assert '\u5931\u8d25' in env.source.messages[-1]
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
    assert '\u5df2\u4e3a' in source.messages[-1]
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
    assert '\u5df2\u4e3a' not in env.source.messages[-1]
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
    assert '\u672a\u67e5\u8be2\u5230' in env.source.messages[-1]

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
    assert '\u6743\u9650\u4e0d\u8db3' in messages[-1]
    assert env.manager.get_bot('SandBot') is bot
    assert env.server.commands == []
