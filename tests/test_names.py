import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

import bot_kikai
import bot_kikai.bot_manager as manager_module
from bot_kikai.bot import Bot
from bot_kikai.bot_manager import BotManager
from bot_kikai.config import Config, config
from bot_kikai.storage import read_json, write_json


@pytest.fixture
def name_saves(env, monkeypatch):
    manager = env.manager
    finished = threading.Condition()
    original_done = manager._task_done

    def task_done(future):
        try:
            original_done(future)
        finally:
            with finished:
                finished.notify_all()

    def settled():
        with manager._lock:
            return manager._name_save_future is None and (
                not manager._pending_names or manager._name_save_failed or manager._write_blocked
            )

    def wait():
        with finished:
            assert finished.wait_for(settled, timeout=5), 'name save did not settle'

    monkeypatch.setattr(manager, '_task_done', task_done)
    return wait


@pytest.fixture
def writes(monkeypatch):
    calls = []
    original = manager_module.write_json

    def record(path, data):
        original(path, data)
        calls.append(data)

    monkeypatch.setattr(manager_module, 'write_json', record)
    return calls


@pytest.fixture
def busy_workers(env):
    release = threading.Event()
    tasks = [env.manager.submit(release.wait, 10) for _ in range(4)]
    try:
        yield release
    finally:
        release.set()
        for task in tasks:
            task.result(timeout=5)


def test_legacy_data_starts_unconfirmed_and_round_trips_after_observation(env):
    bot = Bot.from_dict(env.server, 'SandBot', {'nick': 'farm', 'dim': 0, 'pos': '1 64 2'})
    assert bot.expected_name == bot.real_name == 'sandbot'
    assert bot.confirmed_name is None
    assert 'confirmed_name' not in bot.to_dict()
    assert bot.confirm_name('SandBot')
    assert not bot.confirm_name('SandBot')
    assert bot.expected_name == 'sandbot'
    assert bot.real_name == bot.confirmed_name == 'SandBot'
    restored = Bot.from_dict(env.server, bot.name, bot.to_dict())
    assert restored.real_name == 'SandBot'
    assert restored.to_dict() == bot.to_dict()


@pytest.mark.parametrize('value', ['', 'ab', 'a' * 17, 'two words', '@a', 'SandBot\n', '\u017fandbot', 1, True, [], {}])
def test_invalid_stored_names_are_rejected(env, value):
    with pytest.raises(ValueError, match='confirmed_name'):
        Bot.from_dict(env.server, 'SandBot', {'confirmed_name': value})


@pytest.mark.parametrize('value', ['OtherBot', 'b_SandBot', '@a', '\u017fandbot', None, []])
def test_unrelated_or_invalid_observations_do_not_change_the_name(env, bot, value):
    assert bot.confirm_name('SandBot')
    assert not bot.confirm_name(value)
    assert bot.real_name == 'SandBot'


def test_changed_target_ignores_old_confirmation_but_case_only_change_keeps_it(env):
    data = {'confirmed_name': 'b_SandBot'}
    bot = Bot.from_dict(env.server, 'SandBot', data, Config(bot_name_prefix='b_'))
    assert bot.real_name == 'b_SandBot'
    renamed = Bot.from_dict(env.server, 'OtherBot', data, Config(bot_name_prefix='b_'))
    affixed = Bot.from_dict(env.server, 'SandBot', data, Config(bot_name_prefix='c_'))
    for changed in (renamed, affixed):
        assert changed.confirmed_name is None
        assert changed.real_name == changed.expected_name
        assert 'confirmed_name' not in changed.to_dict()
    same = Bot.from_dict(env.server, 'SANDBOT', data, Config(bot_name_prefix='B_'))
    assert same.expected_name == 'B_sandbot'
    assert same.confirmed_name == 'b_SandBot'


def test_join_and_leave_persist_once_then_update_changed_spelling(env, bot, name_saves, writes):
    bot_kikai.bot_manager_instance = env.manager
    bot_kikai.on_player_joined(env.server, 'SandBot', None)
    name_saves()
    assert bot.is_online
    assert read_json(config.bots_path)['SandBot']['confirmed_name'] == 'SandBot'
    assert len(writes) == 1
    assert env.manager.get_bot_by_nickname('SANDBOT') is bot

    bot_kikai.on_player_left(env.server, 'SandBot')
    bot_kikai.on_player_joined(env.server, 'SandBot', None)
    name_saves()
    assert len(writes) == 1

    bot_kikai.on_player_left(env.server, 'SANDBOT')
    name_saves()
    assert not bot.is_online
    assert bot.real_name == 'SANDBOT'
    assert read_json(config.bots_path)['SandBot']['confirmed_name'] == 'SANDBOT'
    assert len(writes) == 2


