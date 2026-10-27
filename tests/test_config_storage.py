import json
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


def test_first_install_does_not_log_migration_error(env, caplog):
    assert 'ERROR' not in caplog.text
    assert Path(config.config_path).is_file()


def test_migration_keeps_backup_and_resumes_after_partial_write(env):
    old = {'SandBot': {'nicknames': ['farm'], 'position': [1, 64, 2]}}
    storage.write_json(config.config_path, old)
    storage.write_json(config.bots_path, old)
    original = Path(config.config_path).read_bytes()
    Path(config.config_path + '.bak').write_bytes(original)
    config.init(env.server)
    assert storage.read_json(config.bots_path) == old
    assert storage.read_json(config.config_path) == Config().to_dict()
    assert Path(config.config_path + '.bak').read_bytes() == original


def test_migration_does_not_overwrite_existing_bots(env):
    old = {'SandBot': {'nicknames': ['farm']}}
    existing = {'OtherBot': {'nicknames': ['other']}}
    storage.write_json(config.config_path, old)
    storage.write_json(config.bots_path, existing)
    with pytest.raises(ValueError):
        config.init(env.server)
    assert storage.read_json(config.config_path) == old
    assert storage.read_json(config.bots_path) == existing


def test_migration_does_not_replace_an_older_backup(env):
    Path(config.bots_path).unlink()
    old = {'SandBot': {'nick': 'farm'}}
    storage.write_json(config.config_path, old)
    backup = Path(config.config_path + '.bak')
    backup.write_text('older backup', encoding='utf8')
    config.init(env.server)
    assert backup.read_text(encoding='utf8') == 'older backup'
    assert json.loads(Path(config.config_path + '.bak.1').read_text(encoding='utf8')) == old
