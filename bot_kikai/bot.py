import re
import threading
import time

from mcdreforged.api.types import PluginServerInterface, ServerInterface
from mcdreforged.api.rtext import RTextList

from .config import Config, config, is_finite_number


class Bot:
    def __init__(self, server: PluginServerInterface | ServerInterface, name: str, nicknames: list[str],
                 dimension: str, position: list[float], facing: list[float], settings: Config | None = None,
                 confirmed_name: str | None = None):
        settings = settings or config
        if not isinstance(name, str) or re.fullmatch(r'[A-Za-z0-9_]{1,16}', name) is None:
            raise ValueError('假人名称只能包含 1 到 16 个英文字母、数字或下划线')
        self.server = server
        self.name = name
        self._expected_name = f'{settings.bot_name_prefix}{name.lower()}{settings.bot_name_suffix}'
        if re.fullmatch(r'[A-Za-z0-9_]{3,16}', self._expected_name) is None:
            raise ValueError(f'{name}: 加上前后缀后的游戏名必须是 3 到 16 个英文字母、数字或下划线')
        self._confirmed_name: str | None = None
        if confirmed_name is not None:
            if not isinstance(confirmed_name, str) or re.fullmatch(r'[A-Za-z0-9_]{3,16}', confirmed_name) is None:
                raise ValueError(f'{name}: confirmed_name 必须是 3 到 16 个英文字母、数字或下划线')
            self.confirm_name(confirmed_name)
        if not isinstance(nicknames, list) or not all(
            isinstance(nick, str) and nick and not any(
                ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in nick
            ) for nick in nicknames
        ):
            raise ValueError(f'{name}: nicknames 必须是非空、无空白字符的字符串列表')
        self.nicknames = list(dict.fromkeys([name, *nicknames]))
        if type(dimension) is int:
            dimension = {0: 'minecraft:overworld', -1: 'minecraft:the_nether', 1: 'minecraft:the_end'}.get(dimension)
        if not isinstance(dimension, str) or re.fullmatch(r'[a-z0-9_.-]+:[a-z0-9_./-]+', dimension) is None:
            raise ValueError(f'{name}: dimension 必须是有效的命名空间维度 ID')
        self.dimension = dimension
        self.position = self._vector(position, 3, 'position')
        self.facing = self._vector(facing, 2, 'facing')
        self._state = threading.Condition()
        self._action_lock = threading.RLock()
        self._online = False
        self._cancelled = False

    @staticmethod
    def _vector(values, length: int, field: str) -> list[float]:
        if isinstance(values, str):
            try:
                values = [float(value) for value in values.split()]
            except ValueError as error:
                raise ValueError(f'{field} 包含无效数值') from error
        if not isinstance(values, (list, tuple)) or len(values) != length or not all(
            is_finite_number(value) for value in values
        ):
            raise ValueError(f'{field} 必须包含 {length} 个有限数值')
        return [float(value) for value in values]

    @property
    def expected_name(self) -> str:
        return self._expected_name

    @property
    def confirmed_name(self) -> str | None:
        return self._confirmed_name

    @property
    def real_name(self) -> str:
        return self._confirmed_name or self._expected_name

    def confirm_name(self, player: str) -> bool:
        """Learn spelling, not a new identity; the manager serializes observations."""
        if not isinstance(player, str) or re.fullmatch(r'[A-Za-z0-9_]{3,16}', player) is None:
            return False
        if player.casefold() != self.expected_name.casefold() or player == self._confirmed_name:
            return False
        self._confirmed_name = player
        return True

    @property
    def is_online(self) -> bool:
        with self._state:
            return self._online

    @is_online.setter
    def is_online(self, value: bool) -> None:
        with self._state:
            self._online = value
            self._state.notify_all()

    def cancel(self) -> None:
        with self._state:
            self._cancelled = True
            self._state.notify_all()

    def _execute(self, command: str) -> bool:
        with self._state:
            if self._cancelled or not self.server.is_server_running():
                return False
            self.server.execute(command)
            return True

    # --- 核心动作 ---

    def spawn(self, executor: str | None = None, pos=None, dim=None, facing=None):
        """发送召唤请求，并等待玩家加入事件确认上线。"""
        with self._action_lock:
            with self._state:
                if self._cancelled or not self.server.is_server_running():
                    return False
                if self._online:
                    return True
            pos_str = ' '.join(map(str, self.position if pos is None else self._vector(pos, 3, 'position')))
            facing_str = ' '.join(map(str, self.facing if facing is None else self._vector(facing, 2, 'facing')))
            spawn_dim = self.dimension if dim is None else dim
            if not isinstance(spawn_dim, str) or re.fullmatch(r'[a-z0-9_.-]+:[a-z0-9_./-]+', spawn_dim) is None:
                raise ValueError('无效的维度 ID')
            if executor is not None and re.fullmatch(r'[A-Za-z0-9_]{3,16}', executor) is None:
                raise ValueError('无效的执行玩家名')
            command = f'player {self.real_name} spawn at {pos_str} facing {facing_str} in {spawn_dim}'
            if executor:
                command = f'execute as {executor} run {command}'
            if not self._execute(command):
                return False

            deadline = time.monotonic() + config.spawn_max_wait_time
            with self._state:
                while not self._online and not self._cancelled and self.server.is_server_running():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    self._state.wait(min(config.spawn_check_interval, remaining))
                if self._online and not self._cancelled and self.server.is_server_running():
                    return True
            self.server.logger.warning(f'[BotKikai] 未能确认假人 {self.name} 上线，操作已终止')
            return False

    def kill(self):
        """下线假人"""
        with self._action_lock:
            return self._execute(f'player {self.real_name} kill')

    def stop(self):
        """停止假人的所有动作"""
        with self._action_lock:
            return self._execute(f'player {self.real_name} stop')

    def _ensure_online(self, executor: str | None = None):
        return self.spawn(executor=executor)

    def _interact(self, action: str, continuous: bool, interval: int, executor: str | None) -> bool:
        if type(interval) is not int or interval < 0:
            raise ValueError('动作间隔必须是非负整数')
        with self._action_lock:
            if not self._ensure_online(executor):
                return False
            mode = ('continuous' if interval == 0 else f'interval {interval}') if continuous else 'once'
            return self._execute(f'player {self.real_name} {action} {mode}')

    # --- 交互动作 ---

    def use(self, continuous: bool = False, interval: int = 0, executor: str | None = None):
        """让假人执行“使用”（右键）动作"""
        return self._interact('use', continuous, interval, executor)

    def attack(self, continuous: bool = False, interval: int = 0, executor: str | None = None):
        """让假人执行“攻击”（左键）动作"""
        return self._interact('attack', continuous, interval, executor)

    # --- 状态与效果 ---

    def glowing(self, duration_sec: int = 120, amplifier: int = 0, executor: str | None = None):
        """为假人应用发光效果"""
        with self._action_lock:
            if not self._ensure_online(executor):
                return False
            return self._execute(f'effect give {self.real_name} glowing {duration_sec} {amplifier}')

    # --- 数据转换 ---

    def to_dict(self) -> dict:
        data = {
            'nicknames': self.nicknames.copy(),
            'dimension': self.dimension,
            'position': self.position.copy(),
            'facing': self.facing.copy(),
        }
        confirmed_name = self.confirmed_name
        if confirmed_name is not None:
            data['confirmed_name'] = confirmed_name
        return data

    @staticmethod
    def from_dict(server: PluginServerInterface, name: str, data: dict, settings: Config | None = None) -> "Bot":
        if not isinstance(data, dict):
            raise ValueError(f'{name}: 假人数据必须是 JSON 对象')
        # 兼容旧的 'nick', 'dim', 'pos' 键
        nicknames = data.get('nicknames', data.get('nick', [name]))
        if 'nicknames' not in data and isinstance(nicknames, str):
            nicknames = [nicknames]
        dimension = data.get('dimension', data.get('dim', 'minecraft:overworld'))
        position = data.get('position', data.get('pos', [0.0, 64.0, 0.0]))
        facing = data.get('facing', [0.0, 0.0])

        return Bot(
            server=server,
            name=name,
            nicknames=nicknames,
            dimension=dimension,
            position=position,
            facing=facing,
            settings=settings,
            confirmed_name=data.get('confirmed_name'),
        )
    
    # Keep the existing entry points; all rendering lives in view.
    def _get_command_rtext(self) -> RTextList:
        from .view import render_bot_actions
        return render_bot_actions(self)

    def get_info_rtext(self) -> RTextList:
        from .view import render_bot_info
        return render_bot_info(self)

    def get_simple_rtext(self) -> RTextList:
        from .view import render_bot_summary
        return render_bot_summary(self)
