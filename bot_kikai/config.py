import os
import json
from typing import Optional, Dict
from dataclasses import dataclass, field

from mcdreforged.api.types import PluginServerInterface


@dataclass
class Config:
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
        data_folder = server.get_data_folder()
        if not os.path.exists(data_folder):
            os.makedirs(data_folder)
            
        self.config_path = os.path.join(data_folder, 'config.json')
        self.bots_path = os.path.join(data_folder, 'bots.json')

        self._migrate_old_config()
        self.load()
    
    def _migrate_old_config(self) -> None:
        """迁移旧版本配置文件"""
        if not self.config_path or not self.bots_path or not self.server:
            return
            
        try:
            with open(self.config_path, 'r', encoding='utf8') as f:
                old_data: dict = json.load(f)
                
            # 检查是否是旧版本的假人信息配置文件
            is_old_format = False
            for value in old_data.values():
                if isinstance(value, dict) and 'nicknames' in value:
                    is_old_format = True
                    break
                    
            if is_old_format:
                self.server.logger.info('[BotKikai] 检测到旧版本配置文件，开始迁移...')
                                
                # 迁移假人数据到新的 bots.json
                with open(self.bots_path, 'w', encoding='utf8') as f:
                    json.dump(old_data, f, ensure_ascii=False, indent=4)
                self.server.logger.info('[BotKikai] 配置文件迁移完成')
                
                # 备份旧配置文件
                old_backup = f"{self.config_path}.bak"
                os.rename(self.config_path, old_backup)
                self.server.logger.info(f'[BotKikai] 已备份旧配置文件到 {old_backup}')
        except Exception as e:
            self.server.logger.error(f'[BotKikai] 迁移配置文件时出错: {e}')

    def load(self) -> None:
        """加载配置文件"""
        if not self.config_path or not os.path.isfile(self.config_path):
            self.save()
            return

        with open(self.config_path, 'r', encoding='utf8') as f:
            try:
                config_data = json.load(f)
                # 更新配置
                for key, value in config_data.items():
                    if hasattr(self, key):
                        setattr(self, key, value)
            except json.JSONDecodeError:
                self.save()

    def save(self) -> None:
        """保存配置到文件"""
        if not self.config_path:
            return
            
        config_data = {
            'prefix_short': self.prefix_short,
            'spawn_max_wait_time': self.spawn_max_wait_time,
            'spawn_check_interval': self.spawn_check_interval,
            'bot_name_prefix': self.bot_name_prefix,
            'bot_name_suffix': self.bot_name_suffix,
            'permission': self.permission
        }
        
        with open(self.config_path, 'w', encoding='utf8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)


# 创建全局配置实例
config = Config()
