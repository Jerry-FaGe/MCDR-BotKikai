import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from bot_kikai import command
import bot_kikai.bot_manager as manager_module
from bot_kikai.config import config
from bot_kikai.storage import read_json, write_json


@pytest.mark.parametrize('online', [False, True])
@pytest.mark.parametrize('confirmed', [False, True])
def test_alias_edits_only_change_nicknames_and_keep_the_active_bot(env, bot, online, confirmed):
    bot.is_online = online
    if confirmed:
        bot.confirm_name('SandBot')
        env.manager.save()
    before = bot.to_dict()
    generation = env.manager.generation
    status_version = env.manager._status_versions[bot]

    assert env.manager.add_alias('FARM', 'new')
    assert env.manager.get_bot_by_nickname('NEW') is bot
    assert env.manager.remove_alias('new', 'FARM')
    assert env.manager.get_bot_by_nickname('farm') is None
    assert env.manager.get_bot('SandBot') is bot
    assert env.manager.get_bot_by_real_name('SANDBOT') is bot
    assert bot.is_online is online
    assert env.manager.generation == generation
    assert env.manager._status_versions[bot] == status_version
    before['nicknames'] = ['SandBot', '\u5237\u6c99\u673a', 'new']
    assert bot.to_dict() == before
    assert read_json(config.bots_path)['SandBot'] == before
    assert not env.server.commands


def test_alias_edits_persist_across_reload(env, bot):
    assert env.manager.add_alias('farm', '\u6c99\u573a')
    assert env.manager.remove_alias('farm', 'farm')
    env.manager.load()
    current = env.manager.get_bot('SandBot')
    assert current is not bot
    assert env.manager.get_bot_by_nickname('\u6c99\u573a') is current
    assert env.manager.get_bot_by_nickname('farm') is None
    assert current.position == bot.position
    assert current.facing == bot.facing


def test_duplicate_add_and_missing_remove_do_not_write(env, bot, monkeypatch):
    before = Path(config.bots_path).read_bytes()

    def fail(*args):
        raise AssertionError('a no-op must not write')

    monkeypatch.setattr(manager_module, 'write_json', fail)
    assert not env.manager.add_alias('farm', 'FARM')
    assert not env.manager.add_alias('farm', 'SANDBOT')
    assert not env.manager.remove_alias('farm', 'missing')
    assert Path(config.bots_path).read_bytes() == before


def test_alias_lookup_deduplication_and_removal_use_casefold(env, bot):
    assert env.manager.add_alias('farm', 'Stra\u00dfe')
    assert not env.manager.add_alias('farm', 'STRASSE')
    assert env.manager.get_bot_by_nickname('strasse') is bot
    assert env.manager.remove_alias('STRASSE', 'strasse')
    assert env.manager.get_bot_by_nickname('Stra\u00dfe') is None


@pytest.mark.parametrize('alias', ['', 'two words', 'bad\nname', '\x00name', '\x7f', None, 1, []])
@pytest.mark.parametrize('method', ['add_alias', 'remove_alias'])
def test_invalid_aliases_are_rejected_without_mutation(env, bot, alias, method):
    before = bot.to_dict()
    data = Path(config.bots_path).read_bytes()
    with pytest.raises(ValueError):
        getattr(env.manager, method)('farm', alias)
    assert bot.to_dict() == before
    assert Path(config.bots_path).read_bytes() == data


@pytest.mark.parametrize('alias', ['OTHERBOT', 'other', 'B_OTHERBOT', 'ADD', 'del', 'List', 'reload'])
def test_alias_conflicts_are_rejected(env, bot, alias):
    write_json(config.config_path, {'bot_name_prefix': 'b_'})
    env.manager.reload_config()
    env.manager.upsert_bot('OtherBot', 'other', 'minecraft:overworld', [0, 64, 0], [0, 0])
    current = env.manager.get_bot('SandBot')
    before = current.to_dict()
    data = Path(config.bots_path).read_bytes()
    with pytest.raises(ValueError):
        env.manager.add_alias('farm', alias)
    assert current.to_dict() == before
    assert Path(config.bots_path).read_bytes() == data


@pytest.mark.parametrize('alias', ['SandBot', 'SANDBOT', 'b_sandbot', 'B_SANDBOT'])
def test_registered_and_game_names_cannot_be_removed(env, bot, alias):
    write_json(config.config_path, {'bot_name_prefix': 'b_'})
    env.manager.reload_config()
    current = env.manager.get_bot('SandBot')
    before = Path(config.bots_path).read_bytes()
    with pytest.raises(ValueError):
        env.manager.remove_alias('farm', alias)
    assert env.manager.get_bot_by_nickname(alias) is current
    assert Path(config.bots_path).read_bytes() == before


