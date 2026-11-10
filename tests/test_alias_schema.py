from pathlib import Path

import pytest

from bot_kikai import view
from bot_kikai.config import config
from bot_kikai.storage import read_json, write_json


@pytest.mark.parametrize('record', [{}, {'aliases': []}])
def test_record_without_aliases_keeps_both_identities_and_display_name(env, record):
    write_json(config.config_path, {'bot_name_prefix': 'b_', 'bot_name_suffix': '_m'})
    write_json(config.bots_path, {'SandBot': record})
    env.manager.reload_config()
    bot = env.manager.get_bot('SandBot')
    assert bot.aliases == []
    assert env.manager.resolve_bot('SANDBOT') is bot
    assert env.manager.resolve_bot('B_SandBot_M') is bot
    assert view.render_feedback('ok', bot=bot).to_plain_text() == '[BK] SandBot · ok'
    env.manager.save()
    env.manager.load()
    assert read_json(config.bots_path)['SandBot']['aliases'] == []
    assert env.manager.resolve_bot('b_sandbot_m') is env.manager.get_bot('SandBot')


def test_aliases_store_only_extra_names_in_first_occurrence_order(env):
    write_json(config.config_path, {'bot_name_prefix': 'b_'})
    write_json(config.bots_path, {'SandBot': {
        'aliases': ['SANDBOT', 'B_SandBot', '刷沙机', 'sandbot', 'Straße', 'STRASSE', 'farm', '刷沙机'],
    }})
    env.manager.reload_config()
    bot = env.manager.get_bot('SandBot')
    assert bot.aliases == ['刷沙机', 'Straße', 'farm']
    for target in ['sandbot', 'B_SANDBOT', '刷沙机', 'strasse', 'FARM']:
        assert env.manager.resolve_bot(target) is bot
    assert view.render_feedback('ok', bot=bot).to_plain_text() == '[BK] 刷沙机 · ok'
    env.manager.save()
    assert read_json(config.bots_path)['SandBot']['aliases'] == ['刷沙机', 'Straße', 'farm']
    for alias in ['刷沙机', 'STRASSE', 'farm']:
        assert env.manager.remove_alias('b_sandbot', alias)
    env.manager.load()
    bot = env.manager.resolve_bot('sandbot')
    assert bot.aliases == []
    assert env.manager.resolve_bot('b_sandbot') is bot
    assert view.render_feedback('ok', bot=bot).to_plain_text() == '[BK] SandBot · ok'


@pytest.mark.parametrize('legacy', [
    {'nicknames': ['SandBot', 'farm']}, {'nick': ['SandBot', 'farm']}, {'nick': 'farm'},
])
def test_legacy_aliases_are_read_and_only_edited_record_is_converted(env, legacy):
    record = {**legacy, 'dim': -1, 'pos': '1 64 2', 'facing': '90 0', 'note': 'keep me'}
    other = {'nicknames': ['OtherBot', 'other'], 'position': [9, 70, 8]}
    write_json(config.bots_path, {'SandBot': record, 'OtherBot': other})
    before = Path(config.bots_path).read_bytes()
    env.manager.load()
    bot = env.manager.resolve_bot('FARM')
    assert bot.aliases == ['farm']
    assert Path(config.bots_path).read_bytes() == before
    assert env.manager.add_alias('farm', '刷沙机')
    saved = read_json(config.bots_path)
    assert saved['SandBot'] == {
        'aliases': ['farm', '刷沙机'], 'dim': -1, 'pos': '1 64 2', 'facing': '90 0', 'note': 'keep me',
    }
    assert saved['OtherBot'] == other
    env.manager.load()
    assert env.manager.resolve_bot('刷沙机').position == [1, 64, 2]
    assert env.manager.resolve_bot('other').name == 'OtherBot'
    env.manager.save()
    saved = read_json(config.bots_path)
    assert saved['OtherBot']['aliases'] == ['other']
    assert all('nicknames' not in value and 'nick' not in value for value in saved.values())


@pytest.mark.parametrize('aliases', [[], ['current']])
def test_explicit_aliases_take_precedence_over_legacy_fields(env, aliases):
    record = {'aliases': aliases, 'nicknames': ['SandBot', 'stale'], 'nick': 'older'}
    write_json(config.bots_path, {'SandBot': record})
    env.manager.load()
    bot = env.manager.get_bot('SandBot')
    assert bot.aliases == aliases
    assert env.manager.resolve_bot('stale') is None
    assert env.manager.resolve_bot('older') is None
    assert env.manager.add_alias('sandbot', 'new')
    assert env.manager.remove_alias('sandbot', 'new')
    env.manager.load()
    assert env.manager.get_bot('SandBot').aliases == aliases
    assert read_json(config.bots_path)['SandBot'] == {'aliases': aliases}


@pytest.mark.parametrize('record', [
    {'aliases': None, 'nicknames': ['farm']},
    {'aliases': 'farm', 'nicknames': ['fallback']},
    {'nicknames': 'farm', 'nick': 'fallback'},
])
def test_invalid_current_field_does_not_fall_back_to_legacy_fields(env, record):
    write_json(config.bots_path, {'SandBot': record})
    before = Path(config.bots_path).read_bytes()
    with pytest.raises(ValueError):
        env.manager.load()
    assert not env.manager.bots
    assert Path(config.bots_path).read_bytes() == before


def test_name_confirmation_preserves_legacy_alias_fields_until_they_are_edited(env):
    record = {'nicknames': ['SandBot', 'farm'], 'position': [1, 64, 2]}
    write_json(config.bots_path, {'SandBot': record})
    env.manager.load()
    env.manager.update_player_status('SandBot', True)
    env.manager.shutdown()
    assert read_json(config.bots_path) == {'SandBot': {**record, 'confirmed_name': 'SandBot'}}
