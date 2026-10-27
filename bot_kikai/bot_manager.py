import threading
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from mcdreforged.api.types import PluginServerInterface

from .bot import Bot
from .config import Config, config
from .storage import read_json, write_json


class BotManager:
    MAX_PENDING_TASKS = 32

    def __init__(self, server: PluginServerInterface):
        self.server = server
        self.bots: dict[str, Bot] = {}
        self._lock = threading.RLock()
        self._aliases: dict[str, Bot] = {}
        self._real_names: dict[str, Bot] = {}
        self._status_versions: dict[Bot, int] = {}
        self._generation = 0
        self._closed = False
        self._write_blocked = False
        self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='botkikai')
        self._slots = threading.BoundedSemaphore(self.MAX_PENDING_TASKS)
        self._tasks: set[Future] = set()
        if not config.bots_path:
            raise RuntimeError('假人数据路径尚未初始化')
        if not Path(config.bots_path).exists():
            write_json(config.bots_path, {})
        self.load()

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    def is_active(self, generation: int | None = None) -> bool:
        with self._lock:
            return not self._closed and (generation is None or generation == self._generation)

    def _check_active(self, generation: int | None = None) -> None:
        if not self.is_active(generation):
            raise RuntimeError('操作已因重载、卸载或服务器停止而取消')

    def _check_writable(self) -> None:
        self._check_active()
        if self._write_blocked:
            raise RuntimeError('bots.json 加载失败，已暂停写入；请修复文件后重载')

    @staticmethod
    def _indexes(bots: dict[str, Bot]) -> tuple[dict[str, Bot], dict[str, Bot]]:
        aliases: dict[str, Bot] = {}
        real_names: dict[str, Bot] = {}
        for bot in bots.values():
            for name in [bot.name, bot.real_name, *bot.nicknames]:
                key = name.casefold()
                if key in {'add', 'del', 'list', 'reload'}:
                    raise ValueError(f'{bot.name}: 名称或别名 {name!r} 与管理命令冲突')
                if key in aliases and aliases[key] is not bot:
                    raise ValueError(f'名称或别名 {name!r} 同时属于 {aliases[key].name} 和 {bot.name}')
                aliases[key] = bot
            real_names[bot.real_name.casefold()] = bot
        return aliases, real_names

    def _read_bots(self, settings: Config) -> dict[str, Bot]:
        try:
            data = read_json(config.bots_path)
            if not isinstance(data, dict):
                raise ValueError('bots.json 必须是 JSON 对象')
            bots = {name: Bot.from_dict(self.server, name, value, settings) for name, value in data.items()}
            self._indexes(bots)
            return bots
        except (OSError, ValueError):
            self._write_blocked = True
            raise

    def _install(self, bots: dict[str, Bot]) -> None:
        aliases, real_names = self._indexes(bots)
        online_names = {bot.real_name.casefold() for bot in self.bots.values() if bot.is_online}
        for name, old_bot in self.bots.items():
            if bots.get(name) is not old_bot:
                old_bot.cancel()
        for bot in bots.values():
            if bot.real_name.casefold() in online_names:
                bot.is_online = True
        self._status_versions = {bot: self._status_versions.get(bot, 0) for bot in bots.values()}
        self.bots = bots
        self._aliases = aliases
        self._real_names = real_names

    def load(self) -> None:
        with self._lock:
            self._check_active()
            bots = self._read_bots(config)
            self._install(bots)
            self._generation += 1
            self._write_blocked = False

    def reload_config(self) -> None:
        with self._lock:
            self._check_active()
            settings = config.read()
            if settings.prefix_short != config.prefix_short:
                raise ValueError('修改命令前缀后请执行 !!MCDR plugin reload bot_kikai；当前配置未应用')
            bots = self._read_bots(settings)
            config.apply(settings)
            self._install(bots)
            self._generation += 1
            self._write_blocked = False

    def _persist(self, bots: dict[str, Bot]) -> None:
        self._check_writable()
        self._read_bots(config)
        write_json(config.bots_path, {name: bot.to_dict() for name, bot in bots.items()})

    def save(self) -> None:
        with self._lock:
            self._persist(self.bots)

    def _commit(self, bots: dict[str, Bot]) -> None:
        self._indexes(bots)
        self._persist(bots)
        self._install(bots)

    def add_bot(self, bot: Bot) -> None:
        with self._lock:
            self._commit({**self.bots, bot.name: bot})

    def upsert_bot(self, name: str, nickname: str, dimension: str, position, facing,
                   generation: int | None = None) -> bool:
        with self._lock:
            self._check_active(generation)
            old_bot = self.bots.get(name)
            nicknames = old_bot.nicknames.copy() if old_bot else [name]
            if nickname not in nicknames:
                nicknames.append(nickname)
            bot = Bot(self.server, name, nicknames, dimension, position, facing)
            self._commit({**self.bots, name: bot})
            return old_bot is None

    def remove_bot(self, name: str) -> bool:
        with self._lock:
            self._check_writable()
            if name not in self.bots:
                return False
            bots = self.bots.copy()
            del bots[name]
            self._commit(bots)
            return True

    def get_bot(self, name: str) -> Bot | None:
        with self._lock:
            return self.bots.get(name)

    def get_bot_by_nickname(self, nickname: str, generation: int | None = None) -> Bot | None:
        with self._lock:
            self._check_active(generation)
            return self._aliases.get(nickname.casefold())

    def get_bot_by_real_name(self, real_name: str) -> Bot | None:
        """通过假人的真实游戏名（带前后缀）查找 Bot 对象"""
        with self._lock:
            return self._real_names.get(real_name.casefold())

    def get_all_bots(self) -> list[Bot]:
        with self._lock:
            return list(self.bots.values())

    def get_online_bots(self) -> list[Bot]:
        return [bot for bot in self.get_all_bots() if bot.is_online]

    def get_offline_bots(self) -> list[Bot]:
        return [bot for bot in self.get_all_bots() if not bot.is_online]

    def set_bot_online(self, name: str):
        with self._lock:
            bot = self.bots.get(name)
            if bot:
                self._set_online(bot, True)

    def set_bot_offline(self, name: str):
        with self._lock:
            bot = self.bots.get(name)
            if bot:
                self._set_online(bot, False)

    def _set_online(self, bot: Bot, online: bool) -> None:
        bot.is_online = online
        self._status_versions[bot] += 1

    def update_player_status(self, player: str, online: bool) -> None:
        with self._lock:
            if self._closed:
                return
            bot = self._real_names.get(player.casefold())
            if bot:
                self._set_online(bot, online)

    def clear_all_online_status(self):
        with self._lock:
            if self._closed:
                return
            for bot in self.bots.values():
                bot.is_online = False
            bots = {name: Bot.from_dict(self.server, name, bot.to_dict()) for name, bot in self.bots.items()}
            self._install(bots)
            self._generation += 1

    def submit(self, callback, *args) -> Future:
        with self._lock:
            self._check_active()
            if not self._slots.acquire(blocking=False):
                raise RuntimeError('后台任务已满，请稍后重试')
            generation = self._generation

            def run():
                if self.is_active(generation):
                    return callback(*args)
                return None

            try:
                future = self._pool.submit(run)
            except Exception:
                self._slots.release()
                raise
            self._tasks.add(future)
            future.add_done_callback(self._task_done)
            return future

    def _task_done(self, future: Future) -> None:
        with self._lock:
            self._tasks.discard(future)
            self._slots.release()
        if not future.cancelled() and future.exception() is not None:
            self.server.logger.error(f'[BotKikai] 后台任务失败: {future.exception()}')

    def sync_online_status(self) -> bool:
        with self._lock:
            if self._closed or not self.server.is_server_startup():
                return False
            snapshot = {key: (bot, self._status_versions[bot]) for key, bot in self._real_names.items()}
            generation = self._generation
        if not snapshot:
            return True
        try:
            import minecraft_data_api as api
            result = api.get_server_player_list()
            if result is None:
                self.server.logger.warning('[BotKikai] 在线列表查询超时，保留当前状态')
                return False
            players = {name.casefold() for name in result[2]}
        except Exception as error:
            self.server.logger.warning(f'[BotKikai] 无法同步在线列表，保留当前状态: {error}')
            return False
        with self._lock:
            if not self.is_active(generation):
                return False
            # 查询期间收到的加入/退出事件优先，旧快照不能覆盖它们。
            for key, (bot, version) in snapshot.items():
                if self._real_names.get(key) is bot and self._status_versions[bot] == version:
                    self._set_online(bot, key in players)
        return True

    def request_sync(self) -> Future | None:
        if self.server.is_server_startup():
            try:
                return self.submit(self.sync_online_status)
            except RuntimeError as error:
                self.server.logger.warning(f'[BotKikai] 未能安排在线状态同步: {error}')
        return None

    def shutdown(self) -> None:
        with self._lock:
            self._closed = True
            self._generation += 1
            for bot in self.bots.values():
                bot.cancel()
            tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        self._pool.shutdown(wait=False, cancel_futures=True)
