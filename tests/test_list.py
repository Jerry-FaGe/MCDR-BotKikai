import json

import pytest

from bot_kikai import view
from bot_kikai.bot import Bot
from bot_kikai.config import config


def _nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _nodes(child)


def _text_nodes(message):
    return [node for node in _nodes(json.loads(message.to_json_str())) if 'text' in node]


def _commands(message, label=None):
    nodes = [node for node in _text_nodes(message) if 'clickEvent' in node]
    assert all(node['clickEvent']['action'] == 'suggest_command' for node in nodes)
    return [node['clickEvent']['value'] for node in nodes if label is None or node['text'] == label]


def _bots(env, count):
    bots = [Bot(env.server, f'Bot{i:03}', [], 'minecraft:overworld', [0, 64, 0], [0, 0])
            for i in range(count)]
    for index, bot in enumerate(bots):
        bot.is_online = index % 2 == 0
    return bots


@pytest.mark.parametrize('count', [0, 1, 10, 11, 20, 21])
@pytest.mark.parametrize('requested_page', [1, 2, 99])
def test_pagination_boundaries_keep_navigation_and_clamp_to_last_page(env, count, requested_page):
    bots = _bots(env, count)
    incoming = list(reversed(bots))
    page_count = max(1, (count + 9) // 10)
    page = min(requested_page, page_count)
    message = view.render_bot_list(incoming, page=requested_page)
    text = message.to_plain_text()

    assert f'\u7b2c {page}/{page_count} \u9875' in text
    assert f'\u5171 {count} \u4e2a' in text
    assert _commands(message, '[\u8be6\u60c5]') == [
        f'!!bk {bot.name}' for bot in bots[(page - 1) * 10:page * 10]
    ]
    assert incoming == list(reversed(bots))
    assert ('\u9875\u7801\u8d85\u51fa\u8303\u56f4' in text) is (requested_page > page_count)
    for label, enabled in [('[\u4e0a\u4e00\u9875]', page > 1), ('[\u4e0b\u4e00\u9875]', page < page_count)]:
        node = next(node for node in _text_nodes(message) if node['text'] == label)
        assert ('clickEvent' in node) is enabled
        assert node['color'] == ('aqua' if enabled else 'gray')
        assert 'hoverEvent' in node
    suffix = f' {page}' if page > 1 else ''
    assert _commands(message, '[\u5237\u65b0]') == [f'!!bk list{suffix}']


@pytest.mark.parametrize('status, query, names', [
    ('all', 'SAND', ['SandBot']),
    ('all', 'B_SANDBOT', ['SandBot']),
    ('all', '\u6c99', ['SandBot']),
    ('all', 'STRASSE', ['SandBot']),
    ('all', 'fArM', ['IronBot', 'SandBot']),
    ('online', 'farm', ['SandBot']),
    ('offline', 'farm', ['IronBot']),
    ('offline', 'SAND', []),
    ('all', 'online', ['IronBot']),
    ('all', '2', ['IronBot']),
    ('all', 'missing', []),
])
def test_search_matches_all_identities_and_aliases_with_status_filter(env, status, query, names):
    config.bot_name_prefix = 'b_'
    sand = Bot(env.server, 'SandBot', ['farm', '\u5237\u6c99\u673a', 'Stra\u00dfe'],
               'minecraft:overworld', [0, 64, 0], [0, 0], confirmed_name='b_SandBot')
    iron = Bot(env.server, 'IronBot', ['farm-2', 'online'], 'minecraft:the_nether', [0, 64, 0], [0, 0])
    sand.is_online = True
    message = view.render_bot_list([sand, iron], status=status, query=query)

    assert _commands(message, '[\u8be6\u60c5]') == [f'!!bk {name}' for name in names]
    assert f'\u641c\u7d22: {query}' in message.to_plain_text()
    assert f'\u5171 {len(names)} \u4e2a' in message.to_plain_text()
    assert env.server.commands == []


def test_filtering_precedes_pagination_and_each_record_is_returned_once(env):
    bots = _bots(env, 42)
    for bot in bots:
        bot.nicknames += ['farm', 'farmland']
    message = view.render_bot_list(bots, status='online', query='FARM', page=2)
    assert '\u7b2c 2/3 \u9875' in message.to_plain_text()
    assert '\u5171 21 \u4e2a' in message.to_plain_text()
    assert _commands(message, '[\u8be6\u60c5]') == [f'!!bk Bot{i:03}' for i in range(20, 40, 2)]


def test_order_depends_on_registered_name_not_status_or_alias(env):
    bots = [Bot(env.server, name, [alias], 'minecraft:overworld', [0, 64, 0], [0, 0])
            for name, alias in [('zBot', 'aaa'), ('Alpha', 'zzz'), ('bravo', '\u5237\u6c99\u673a')]]
    expected = ['!!bk Alpha', '!!bk bravo', '!!bk zBot']
    assert _commands(view.render_bot_list(bots), '[\u8be6\u60c5]') == expected
    bots[0].is_online = True
    bots[1].nicknames = ['Alpha', 'first']
    assert _commands(view.render_bot_list(bots), '[\u8be6\u60c5]') == expected


def test_online_snapshot_is_shared_by_filter_status_and_actions(env, bot, monkeypatch):
    reads = []

    def changing_status(self):
        reads.append(self.name)
        return len(reads) == 1

    monkeypatch.setattr(Bot, 'is_online', property(changing_status))
    message = view.render_bot_list([bot], status='online')
    assert reads == ['SandBot']
    assert '[\u5728\u7ebf] farm' in message.to_plain_text()
    assert _commands(message, '[\u53f3\u952e]') == ['!!bk SandBot use']
    assert _commands(message, '[\u4e0b\u7ebf]') == ['!!bk SandBot kill']
    assert _commands(message, '[\u4e0a\u7ebf]') == []


@pytest.mark.parametrize('name', ['long-label-' * 10, '\u8d85\u957f\u673a\u5668\u540d\u79f0' * 10])
def test_long_labels_are_shortened_only_in_visible_text(env, name):
    bot = Bot(env.server, 'SandBot', [name, 'farm'], 'example:custom/room',
              [12.3456789, 64, -0.0049], [180, 0], confirmed_name='SandBot')
    before = bot.to_dict()
    message = view.render_bot_summary(bot)
    label = next(node for node in _text_nodes(message) if node.get('color') == 'gold')
    assert label['text'] == name[:7] + '\u2026'
    hover = json.dumps(label['hoverEvent'], ensure_ascii=False)
    assert name in hover
    assert 'SandBot' in hover
    assert 'farm' in hover
    assert 'example:custom/room' in hover
    assert '\u767b\u8bb0\u4f4d\u7f6e:' in hover
    assert '\u4e0d\u662f\u5b9e\u65f6\u4f4d\u7f6e' in hover
    assert '\n' not in message.to_plain_text()
    assert _commands(message) == ['!!bk SandBot spawn', '!!bk SandBot use', '!!bk SandBot']
    assert bot.to_dict() == before


@pytest.mark.parametrize('name', [
    'abcdef', 'abcdefg', 'abcdefgh',
    '\u673a' * 6, '\u673a' * 7, '\u673a' * 8,
    'farm\u673a\u5668\u4eba', 'farm\u673a\u5668\u4eba\u5854',
])
def test_list_names_keep_seven_characters_before_ellipsis(env, name):
    bot = Bot(env.server, 'SandBot', [name], 'minecraft:overworld', [0, 64, 0], [0, 0])
    message = view.render_bot_summary(bot)
    expected = name if len(name) <= 7 else name[:7] + '\u2026'
    assert message.to_plain_text().startswith(f'[\u79bb\u7ebf] {expected} ')
    label = next(node for node in _text_nodes(message) if node.get('color') == 'gold')
    assert name in json.dumps(label['hoverEvent'], ensure_ascii=False)
    assert name in view.render_bot_info(bot).to_plain_text()


def test_long_query_is_preserved_in_navigation_and_hover(env, bot):
    query = '\u5237\u6c99\u673a' * 20
    message = view.render_bot_list([bot], query=query)
    assert query not in message.to_plain_text()
    assert query in json.dumps(json.loads(message.to_json_str()), ensure_ascii=False)
    assert _commands(message, '[\u5728\u7ebf]') == [f'!!bk list online search {query}']
    assert _commands(message, '[\u5237\u65b0]') == [f'!!bk list search {query}']


@pytest.mark.parametrize('aliases, label', [
    (['SANDBOT', 'b_SANDBOT', '\u5237\u6c99\u673a', 'farm'], '\u5237\u6c99\u673a'),
    (['SANDBOT', 'b_SANDBOT'], 'SandBot'),
    ([], 'SandBot'),
])
def test_list_display_name_uses_existing_alias_order(env, aliases, label):
    config.bot_name_prefix = 'b_'
    bot = Bot(env.server, 'SandBot', aliases, 'minecraft:overworld', [0, 64, 0], [0, 0])
    before = bot.nicknames.copy()
    assert view.render_bot_summary(bot).to_plain_text().startswith(f'[\u79bb\u7ebf] {label} ')
    assert bot.nicknames == before


@pytest.mark.parametrize('online', [False, True])
@pytest.mark.parametrize('can_operate', [False, True])
def test_compact_rows_only_offer_permitted_shortcuts_with_semantic_colors(env, bot, online, can_operate):
    bot.is_online = online
    message = view.render_bot_summary(bot, can_operate=can_operate)
    buttons = {node['text']: node for node in _text_nodes(message) if 'clickEvent' in node}
    expected = {}
    if can_operate:
        expected.update({'[\u4e0b\u7ebf]': 'red'} if online else {'[\u4e0a\u7ebf]': 'green'})
        expected['[\u53f3\u952e]'] = 'aqua'
    expected['[\u8be6\u60c5]'] = 'aqua'
    assert list(buttons) == list(expected)
    assert {label: node['color'] for label, node in buttons.items()} == expected
    assert '\n' not in message.to_plain_text()
    if can_operate:
        hover = json.dumps(buttons['[\u53f3\u952e]']['hoverEvent'], ensure_ascii=False)
        assert '\u79bb\u7ebf\u65f6\u4f1a\u5148\u81ea\u52a8\u53ec\u5524' in hover


@pytest.mark.parametrize('status, query', [('all', None), ('online', None), ('offline', None), ('online', 'missing')])
@pytest.mark.parametrize('count', [0, 1, 12])
def test_lists_use_explicit_colors_and_suggestions_even_for_empty_results(env, status, query, count):
    message = view.render_bot_list(_bots(env, count), status=status, query=query, page=2, can_operate=False)
    nodes = [node for node in _text_nodes(message) if node['text'].strip()]
    assert nodes
    assert all('color' in node and '\u00a7' not in node['text'] for node in nodes)
    active = next(node for node in nodes if node['text'] == f'[{view._LIST_STATUSES[status]}]')
    assert active['color'] == 'gold'
    assert 'clickEvent' not in active
    assert '[\u5237\u65b0]' in message.to_plain_text()
    assert all(' use' not in cmd and ' spawn' not in cmd and ' kill' not in cmd for cmd in _commands(message))
    assert ('[\u6e05\u9664\u641c\u7d22]' in message.to_plain_text()) is (query is not None)


def test_empty_filtered_results_distinguish_no_matches_from_no_records(env, bot):
    online = view.render_bot_list([bot], status='online')
    searched = view.render_bot_list([bot], status='online', query='nothing')
    empty = view.render_bot_list([], status='online', query='nothing')
    assert '\u6ca1\u6709\u5728\u7ebf\u5047\u4eba' in online.to_plain_text()
    assert '\u6ca1\u6709\u627e\u5230\u7b26\u5408\u6761\u4ef6\u7684\u5047\u4eba' in searched.to_plain_text()
    assert '\u5c1a\u672a\u767b\u8bb0\u5047\u4eba' in empty.to_plain_text()
    assert _commands(searched, '[\u6e05\u9664\u641c\u7d22]') == ['!!bk list online']
    assert _commands(online, '[\u5168\u90e8]') == ['!!bk list']
    assert _commands(empty, '[\u5e2e\u52a9]') == ['!!bk']
    for message in (online, searched, empty):
        assert '\u7b2c 1/1 \u9875' in message.to_plain_text()
        assert '\u5171 0 \u4e2a' in message.to_plain_text()


@pytest.mark.parametrize('options', [
    {'page': 0}, {'page': -1}, {'page': 1.5}, {'page': True}, {'status': 'unknown'},
    {'query': ''}, {'query': 'two words'}, {'query': 'line\nbreak'}, {'query': 'tab\t'}, {'query': '\x00'},
])
def test_renderer_rejects_invalid_list_options(env, options):
    with pytest.raises(ValueError):
        view.render_bot_list([], **options)