def test_leave_can_be_the_first_real_name_observation(env, bot, name_saves):
    env.manager.update_player_status('SandBot', False)
    name_saves()
    assert not bot.is_online
    assert bot.confirmed_name == 'SandBot'
    assert read_json(config.bots_path)['SandBot']['confirmed_name'] == 'SandBot'


def test_status_only_updates_and_other_players_do_not_confirm(env, bot, name_saves, writes):
    env.manager.set_bot_online(bot.name)
    env.manager.set_bot_offline(bot.name)
    env.manager.update_player_status('SandBot', True, confirm=False)
    env.manager.update_player_status('OtherBot', True)
    name_saves()
    assert bot.is_online
    assert bot.confirmed_name is None
    assert not writes


def test_sync_retains_original_names_without_repeated_writes(env, bot, monkeypatch, name_saves, writes):
    env.server.startup = True
    players = ['sAnDbOt', 'OtherBot']
    monkeypatch.setitem(sys.modules, 'minecraft_data_api', SimpleNamespace(
        get_server_player_list=lambda: (len(players), 20, players),
    ))
    for _ in range(2):
        assert env.manager.request_sync().result(timeout=3)
        name_saves()
    assert bot.is_online
    assert bot.confirmed_name == 'sAnDbOt'
    assert len(writes) == 1
    players.clear()
    assert env.manager.sync_online_status()
    name_saves()
    assert not bot.is_online
    assert bot.confirmed_name == 'sAnDbOt'
    assert len(writes) == 1


def test_stale_sync_cannot_replace_newer_event_spelling(env, bot, monkeypatch, name_saves):
    env.server.startup = True

    def query():
        env.manager.update_player_status('SANDBOT', False)
        return 1, 20, ['SandBot']

    monkeypatch.setitem(sys.modules, 'minecraft_data_api', SimpleNamespace(get_server_player_list=query))
    assert env.manager.sync_online_status()
    name_saves()
    assert not bot.is_online
    assert bot.real_name == 'SANDBOT'
    assert read_json(config.bots_path)['SandBot']['confirmed_name'] == 'SANDBOT'


@pytest.mark.parametrize('operation', ['reload', 'update', 'delete', 'stop'])
def test_stale_sync_cannot_confirm_replaced_or_cancelled_records(env, bot, monkeypatch, name_saves, operation):
    env.server.startup = True

    def query():
        if operation == 'reload':
            env.manager.reload_config()
        elif operation == 'update':
            env.manager.upsert_bot('SandBot', 'new', 'minecraft:overworld', [8, 64, 0], [0, 0])
        elif operation == 'delete':
            env.manager.remove_bot('SandBot')
        else:
            env.manager.clear_all_online_status()
        return 1, 20, ['SandBot']

    monkeypatch.setitem(sys.modules, 'minecraft_data_api', SimpleNamespace(get_server_player_list=query))
    env.manager.sync_online_status()
    name_saves()
    assert bot.confirmed_name is None
    current = env.manager.get_bot('SandBot')
    assert current is None or current.confirmed_name is None
    assert 'confirmed_name' not in read_json(config.bots_path).get('SandBot', {})


def test_waiting_action_uses_confirmed_name_without_replacing_the_bot(env, bot, name_saves):
    spawn_requested = threading.Event()
    env.server.on_execute = lambda text: spawn_requested.set()
    task = env.manager.submit(bot.use)
    try:
        assert spawn_requested.wait(3)
        env.manager.update_player_status('sAnDbOt', True)
        assert task.result(timeout=3)
        name_saves()
        assert env.manager.get_bot('SandBot') is bot
        assert env.server.commands[0].startswith('player sandbot spawn ')
        assert env.server.commands[-1] == 'player sAnDbOt use once'
    finally:
        bot.cancel()


def test_synchronous_spawn_confirmation_does_not_deadlock_metadata_save(env, bot, name_saves):
    env.server.on_execute = lambda text: env.manager.update_player_status('SandBot', True)
    assert env.manager.submit(bot.use).result(timeout=3)
    name_saves()
    assert env.server.commands[-1] == 'player SandBot use once'