def test_game_name_can_target_alias_management_without_becoming_an_alias(env, bot):
    write_json(config.config_path, {'bot_name_prefix': 'b_'})
    env.manager.reload_config()
    current = env.manager.get_bot('SandBot')
    assert env.manager.add_alias('B_SANDBOT', 'new')
    before = Path(config.bots_path).read_bytes()
    assert not env.manager.add_alias('new', 'b_SandBot')
    assert all(nick.casefold() != 'b_sandbot' for nick in current.nicknames)
    assert Path(config.bots_path).read_bytes() == before


def test_removing_last_custom_alias_keeps_the_record(env, bot):
    assert env.manager.remove_alias('farm', '\u5237\u6c99\u673a')
    assert env.manager.remove_alias('farm', 'farm')
    assert bot.nicknames == ['SandBot']
    assert env.manager.get_bot_by_nickname('sandbot') is bot
    assert set(read_json(config.bots_path)) == {'SandBot'}


def test_remove_clears_all_legacy_case_variants_and_preserves_other_order(env, bot):
    data = bot.to_dict()
    data['nicknames'] = ['SandBot', 'farm', 'FARM', 'last']
    write_json(config.bots_path, {'SandBot': data})
    env.manager.load()
    current = env.manager.get_bot('SandBot')
    assert env.manager.remove_alias('FARM', 'farm')
    assert current.nicknames == ['SandBot', 'last']
    assert env.manager.get_bot_by_nickname('farm') is None


@pytest.mark.parametrize('method', ['add_alias', 'remove_alias'])
def test_unknown_bot_is_not_created_by_alias_commands(env, method):
    before = Path(config.bots_path).read_bytes()
    with pytest.raises(ValueError):
        getattr(env.manager, method)('missing', 'new')
    assert not env.manager.bots
    assert Path(config.bots_path).read_bytes() == before


@pytest.mark.parametrize('method, alias', [('add_alias', 'new'), ('remove_alias', 'farm')])
def test_alias_write_failure_does_not_change_memory_indexes_or_actions(env, bot, monkeypatch, method, alias):
    bot.is_online = True
    before = bot.to_dict()
    data = Path(config.bots_path).read_bytes()
    aliases = env.manager._aliases

    def fail(*args):
        raise OSError('disk full')

    monkeypatch.setattr(manager_module, 'write_json', fail)
    with pytest.raises(OSError):
        getattr(env.manager, method)('farm', alias)
    assert env.manager._aliases is aliases
    assert env.manager.get_bot_by_nickname('new') is None
    assert bot.to_dict() == before
    assert bot.is_online
    assert bot.stop()
    assert Path(config.bots_path).read_bytes() == data


def test_bad_file_blocks_alias_writes_until_reloaded(env, bot):
    before = bot.to_dict()
    Path(config.bots_path).write_text('{', encoding='utf8')
    with pytest.raises(ValueError):
        env.manager.add_alias('farm', 'new')
    assert bot.to_dict() == before
    assert Path(config.bots_path).read_text(encoding='utf8') == '{'
    write_json(config.bots_path, {'SandBot': before})
    with pytest.raises(RuntimeError):
        env.manager.add_alias('farm', 'new')
    env.manager.load()
    assert env.manager.add_alias('farm', 'new')


def test_alias_patch_preserves_external_coordinates_names_and_other_records(env, bot):
    data = read_json(config.bots_path)
    data['SandBot'].update(position=[9, 80, 7], facing=[45, 15], dimension='minecraft:the_nether',
                           confirmed_name='SandBot', note='keep me')
    data['OtherBot'] = {'nick': 'other', 'dim': -1, 'pos': '3 70 5'}
    write_json(config.bots_path, data)
    before = bot.to_dict()
    assert env.manager.add_alias('farm', 'new')
    data['SandBot']['nicknames'].append('new')
    before['nicknames'].append('new')
    assert read_json(config.bots_path) == data
    assert bot.to_dict() == before


@pytest.mark.parametrize('external_change', ['delete', 'rename', 'aliases'])
def test_changed_disk_record_requires_reload_instead_of_overwriting(env, bot, external_change):
    data = read_json(config.bots_path)
    if external_change == 'delete':
        data.clear()
    elif external_change == 'rename':
        data['SANDBOT'] = data.pop('SandBot')
    else:
        data['SandBot']['nicknames'].append('external')
    write_json(config.bots_path, data)
    before = Path(config.bots_path).read_bytes()
    nicknames = bot.nicknames.copy()
    with pytest.raises(RuntimeError, match='!!bk reload'):
        env.manager.add_alias('farm', 'new')
    assert bot.nicknames == nicknames
    assert env.manager.get_bot_by_nickname('new') is None
    assert Path(config.bots_path).read_bytes() == before


