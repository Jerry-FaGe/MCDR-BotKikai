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
from bot_kikai.config import config
from bot_kikai.storage import read_json, write_json


def test_reload_preserves_online_and_applies_deletions(env, bot):
    env.manager.update_player_status(bot.real_name, True)
    env.manager.upsert_bot('OtherBot', 'other', 'minecraft:overworld', [0, 64, 0], [0, 0])
    write_json(config.bots_path, {'SandBot': bot.to_dict()})
    env.manager.reload_config()
    current = env.manager.get_bot('SandBot')
    assert current is not bot
    assert current.is_online
    assert env.manager.get_bot('OtherBot') is None
    assert not bot.use()


def test_affix_reload_does_not_transfer_online_to_a_different_player(env, bot):
    env.manager.update_player_status(bot.real_name, True)
    write_json(config.config_path, {'bot_name_prefix': 'b_'})
    env.manager.reload_config()
    assert bot.real_name == 'sandbot'
    current = env.manager.get_bot('SandBot')
    assert current.real_name == 'b_sandbot'
    assert not current.is_online


@pytest.mark.parametrize('bad_data', ['{', '[]', '{"BadBot": null}', '{"BadBot": {"position": [1]}}'])
def test_failed_reload_keeps_state_and_blocks_overwriting_bad_data(env, bot, bad_data):
    bot.is_online = True
    write_json(config.config_path, {'permission': {'bot': 2}})
    Path(config.bots_path).write_text(bad_data, encoding='utf8')
    with pytest.raises(ValueError):
        env.manager.reload_config()
    assert env.manager.get_bot('SandBot') is bot
    assert bot.is_online
    assert config.permission['bot'] == 1
    with pytest.raises(RuntimeError):
        env.manager.remove_bot('SandBot')
    with pytest.raises(RuntimeError):
        env.manager.save()
    assert Path(config.bots_path).read_text(encoding='utf8') == bad_data
    write_json(config.bots_path, {'SandBot': bot.to_dict()})
    env.manager.reload_config()
    assert config.permission['bot'] == 2
    assert env.manager.remove_bot('SandBot')


def test_bad_data_prevents_initial_manager_loading(env):
    Path(config.bots_path).write_text('{', encoding='utf8')
    with pytest.raises(ValueError):
        BotManager(env.server)
    assert Path(config.bots_path).read_text(encoding='utf8') == '{'


def test_corrupt_file_is_not_overwritten_even_without_reloading(env, bot):
    Path(config.bots_path).write_text('{', encoding='utf8')
    with pytest.raises(ValueError):
        env.manager.upsert_bot('NewBot', 'new', 'minecraft:overworld', [0, 64, 0], [0, 0])
    assert Path(config.bots_path).read_text(encoding='utf8') == '{'
    assert env.manager.get_bot('SandBot') is bot
    assert env.manager.get_bot('NewBot') is None


def test_missing_file_during_reload_is_not_recreated(env, bot):
    Path(config.bots_path).unlink()
    with pytest.raises(OSError):
        env.manager.load()
    assert env.manager.get_bot('SandBot') is bot
    assert not Path(config.bots_path).exists()


def test_save_failure_does_not_change_memory_or_retire_bot(env, bot, monkeypatch):
    before = Path(config.bots_path).read_bytes()

    def fail(*args):
        raise OSError('disk full')

    monkeypatch.setattr(manager_module, 'write_json', fail)
    with pytest.raises(OSError):
        env.manager.upsert_bot('SandBot', 'second', 'minecraft:the_nether', [8, 64, 8], [0, 0])
    assert env.manager.get_bot('SandBot') is bot
    assert bot.dimension == 'minecraft:overworld'
    assert bot.kill()
    assert Path(config.bots_path).read_bytes() == before


def test_save_cannot_overwrite_a_newer_delete(env, bot, monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    real_write = manager_module.write_json

    def delayed_write(path, data):
        if threading.current_thread().name == 'old-save':
            entered.set()
            assert release.wait(3)
        real_write(path, data)

    monkeypatch.setattr(manager_module, 'write_json', delayed_write)
    writer = threading.Thread(target=env.manager.save, name='old-save')
    writer.start()
    assert entered.wait(3)
    with ThreadPoolExecutor(max_workers=1) as pool:
        deletion = pool.submit(env.manager.remove_bot, bot.name)
        release.set()
        assert deletion.result(timeout=3)
    writer.join(3)
    assert not writer.is_alive()
    assert read_json(config.bots_path) == {}
    assert env.manager.get_bot(bot.name) is None


def test_concurrent_updates_merge_nicknames_without_losing_any(env, bot):
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(env.manager.upsert_bot, 'SandBot', f'alias{i}',
                               'minecraft:overworld', [i, 64, 0], [0, 0]) for i in range(20)]
        for future in futures:
            future.result(timeout=5)
    expected = {f'alias{i}' for i in range(20)}
    assert expected <= set(env.manager.get_bot('SandBot').nicknames)
    assert expected <= set(read_json(config.bots_path)['SandBot']['nicknames'])