def test_known_name_survives_offline_reload_and_manager_restart(env, bot, name_saves):
    env.manager.update_player_status('SandBot', False)
    name_saves()
    env.manager.reload_config()
    assert env.manager.get_bot('SandBot').confirmed_name == 'SandBot'
    env.manager.shutdown()
    restarted = BotManager(env.server)
    try:
        current = restarted.get_bot('SandBot')
        assert not current.is_online
        assert current.real_name == 'SandBot'
        assert current.kill()
        assert env.server.commands[-1] == 'player SandBot kill'
    finally:
        restarted.shutdown()


def test_plugin_upgrade_does_not_treat_predicted_name_as_confirmation(env, bot):
    legacy_bot = SimpleNamespace(real_name='sandbot', is_online=True)
    previous = SimpleNamespace(bot_manager_instance=SimpleNamespace(get_all_bots=lambda: [legacy_bot]))
    bot_kikai.on_load(env.server, previous)
    current = bot_kikai.bot_manager_instance.get_bot('SandBot')
    assert current.is_online
    assert current.confirmed_name is None
    bot_kikai.bot_manager_instance.shutdown()
    assert 'confirmed_name' not in read_json(config.bots_path)['SandBot']


def test_unsaved_offline_name_survives_plugin_reload(env, bot, monkeypatch, name_saves):
    original_write = manager_module.write_json

    def fail(*args):
        raise OSError('disk full')

    monkeypatch.setattr(manager_module, 'write_json', fail)
    env.manager.update_player_status('SandBot', False)
    name_saves()
    previous = SimpleNamespace(bot_manager_instance=env.manager)
    env.manager.shutdown()
    monkeypatch.setattr(manager_module, 'write_json', original_write)
    bot_kikai.on_load(env.server, previous)
    current = bot_kikai.bot_manager_instance.get_bot('SandBot')
    assert current.confirmed_name == 'SandBot'
    assert not current.is_online
    bot_kikai.bot_manager_instance.shutdown()
    assert read_json(config.bots_path)['SandBot']['confirmed_name'] == 'SandBot'


def test_normal_edit_keeps_name_while_pending_save_is_queued(env, bot, name_saves, busy_workers):
    env.manager.update_player_status('SandBot', True)
    env.manager.upsert_bot('SandBot', 'new', 'minecraft:the_nether', [8, 70, 9], [45, 10])
    current = env.manager.get_bot('SandBot')
    assert current is not bot
    assert current.confirmed_name == 'SandBot'
    assert current.is_online
    busy_workers.set()
    name_saves()
    saved = read_json(config.bots_path)['SandBot']
    assert saved == current.to_dict()
    assert saved['position'] == [8, 70, 9]
    assert saved['facing'] == [45, 10]
    assert 'new' in saved['nicknames']


def test_queued_confirmation_does_not_resurrect_deleted_bot(env, bot, name_saves, busy_workers):
    env.manager.update_player_status('SandBot', True)
    assert env.manager.remove_bot('SandBot')
    busy_workers.set()
    name_saves()
    assert read_json(config.bots_path) == {}


def test_readded_record_does_not_inherit_deleted_pending_confirmation(env, bot, name_saves, busy_workers):
    env.manager.update_player_status('SandBot', True)
    env.manager.remove_bot('SandBot')
    env.manager.upsert_bot('SandBot', 'new', 'minecraft:overworld', [0, 64, 0], [0, 0])
    busy_workers.set()
    name_saves()
    assert env.manager.get_bot('SandBot').confirmed_name is None
    assert 'confirmed_name' not in read_json(config.bots_path)['SandBot']


def test_queued_confirmation_preserves_valid_external_edits(env, bot, name_saves, busy_workers):
    env.manager.update_player_status('SandBot', True)
    data = read_json(config.bots_path)
    data['SandBot'].update(nicknames=['external'], position=[9, 80, 7], facing=[45, 15], note='keep me')
    data['OtherBot'] = {'nick': 'other', 'dim': -1, 'pos': '3 70 5'}
    write_json(config.bots_path, data)
    busy_workers.set()
    name_saves()
    data['SandBot']['confirmed_name'] = 'SandBot'
    assert read_json(config.bots_path) == data


def test_queued_confirmation_respects_external_deletion(env, bot, name_saves, busy_workers):
    env.manager.update_player_status('SandBot', True)
    write_json(config.bots_path, {})
    busy_workers.set()
    name_saves()
    assert read_json(config.bots_path) == {}


