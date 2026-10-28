import math
import re
from pathlib import Path
from typing import ClassVar, Optional, Dict
from dataclasses import dataclass, field

from mcdreforged.api.types import PluginServerInterface

from .storage import read_json, write_json


def is_finite_number(value) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


@dataclass
class Config:
    FIELDS: ClassVar[tuple[str, ...]] = (
        'prefix_short', 'spawn_max_wait_time', 'spawn_check_interval',
        'bot_name_prefix', 'bot_name_suffix', 'permission',
    )
    # 命令配置
    prefix_short: str = '!!bk'  # 命令前缀
    
    # 假人自动上线相关配置
    spawn_max_wait_time: float = 10.0  # 最大等待时间（秒）
    spawn_check_interval: float = 0.5  # 检查间隔（秒）

    # Carpet 假人前后缀
    bot_name_prefix: str = ''  # 假人名称前缀
    bot_name_suffix: str = ''  # 假人名称后缀

    # 权限配置  guest: 0, user: 1, helper: 2, admin: 3, owner: 4
    permission: Dict[str, int] = field(default_factory=lambda: {
        'bot': 1,  # 操作假人(spawn,use,kill)的最低权限
        'list': 3  # 操作假人列表(add,remove)的最低权限
    })

    # 运行时状态
    server: Optional[PluginServerInterface] = None
    config_path: Optional[str] = None
    bots_path: Optional[str] = None

    def init(self, server: PluginServerInterface) -> None:
        """初始化配置文件路径"""
        self.server = server
        data_folder = Path(server.get_data_folder())
        data_folder.mkdir(parents=True, exist_ok=True)
        self.config_path = str(data_folder / 'config.json')
        self.bots_path = str(data_folder / 'bots.json')

        if not Path(self.config_path).exists():
            write_json(self.config_path, Config().to_dict())
        self.load()

    @classmethod
    def from_dict(cls, data: dict) -> 'Config':
        if not isinstance(data, dict):
            raise ValueError('config.json 必须是 JSON 对象')
        unknown = set(data) - set(cls.FIELDS)
        if unknown:
            if any(isinstance(data[key], dict) and ('nicknames' in data[key] or 'nick' in data[key])
                   for key in unknown):
                raise ValueError('config.json 不再支持旧版假人记录布局；请先备份，使用已发布的 v0.6.0 迁移到 bots.json 后再升级')
            raise ValueError(f'未知配置项: {", ".join(sorted(unknown))}')
        result = cls()
        for key in cls.FIELDS:
            if key in data and key != 'permission':
                setattr(result, key, data[key])
        if not isinstance(result.prefix_short, str) or not result.prefix_short or any(
            ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in result.prefix_short
        ):
            raise ValueError('prefix_short 必须是非空、无空白字符的命令前缀')
        for key in ('spawn_max_wait_time', 'spawn_check_interval'):
            value = getattr(result, key)
            if not is_finite_number(value) or value <= 0:
                raise ValueError(f'{key} 必须是大于 0 的有限数值')
        for key in ('bot_name_prefix', 'bot_name_suffix'):
            value = getattr(result, key)
            if not isinstance(value, str) or re.fullmatch(r'[A-Za-z0-9_]*', value) is None:
                raise ValueError(f'{key} 只能包含英文字母、数字和下划线')
        if len(result.bot_name_prefix) + len(result.bot_name_suffix) > 15:
            raise ValueError('假人前后缀总长度不能超过 15')
        permissions = data.get('permission', {})
        if not isinstance(permissions, dict) or set(permissions) - set(result.permission):
            raise ValueError('permission 只支持 bot 和 list 两项')
        for key, value in permissions.items():
            if type(value) is not int or not 0 <= value <= 4:
                raise ValueError(f'permission.{key} 必须是 0 到 4 的整数')
            result.permission[key] = value
        return result

    def read(self) -> 'Config':
        if not self.config_path:
            raise RuntimeError('配置路径尚未初始化')
        return self.from_dict(read_json(self.config_path))

    def apply(self, other: 'Config') -> None:
        for key, value in other.to_dict().items():
            setattr(self, key, value)

    def load(self) -> None:
        """验证全部配置后才应用；读取失败时不修改文件或当前状态。"""
        self.apply(self.read())

    def to_dict(self) -> dict:
        return {
            **{key: getattr(self, key) for key in self.FIELDS if key != 'permission'},
            'permission': self.permission.copy(),
        }

    def save(self) -> None:
        """保存配置到文件"""
        if not self.config_path:
            return
            
        write_json(self.config_path, self.from_dict(self.to_dict()).to_dict())


# 创建全局配置实例
config = Config()