@pytest.mark.parametrize('name,alias', [('sandbot', 'other'), ('OtherBot', 'farm'), ('OtherBot', 'SANDBOT'), ('list', 'other')])
def test_name_and_alias_collisions_are_rejected(env, bot, name, alias):
    before = Path(config.bots_path).read_bytes()
    with pytest.raises(ValueError):
        env.manager.upsert_bot(name, alias, 'minecraft:overworld', [0, 64, 0], [0, 0])
    assert Path(config.bots_path).read_bytes() == before
    assert len(env.manager.bots) == 1


def test_real_names_work_without_writing_aliases_on_join(env, bot):
    write_json(config.config_path, {'bot_name_prefix': 'b_'})
    env.manager.reload_config()
    before = Path(config.bots_path).read_bytes()
    bot_kikai.bot_manager_instance = env.manager
    bot_kikai.on_player_joined(env.server, 'b_SandBot', None)
    current = env.manager.get_bot_by_nickname('B_SANDBOT')
    assert current.is_online
    assert Path(config.bots_path).read_bytes() == before


def test_sync_discovers_already_online_bots(env, bot, monkeypatch):
    env.server.startup = True
    monkeypatch.setitem(sys.modules, 'minecraft_data_api', SimpleNamespace(
        get_server_player_list=lambda: (1, 20, ['SandBot']),
    ))
    assert env.manager.request_sync().result(timeout=3)
    assert bot.is_online


def test_sync_cannot_overwrite_newer_player_events(env, bot, monkeypatch):
    env.server.startup = True
    bot.is_online = True

    def query():
        env.manager.update_player_status('sandbot', False)
        return 1, 20, ['SandBot']

    monkeypatch.setitem(sys.modules, 'minecraft_data_api', SimpleNamespace(get_server_player_list=query))
    assert env.manager.sync_online_status()
    assert not bot.is_online


def test_timed_out_sync_keeps_current_status(env, bot, monkeypatch):
    env.server.startup = True
    bot.is_online = True
    monkeypatch.setitem(sys.modules, 'minecraft_data_api', SimpleNamespace(get_server_player_list=lambda: None))
    assert not env.manager.sync_online_status()
    assert bot.is_online


def test_unloaded_manager_cannot_save_or_accept_tasks(env, bot):
    before = Path(config.bots_path).read_bytes()
    env.manager.shutdown()
    with pytest.raises(RuntimeError):
        env.manager.save()
    with pytest.raises(RuntimeError):
        env.manager.submit(lambda: None)
    assert not bot.kill()
    assert Path(config.bots_path).read_bytes() == before


def test_background_queue_is_bounded(env):
    release = threading.Event()
    futures = []
    try:
        futures = [env.manager.submit(release.wait, 3) for _ in range(env.manager.MAX_PENDING_TASKS)]
        with pytest.raises(RuntimeError):
            env.manager.submit(lambda: None)
    finally:
        release.set()
        for future in futures:
            future.result(timeout=5)


def test_old_generation_cannot_commit_after_reload(env, bot):
    generation = env.manager.generation
    env.manager.reload_config()
    with pytest.raises(RuntimeError):
        env.manager.upsert_bot('OtherBot', 'other', 'minecraft:overworld', [0, 64, 0], [0, 0], generation)
    assert env.manager.get_bot('OtherBot') is None


@pytest.mark.parametrize('data', [
    {'position': [1]}, {'facing': [0, float('nan')]}, {'dimension': 'invalid'},
    {'nicknames': 'not a list'}, {'nicknames': ['two words']},
    {'position': [True, 64, 0]}, {'dimension': '@a'}, {'position': [10 ** 1000, 64, 0]},
])
def test_invalid_bot_data_is_rejected(env, data):
    with pytest.raises(ValueError):
        Bot.from_dict(env.server, 'TestBot', data)


def test_legacy_data_fields_are_supported(env):
    bot = Bot.from_dict(env.server, 'TestBot', {'nick': 'farm', 'dim': -1, 'pos': '1 64 2', 'facing': '90 0'})
    assert bot.nicknames == ['TestBot', 'farm']
    assert bot.dimension == 'minecraft:the_nether'
    assert bot.position == [1, 64, 2]
