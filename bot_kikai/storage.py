import json
import os

class Storage:
    def __init__(self, server_instance):
        data_folder = server_instance.get_data_folder()
        if not os.path.exists(data_folder):
            os.makedirs(data_folder)
        self.config_path = os.path.join(data_folder, 'BotKikai.json')
        self.bot_dic = {}
        self.bot_list = []  # 在线的假人列表

    def load(self):
        """从 JSON 文件加载假人数据"""
        if not os.path.isfile(self.config_path):
            self.save()
            return
        with open(self.config_path, 'r', encoding='utf8') as f:
            try:
                self.bot_dic = json.load(f)
            except json.JSONDecodeError:
                self.bot_dic = {}

    def save(self):
        """保存假人数据到 JSON 文件"""
        with open(self.config_path, 'w', encoding='utf8') as f:
            json.dump(self.bot_dic, f, indent=4, ensure_ascii=False)

    def search_by_nickname(self, nickname):
        """通过昵称查找假人的主名"""
        for name, info in self.bot_dic.items():
            if nickname in info.get('nick', []):
                return name
        return None

    def get_bot_info(self, name):
        """获取特定假人的信息"""
        return self.bot_dic.get(name)

    def add_bot(self, name, bot_info):
        """添加或更新一个假人"""
        self.bot_dic[name] = bot_info
        self.save()

    def del_bot(self, name):
        """删除一个假人"""
        if name in self.bot_dic:
            del self.bot_dic[name]
            self.save()
            return True
        return False

    def get_all_bots(self):
        """返回所有假人的字典"""
        return self.bot_dic

    # 在线状态管理
    def set_bot_online(self, name):
        if name not in self.bot_list:
            self.bot_list.append(name)

    def set_bot_offline(self, name):
        if name in self.bot_list:
            self.bot_list.remove(name)

    def is_bot_online(self, name):
        return name in self.bot_list

    def get_online_bots(self):
        return self.bot_list
        
    def set_online_bots(self, new_list):
        self.bot_list = new_list

    def clear_online_bots(self):
        self.bot_list = []

    def auth_player(self, player_name: str):
        """检查一个玩家名是否属于已配置的假人"""
        lower_dic = {name.lower(): name for name in self.bot_dic}
        return lower_dic.get(player_name.lower())

# 一个全局实例，将在插件加载时初始化
storage_instance = None

def init_storage(server):
    global storage_instance
    if storage_instance is None:
        storage_instance = Storage(server)
    storage_instance.load()
    return storage_instance
