import time

from mcdreforged.api.types import PluginServerInterface, ServerInterface
from mcdreforged.api.rtext import RText, RTextList, RAction

from . import utils


class Bot:
    def __init__(self, server: PluginServerInterface | ServerInterface, name: str, nicknames: list[str], dimension: str, position: list[float], facing: list[float]):
        self.server = server
        self.name = name
        self.nicknames = nicknames if nicknames is not None else [name]
        self.dimension = dimension
        self.position = position
        self.facing = facing
        self.is_online = False

    # --- 核心动作 ---

    def spawn(self, executor: str | None = None, pos=None, dim=None, facing=None):
        """
        在世界中生成假人
        :param executor: 如果由一名玩家执行，则假人会尝试复制其游戏模式
        """
        spawn_pos = pos or self.position
        spawn_dim = dim or self.dimension
        spawn_facing = facing or self.facing
        
        if spawn_pos is None or spawn_dim is None or spawn_facing is None:
            self.server.logger.error(f"[BotKikai] 假人 {self.name} 因缺少位置、维度或朝向信息而无法生成")
            return False

        pos_str = ' '.join(map(str, spawn_pos))
        facing_str = ' '.join(map(str, spawn_facing))
        
        base_command = f'player {self.name} spawn at {pos_str} facing {facing_str} in {spawn_dim}'
        
        if executor:
            final_command = f'execute as {executor} run {base_command}'
        else:
            final_command = base_command
            
        self.server.execute(final_command)
        return True

    def kill(self):
        """下线假人"""
        self.server.execute(f'player {self.name} kill')
        return True

    def stop(self):
        """停止假人的所有动作"""
        self.server.execute(f'player {self.name} stop')

    def _ensure_online(self, executor: str | None = None):
        if not self.is_online:
            self.spawn(executor=executor)
            
            # TODO 考虑独立配置文件
            max_wait_time = 10  # 自动上线等待时间
            wait_interval = 0.5  # 自动上线检查间隔
            waited_time = 0
            
            while not self.is_online and waited_time < max_wait_time:
                time.sleep(wait_interval)
                waited_time += wait_interval
            
            if not self.is_online:
                self.server.logger.warning(f"[BotKikai] 假人 {self.name} 在 {max_wait_time} 秒内未能成功上线，后续动作可能失败")

    # --- 交互动作 ---

    def use(self, continuous: bool = False, interval: int = 0, executor: str | None = None):
        """让假人执行“使用”（右键）动作"""
        self._ensure_online(executor)
        if continuous:
            action = f'use continuous' if interval <= 0 else f'use interval {interval}'
        else:
            action = 'use once'
        self.server.execute(f'player {self.name} {action}')

    def attack(self, continuous: bool = False, interval: int = 0, executor: str | None = None):
        """让假人执行“攻击”（左键）动作"""
        self._ensure_online(executor)
        if continuous:
            action = f'attack continuous' if interval <= 0 else f'attack interval {interval}'
        else:
            action = 'attack once'
        self.server.execute(f'player {self.name} {action}')

    # --- 状态与效果 ---

    def glowing(self, duration_sec: int = 120, amplifier: int = 0, executor: str | None = None):
        """为假人应用发光效果"""
        self._ensure_online(executor)
        self.server.execute(f'effect give {self.name} glowing {duration_sec} {amplifier}')

    # --- 数据转换 ---

    def to_dict(self) -> dict:
        return {
            'nicknames': self.nicknames,
            'dimension': self.dimension,
            'position': self.position,
            'facing': self.facing,
        }

    @staticmethod
    def from_dict(server: PluginServerInterface, name: str, data: dict) -> "Bot":
        # 兼容旧的 'nick', 'dim', 'pos' 键
        nicknames = data.get('nicknames', data.get('nick', [name]))
        dimension = data.get('dimension', data.get('dim', 'minecraft:overworld'))
        position = data.get('position', data.get('pos', [0.0, 64.0, 0.0]))
        facing_data = data.get('facing', [0.0, 0.0])
        facing = [float(v) for v in facing_data.split()] if isinstance(facing_data, str) else facing_data

        return Bot(
            server=server,
            name=name,
            nicknames=nicknames,
            dimension=dimension,
            position=position,
            facing=facing
        )
    
    def _get_command_rtext(self) -> RTextList:
        special_rtext = RTextList()
        if self.is_online:
            special_rtext.append(
                RText('§4[下线] ').c(RAction.suggest_command, f'{utils.prefix_short} {self.name} kill').h(f'下线 §6{self.name}'),
                RText('§b[停止] ').c(RAction.suggest_command, f'{utils.prefix_short} {self.name} stop').h(f'§6{self.name} §7停止所有动作'),
            )
        else:
            special_rtext.append(
                RText('§a[上线] ').c(RAction.suggest_command, f'{utils.prefix_short} {self.name} spawn').h(f'召唤 §6{self.name}'),
            )

        return RTextList(
            special_rtext,
            RText('§b[报点] ').c(RAction.suggest_command, f'{utils.prefix_short} {self.name} where').h(f'§6{self.name} §7发光两分钟并输出坐标'),
            RText('§b[右键] ').c(RAction.suggest_command, f'{utils.prefix_short} {self.name} use').h(f'§6{self.name} §7右键一次'),
            RText('§b[持续右键] ').c(RAction.suggest_command, f'{utils.prefix_short} {self.name} huse ').h(f'§6{self.name} §7持续右键，后接正整数可控制间隔 gt'),
            RText('§b[左键] ').c(RAction.suggest_command, f'{utils.prefix_short} {self.name} atk').h(f'§6{self.name} §7左键一次'),
            RText('§b[持续左键] ').c(RAction.suggest_command, f'{utils.prefix_short} {self.name} hatk ').h(f'§6{self.name} §7持续左键，后接正整数可控制间隔 gt'),
        )

    def get_info_rtext(self) -> RTextList:
        nickname_ls = list(filter(lambda x: x.lower() != self.name.lower(), self.nicknames))
        nickname = ", ".join(nickname_ls)
        online_status = '§a在线' if self.is_online else '§4离线'
        return RTextList(
            f'§7----------- §6{self.name} {online_status} §7-----------',
            f'\n§7用于:§d {nickname}',
            f'\n§7维度:§d {self.dimension}',
            RText(f'\n§7坐标:§d {self.position}').c(RAction.run_command, f'[x:{int(self.position[0]) if self.position else 0}, y:{int(self.position[1]) if self.position else 0}, z:{int(self.position[2]) if self.position else 0}, name:{self.name}, dim:{self.dimension}]').h('点击显示可识别坐标点'),
            f'\n§7朝向:§d {self.facing}\n',
            self._get_command_rtext(),
        )
    
    def get_simple_rtext(self) -> RTextList:
        nickname_ls = list(filter(lambda x: x.lower() != self.name.lower(), self.nicknames))
        nickname = ", ".join(nickname_ls)
        online_status = '§a在线' if self.is_online else '§4离线'
        return RTextList(
            '\n'
            f'§7----------- ',
            RText(f'§6{self.name}').h(
                f'§7用于:§d {nickname}\n',
                f'§7维度:§d {self.dimension}\n',
                f'§7坐标:§d {self.position}\n',
                f'§7朝向:§d {self.facing}'
            ),
            f' {online_status} §7-----------\n',
            f'§7此假人用于:§d {nickname}\n',
            self._get_command_rtext(),
        )