def test_alias_cannot_collide_with_an_external_record_not_yet_loaded(env, bot):
    data = read_json(config.bots_path)
    data['OtherBot'] = {'nicknames': ['new']}
    write_json(config.bots_path, data)
    before = Path(config.bots_path).read_bytes()
    with pytest.raises(ValueError):
        env.manager.add_alias('farm', 'NEW')
    assert env.manager.get_bot_by_nickname('new') is None
    assert Path(config.bots_path).read_bytes() == before


def test_alias_edit_does_not_normalize_legacy_position_fields(env):
    data = {'SandBot': {'nick': 'farm', 'dim': -1, 'pos': '1 64 2', 'facing': '90 0'}}
    write_json(config.bots_path, data)
    env.manager.load()
    assert env.manager.add_alias('farm', 'new')
    del data['SandBot']['nick']
    data['SandBot']['nicknames'] = ['SandBot', 'farm', 'new']
    assert read_json(config.bots_path) == data


def test_concurrent_alias_additions_are_not_lost(env, bot):
    with ThreadPoolExecutor(max_workers=4) as pool:
        tasks = [pool.submit(env.manager.add_alias, 'SandBot', f'new{i}') for i in range(12)]
        assert all(task.result(timeout=5) for task in tasks)
    expected = {f'new{i}' for i in range(12)}
    assert expected <= set(bot.nicknames)
    assert read_json(config.bots_path)['SandBot']['nicknames'] == bot.nicknames


def test_alias_write_cannot_resurrect_a_concurrently_deleted_bot(env, bot, monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    original_write = manager_module.write_json

    def delayed_write(path, data):
        if not entered.is_set():
            entered.set()
            assert release.wait(5)
        original_write(path, data)

    monkeypatch.setattr(manager_module, 'write_json', delayed_write)
    with ThreadPoolExecutor(max_workers=2) as pool:
        try:
            edit = pool.submit(env.manager.add_alias, 'farm', 'new')
            assert entered.wait(3)
            deletion = pool.submit(env.manager.remove_bot, 'SandBot')
        finally:
            release.set()
        assert edit.result(timeout=3)
        assert deletion.result(timeout=3)
    assert read_json(config.bots_path) == {}
    assert env.manager.get_bot_by_nickname('new') is None
    assert env.manager.get_bot('SandBot') is None


@pytest.mark.parametrize('remove', [False, True])
def test_alias_edits_do_not_cancel_a_waiting_action(env, bot, remove):
    spawn_requested = threading.Event()
    env.server.on_execute = lambda text: spawn_requested.set()
    task = command.bot_action(env.source, {'nickname': 'farm'}, 'use', env.manager)
    try:
        assert spawn_requested.wait(3)
        if remove:
            assert env.manager.remove_alias('farm', 'farm')
        else:
            assert env.manager.add_alias('farm', 'new')
        assert env.manager.get_bot('SandBot') is bot
        env.manager.update_player_status('SandBot', True)
        task.result(timeout=3)
        assert env.server.commands[-1] == 'player SandBot use once'
        assert '\u5df2\u53d1\u9001' in env.source.messages[-1]
    finally:
        bot.cancel()


def test_alias_edit_preserves_pending_real_name_save(env, bot):
    release = threading.Event()
    tasks = []
    try:
        tasks = [env.manager.submit(release.wait, 10) for _ in range(4)]
        env.manager.update_player_status('SandBot', False)
        name_save = env.manager._name_save_future
        assert name_save is not None
        assert env.manager.add_alias('farm', 'new')
        assert bot.confirmed_name == 'SandBot'
        release.set()
        name_save.result(timeout=5)
        assert read_json(config.bots_path)['SandBot'] == bot.to_dict()
    finally:
        release.set()
        for task in tasks:
            task.result(timeout=5)


def test_alias_edit_during_online_query_keeps_the_snapshot_valid(env, bot, monkeypatch):
    env.server.startup = True

    def query():
        assert env.manager.add_alias('farm', 'new')
        return 1, 20, ['SandBot']

    monkeypatch.setitem(sys.modules, 'minecraft_data_api', SimpleNamespace(get_server_player_list=query))
    assert env.manager.sync_online_status()
    assert env.manager.get_bot_by_nickname('new') is bot
    assert bot.is_online
    assert bot.confirmed_name == 'SandBot'


@pytest.mark.parametrize('method', ['add_alias', 'remove_alias'])
def test_unloaded_manager_cannot_edit_aliases(env, bot, method):
    env.manager.shutdown()
    before = Path(config.bots_path).read_bytes()
    with pytest.raises(RuntimeError):
        getattr(env.manager, method)('farm', 'farm')
    assert Path(config.bots_path).read_bytes() == before
