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
