from pathlib import Path

import pytest

from bot_kikai import storage
from bot_kikai.config import Config, config


def test_partial_permissions_use_defaults():
    assert Config.from_dict({'permission': {'bot': 2}}).permission == {'bot': 2, 'list': 3}


@pytest.mark.parametrize('data', [
    [], {'server': None}, {'config_path': 'somewhere'}, {'prefix_short': ''},
    {'prefix_short': '!!two words'}, {'prefix_short': '!!bad\x00'},
    {'spawn_check_interval': 0}, {'spawn_check_interval': -1},
    {'spawn_max_wait_time': float('inf')}, {'spawn_max_wait_time': float('nan')},
    {'spawn_max_wait_time': True}, {'spawn_max_wait_time': '10'}, {'spawn_max_wait_time': 10 ** 1000},
    {'permission': None}, {'permission': {'list': -1}},
    {'permission': {'bot': 5}}, {'permission': {'bot': True}},
    {'permission': {'other': 1}}, {'bot_name_prefix': '@'},
    {'bot_name_suffix': 'x' * 16},
])
def test_invalid_config_is_rejected(data):
    with pytest.raises(ValueError):
        Config.from_dict(data)


def test_bad_json_preserves_file_and_settings(env):
    path = Path(config.config_path)
    original = '{"prefix_short": "!!farm",'
    path.write_text(original, encoding='utf8')
    before = config.to_dict()
    with pytest.raises(ValueError):
        config.load()
    assert path.read_text(encoding='utf8') == original
    assert config.to_dict() == before


def test_invalid_field_does_not_partially_apply(env):
    storage.write_json(config.config_path, {'prefix_short': '!!farm', 'permission': {'bot': -1}})
    with pytest.raises(ValueError):
        config.load()
    assert config.prefix_short == '!!bk'
    assert config.permission == {'bot': 1, 'list': 3}


def test_atomic_write_preserves_original_if_serialization_fails(tmp_path):
    path = tmp_path / 'bots.json'
    storage.write_json(path, {'original': True})
    before = path.read_bytes()
    with pytest.raises(ValueError):
        storage.write_json(path, {'bad': float('nan')})
    assert path.read_bytes() == before
    assert list(tmp_path.glob('*.tmp')) == []


def test_atomic_write_preserves_original_if_replace_fails(tmp_path, monkeypatch):
    path = tmp_path / 'bots.json'
    storage.write_json(path, {'original': True})
    before = path.read_bytes()

    def fail(*args):
        raise OSError('disk unavailable')

    monkeypatch.setattr(storage.os, 'replace', fail)
    with pytest.raises(OSError):
        storage.write_json(path, {'replacement': True})
    assert path.read_bytes() == before
    assert list(tmp_path.glob('*.tmp')) == []


def test_json_round_trip_does_not_rewrite_string_whitespace(tmp_path):
    path = tmp_path / 'data.json'
    data = {'nicknames': ['a  b', 'hello [  world  ]'], 'position': [1, 2, 3]}
    storage.write_json(path, data)
    assert storage.read_json(path) == data


def test_first_install_creates_default_files_without_backups(env, caplog):
    assert 'ERROR' not in caplog.text
    assert storage.read_json(config.config_path) == Config().to_dict()
    assert storage.read_json(config.bots_path) == {}
    assert {path.name for path in env.path.iterdir()} == {'config.json', 'bots.json'}


@pytest.mark.parametrize('record', [
    {'nicknames': ['farm'], 'position': [1, 64, 2]},
    {'nick': 'farm', 'dim': -1, 'pos': '1 64 2', 'facing': '90 0'},
])
@pytest.mark.parametrize('bots_state', ['missing', 'same', 'different', 'invalid'])
@pytest.mark.parametrize('has_backups', [False, True])
def test_old_config_layout_is_rejected_without_touching_files(env, record, bots_state, has_backups):
    old = {'SandBot': record}
    storage.write_json(config.config_path, old)
    if bots_state == 'missing':
        Path(config.bots_path).unlink()
    elif bots_state == 'same':
        storage.write_json(config.bots_path, old)
    elif bots_state == 'different':
        storage.write_json(config.bots_path, {'OtherBot': {'nicknames': ['other']}})
    else:
        Path(config.bots_path).write_text('{', encoding='utf8')
    if has_backups:
        Path(config.config_path + '.bak').write_bytes(b'older backup')
        Path(config.config_path + '.bak.1').write_bytes(Path(config.config_path).read_bytes())
    config.spawn_max_wait_time = 5.0
    settings = config.to_dict()
    before = {path.name: path.read_bytes() for path in env.path.iterdir()}

    with pytest.raises(ValueError, match=r'v0\.6\.0.*bots\.json'):
        config.init(env.server)

    assert config.to_dict() == settings
    assert {path.name: path.read_bytes() for path in env.path.iterdir()} == before


@pytest.mark.parametrize('mixed_settings', [False, True])
def test_old_config_layout_reload_keeps_current_settings_and_bots(env, bot, mixed_settings):
    bot.is_online = True
    data = {'SandBot': bot.to_dict()}
    if mixed_settings:
        data['spawn_max_wait_time'] = 2.0
    storage.write_json(config.config_path, data)
    before = {path.name: path.read_bytes() for path in env.path.iterdir()}
    settings = config.to_dict()

    with pytest.raises(ValueError, match=r'v0\.6\.0.*bots\.json'):
        env.manager.reload_config()

    assert config.to_dict() == settings
    assert env.manager.get_bot('SandBot') is bot
    assert bot.is_online
    assert bot.kill()
    assert {path.name: path.read_bytes() for path in env.path.iterdir()} == before


def test_split_config_keeps_legacy_bot_fields_and_existing_backups(env):
    storage.write_json(config.config_path, {'spawn_max_wait_time': 5.0})
    data = {'SandBot': {'nick': 'farm', 'dim': -1, 'pos': '1 64 2', 'facing': '90 0'}}
    storage.write_json(config.bots_path, data)
    Path(config.config_path + '.bak').write_bytes(b'older backup')
    before = {path.name: path.read_bytes() for path in env.path.iterdir()}

    config.init(env.server)
    env.manager.load()

    bot = env.manager.get_bot('SandBot')
    assert config.spawn_max_wait_time == 5.0
    assert bot.nicknames == ['SandBot', 'farm']
    assert bot.dimension == 'minecraft:the_nether'
    assert bot.position == [1, 64, 2]
    assert bot.facing == [90, 0]
    assert bot.confirmed_name is None
    assert {path.name: path.read_bytes() for path in env.path.iterdir()} == before