@pytest.mark.parametrize('loader', ['load', 'reload_config'])
def test_reload_keeps_pending_name_and_reschedules_old_generation_save(env, bot, name_saves, busy_workers, loader):
    env.manager.update_player_status('SandBot', True)
    data = read_json(config.bots_path)
    data['SandBot']['position'] = [7, 80, 9]
    data['SandBot']['confirmed_name'] = 'sandbot'
    write_json(config.bots_path, data)
    getattr(env.manager, loader)()
    current = env.manager.get_bot('SandBot')
    assert current is not bot
    assert current.real_name == 'SandBot'
    busy_workers.set()
    name_saves()
    data['SandBot']['confirmed_name'] = 'SandBot'
    assert read_json(config.bots_path) == data


def test_external_case_only_rename_retains_confirmation_on_reload(env, bot, name_saves, busy_workers):
    env.manager.update_player_status('SandBot', False)
    data = read_json(config.bots_path)
    write_json(config.bots_path, {'SANDBOT': data['SandBot']})
    env.manager.reload_config()
    assert env.manager.get_bot('SANDBOT').confirmed_name == 'SandBot'
    busy_workers.set()
    name_saves()
    assert set(read_json(config.bots_path)) == {'SANDBOT'}
    assert read_json(config.bots_path)['SANDBOT']['confirmed_name'] == 'SandBot'


@pytest.mark.parametrize('change', ['prefix', 'suffix', 'name'])
def test_target_change_discards_pending_confirmation(env, bot, name_saves, busy_workers, change):
    env.manager.update_player_status('SandBot', True)
    if change == 'name':
        write_json(config.bots_path, {'OtherBot': bot.to_dict()})
    else:
        write_json(config.config_path, {f'bot_name_{change}': 'b_'})
    env.manager.reload_config()
    current = env.manager.get_all_bots()[0]
    assert current.confirmed_name is None
    assert not current.is_online
    before = Path(config.bots_path).read_bytes()
    busy_workers.set()
    name_saves()
    assert Path(config.bots_path).read_bytes() == before


def test_server_stop_preserves_pending_confirmation(env, bot, name_saves, busy_workers):
    env.manager.update_player_status('SandBot', True)
    env.server.running = False
    env.manager.clear_all_online_status()
    current = env.manager.get_bot('SandBot')
    assert current is not bot
    assert not current.is_online
    assert current.real_name == 'SandBot'
    busy_workers.set()
    name_saves()
    assert read_json(config.bots_path)['SandBot']['confirmed_name'] == 'SandBot'


def test_queued_observations_are_coalesced_into_latest_spelling(env, bot, name_saves, busy_workers, writes):
    other = Bot.from_dict(env.server, 'OtherBot', {})
    env.manager.add_bot(other)
    writes.clear()
    env.manager.update_player_status('SandBot', True)
    first_task = env.manager._name_save_future
    env.manager.update_player_status('SANDBOT', False)
    env.manager.update_player_status('OtherBot', True)
    assert env.manager._name_save_future is first_task
    assert not writes
    busy_workers.set()
    name_saves()
    assert len(writes) == 1
    data = read_json(config.bots_path)
    assert data['SandBot']['confirmed_name'] == 'SANDBOT'
    assert data['OtherBot']['confirmed_name'] == 'OtherBot'


@pytest.mark.parametrize('fail_first', [False, True])
def test_new_observation_while_previous_save_finishes_is_not_lost(env, bot, monkeypatch, name_saves, fail_first):
    entered = threading.Event()
    release = threading.Event()
    original_done = env.manager._task_done
    original_write = manager_module.write_json
    attempts = []

    def write(path, data):
        attempts.append(data)
        if fail_first and len(attempts) == 1:
            raise OSError('temporary failure')
        original_write(path, data)

    def delayed_done(future):
        if not entered.is_set():
            entered.set()
            assert release.wait(5)
        original_done(future)

    monkeypatch.setattr(manager_module, 'write_json', write)
    monkeypatch.setattr(env.manager, '_task_done', delayed_done)
    try:
        env.manager.update_player_status('SandBot', True)
        assert entered.wait(3)
        env.manager.update_player_status('SANDBOT', False)
    finally:
        release.set()
    name_saves()
    assert bot.real_name == 'SANDBOT'
    assert read_json(config.bots_path)['SandBot']['confirmed_name'] == 'SANDBOT'
    assert len(attempts) == 2


@pytest.mark.parametrize('operation', ['update', 'delete'])
def test_in_progress_metadata_write_cannot_overwrite_a_newer_edit(env, bot, monkeypatch, name_saves, operation):
    entered = threading.Event()
    release = threading.Event()
    original_write = manager_module.write_json

    def delayed_write(path, data):
        if not entered.is_set():
            entered.set()
            assert release.wait(5)
        original_write(path, data)

    monkeypatch.setattr(manager_module, 'write_json', delayed_write)
    try:
        env.manager.update_player_status('SandBot', True)
        assert entered.wait(3)
        with ThreadPoolExecutor(max_workers=1) as pool:
            if operation == 'delete':
                task = pool.submit(env.manager.remove_bot, 'SandBot')
            else:
                task = pool.submit(env.manager.upsert_bot, 'SandBot', 'new', 'minecraft:overworld', [9, 80, 7], [45, 15])
            release.set()
            task.result(timeout=3)
    finally:
        release.set()
    name_saves()
    saved = read_json(config.bots_path)
    if operation == 'delete':
        assert saved == {}
    else:
        assert saved['SandBot']['confirmed_name'] == 'SandBot'
        assert saved['SandBot']['position'] == [9, 80, 7]
        assert 'new' in saved['SandBot']['nicknames']


def test_full_queue_retries_name_save_after_a_slot_is_available(env, bot, name_saves):
    release = threading.Event()
    tasks = []
    try:
        tasks = [env.manager.submit(release.wait, 10) for _ in range(env.manager.MAX_PENDING_TASKS)]
        env.manager.update_player_status('SandBot', True)
        assert bot.real_name == 'SandBot'
        assert env.manager._name_save_future is None
        with pytest.raises(RuntimeError):
            env.manager.submit(lambda: None)
        release.set()
        for task in tasks:
            task.result(timeout=5)
        name_saves()
        assert read_json(config.bots_path)['SandBot']['confirmed_name'] == 'SandBot'
    finally:
        release.set()


def test_shutdown_can_flush_names_when_no_task_slot_was_available(env, bot):
    release = threading.Event()
    tasks = []
    try:
        tasks = [env.manager.submit(release.wait, 10) for _ in range(env.manager.MAX_PENDING_TASKS)]
        env.manager.update_player_status('SandBot', True)
        assert env.manager._name_save_future is None
        env.manager.shutdown()
        assert read_json(config.bots_path)['SandBot']['confirmed_name'] == 'SandBot'
    finally:
        release.set()
        for task in tasks:
            if not task.cancelled():
                task.result(timeout=5)


def test_save_failure_preserves_memory_and_file_without_retry_loop(env, bot, monkeypatch, name_saves, caplog):
    before = Path(config.bots_path).read_bytes()
    original_write = manager_module.write_json
    attempts = []

    def fail(*args):
        attempts.append(args)
        raise OSError('disk full')

    monkeypatch.setattr(manager_module, 'write_json', fail)
    env.manager.update_player_status('SandBot', True)
    name_saves()
    assert env.manager.get_bot('SandBot') is bot
    assert bot.is_online
    assert bot.real_name == 'SandBot'
    assert Path(config.bots_path).read_bytes() == before
    assert 'disk full' in caplog.text
    env.manager.submit(lambda: None).result(timeout=3)
    name_saves()
    assert len(attempts) == 1

    monkeypatch.setattr(manager_module, 'write_json', original_write)
    env.manager.update_player_status('SandBot', False)
    name_saves()
    assert read_json(config.bots_path)['SandBot']['confirmed_name'] == 'SandBot'


def test_corrupt_file_blocks_auto_save_until_successful_reload(env, bot, name_saves, caplog):
    before = bot.to_dict()
    Path(config.bots_path).write_text('{', encoding='utf8')
    env.manager.update_player_status('SandBot', True)
    name_saves()
    assert bot.real_name == 'SandBot'
    assert Path(config.bots_path).read_text(encoding='utf8') == '{'
    assert caplog.records
    with pytest.raises(RuntimeError):
        env.manager.save()
    write_json(config.bots_path, {'SandBot': before})
    env.manager.reload_config()
    name_saves()
    assert env.manager.get_bot('SandBot').confirmed_name == 'SandBot'
    assert read_json(config.bots_path)['SandBot']['confirmed_name'] == 'SandBot'


def test_shutdown_flushes_pending_names_but_blocks_later_observations(env, bot, name_saves, busy_workers, writes):
    env.manager.update_player_status('SandBot', True)
    assert env.manager._name_save_future is not None
    env.manager.shutdown()
    assert read_json(config.bots_path)['SandBot']['confirmed_name'] == 'SandBot'
    assert len(writes) == 1
    env.manager.update_player_status('SANDBOT', False)
    env.manager.shutdown()
    busy_workers.set()
    name_saves()
    assert bot.real_name == 'SandBot'
    assert len(writes) == 1
