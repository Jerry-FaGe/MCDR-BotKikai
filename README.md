# MCDR-BotKikai（Bot機械）

一个基于 [MCDReforged](https://github.com/Fallen-Breath/MCDReforged) 的 Minecraft 假人管理插件，专注于简化 [Carpet](https://github.com/gnembon/fabric-carpet) 假人的管理与操作。

> 君は道具ではなく、その名が似合う人になろんだ  

## 📝 简介

在生存服或生电服中，管理假人往往面临这些痛点：
- 记不住每个机器对应的假人英文名？
- 不习惯输入冗长复杂的英文原版/Carpet 指令？
- 机器离主城太远，每次开关机都得舟车劳顿甚至跨维度跑图？

**BotKikai** 为假人引入了**别名映射系统**。只需为假人设置一个中文别名（如将 `SandBot` 别名设置为 `刷沙机`），即可直接用机器名字操控它：
- `!!bk 刷沙机 spawn` 与 `!!bk SandBot spawn` 效果完全相同；
- 在世界任意位置输入 `!!bk 刷沙机 use`，插件会自动将假人召唤到记录位置就位，并自动右键开关启动机器。

> 上古版本的[介绍视频](https://www.bilibili.com/video/BV1Rf4y1C776) By: [Nachuan川川](https://space.bilibili.com/107251863)

## 🚀 特性

- **假人别名系统**：支持为每个假人绑定多个中文或拼音别名，无需记忆英文名与机器对应关系
- **远程一键联动**：执行使用/攻击命令时若假人离线，会自动将其召唤就位并在上线后触发动作
- **交互式聊天栏面板**：单行紧凑列表，点击按钮直接带入命令，支持悬浮预览详细数据与报点
- **分页与状态搜索**：支持按在线/离线状态筛选及关键词实时检索假人
- **灵活的别名管理**：支持独立追加与移除别名，不影响假人坐标、朝向及运行状态
- **前后缀与大小写自适应**：支持 Carpet 假人前后缀，自动记录并持久化服务端真实游戏名大小写
- **安全与稳定性**：配置热重载、原子文件保存、多级权限控制及动作生命周期安全取消

## ⚙️ 依赖

- Python >= 3.10
- [MCDReforged](https://github.com/Fallen-Breath/MCDReforged) >= 2.12.0（推荐 >= 2.16.2）
- [MinecraftDataAPI](https://github.com/Fallen-Breath/MinecraftDataAPI) >= 1.6.2
- Minecraft 服务端需要安装 [Carpet](https://github.com/gnembon/fabric-carpet) 模组

> 注：旧环境升级时请先更新上述依赖；插件不要求开启 RCON。

## 📖 命令说明

基础命令（可于配置文件中自定义）：

```minecraft
!!bk
```

### 管理与查询命令

| 命令 | 说明 | 默认权限 |
|------|------|----------|
| `!!bk` | 显示帮助信息 | 所有人 (guest) |
| `!!bk list [online\|offline] [page]` | 分页查看假人列表，可筛选在线或离线状态（每页 10 条） | 所有人 (guest) |
| `!!bk list [online\|offline] search <关键词> [page]` | 搜索假人（匹配登记名、游戏名或别名） | 所有人 (guest) |
| `!!bk <kikai>` | 显示假人详情面板与操作入口 | 所有人 (guest) |
| `!!bk add <name> <kikai>` | 使用当前玩家所在位置和朝向添加/更新假人 | 管理员 (admin) |
| `!!bk add <name> <kikai> <dim> <pos> <facing>` | 使用指定参数手动添加/更新假人 | 管理员 (admin) |
| `!!bk del <kikai>` | 删除假人记录（不会下线游戏中已在线假人） | 管理员 (admin) |
| `!!bk <kikai> alias` | 打开别名管理面板 | 管理员 (admin) |
| `!!bk <kikai> alias add <alias>` | 为指定假人添加别名 | 管理员 (admin) |
| `!!bk <kikai> alias del <alias>` | 移除指定假人的别名 | 管理员 (admin) |
| `!!bk reload` | 重载配置文件与假人数据 | 管理员 (admin) |

### 假人操作命令

| 命令 | 说明 | 默认权限 |
|------|------|----------|
| `!!bk <kikai> spawn` | 在登记位置召唤假人 | 玩家 (user) |
| `!!bk <kikai> kill` | 移除（下线）假人 | 玩家 (user) |
| `!!bk <kikai> where` | 显示记录位置，并让假人发光 2 分钟 | 玩家 (user) |
| `!!bk <kikai> use` | 假人右键一次（若离线会自动先召唤上线） | 玩家 (user) |
| `!!bk <kikai> huse [<interval>]` | 假人持续右键，可选间隔时间（单位：gt） | 玩家 (user) |
| `!!bk <kikai> atk` | 假人左键一次（若离线会自动先召唤上线） | 玩家 (user) |
| `!!bk <kikai> hatk [<interval>]` | 假人持续左键，可选间隔时间（单位：gt） | 玩家 (user) |
| `!!bk <kikai> stop` | 停止假人的所有动作 | 玩家 (user) |

> 说明：命令中的 `<kikai>` 可使用假人的**登记名**、**游戏名**或任意**别名**（均不区分大小写）。

## ⚡ 快速上手

### 1. 添加假人

前往目标机器前，站好期望的位置与朝向，执行：

```minecraft
!!bk add SandBot 刷沙机
```

插件会自动记录当前维度、精确坐标与朝向。假人基础名（如 `SandBot`）仅限英文字母、数字和下划线。

*也可以手动指定完整参数（支持 `0 / -1 / 1` 或 `overworld / the_nether / the_end` 等维度别名）：*

```minecraft
!!bk add SandBot 刷沙机 minecraft:overworld 0 64 0 -154.43 3.90
```

### 2. 操控假人

```minecraft
!!bk 刷沙机           # 查看假人详情与快捷操作面板
!!bk 刷沙机 spawn     # 召唤假人上线
!!bk 刷沙机 use       # 让假人右键一次（离线会自动先上线）
!!bk 刷沙机 hatk 12   # 让假人每 12 gt（0.6 秒）攻击一次
!!bk 刷沙机 stop      # 停止假人动作
!!bk 刷沙机 kill      # 让假人下线
```

### 3. 查看与检索列表

```minecraft
!!bk list                         # 查看全部假人（第 1 页）
!!bk list 2                       # 查看全部假人（第 2 页）
!!bk list online                  # 仅查看在线假人
!!bk list offline 2               # 仅查看离线假人（第 2 页）
!!bk list search 沙               # 搜索名字或别名包含「沙」的假人
!!bk list online search farm 2    # 在线假人中搜索 farm，查看第 2 页
```

列表每行紧凑展示假人名称与快捷按钮（上线/下线/右键/详情），鼠标悬浮在名称上可快速查看详细坐标与全部别名。

### 4. 独立增删别名

无需重新登记位置，可直接增删别名：

```minecraft
!!bk 刷沙机 alias           # 打开别名管理面板
!!bk 刷沙机 alias add 沙场   # 为同一假人增加别名「沙场」
!!bk SandBot alias del 沙场  # 移除别名「沙场」（登记名不可移除）
```

## ⚙️ 配置文件

插件会在 `config/bot_kikai` 目录下自动生成两个配置文件：

### 1. `config.json`（插件设置）

```json
{
    "prefix_short": "!!bk",
    "spawn_max_wait_time": 10.0,
    "spawn_check_interval": 0.5,
    "bot_name_prefix": "",
    "bot_name_suffix": "",
    "permission": {
        "bot": 1,
        "list": 3
    }
}
```

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `prefix_short` | string | `!!bk` | 插件指令前缀 |
| `spawn_max_wait_time` | float | `10.0` | 等待假人生成的最大超时时间（秒） |
| `spawn_check_interval` | float | `0.5` | 假人上线检测轮询间隔（秒） |
| `bot_name_prefix` | string | `""` | Carpet 假人名字前缀（如 `bot_`） |
| `bot_name_suffix` | string | `""` | Carpet 假人名字后缀 |
| `permission.bot` | int | `1` | 操作假人（spawn/use/kill 等）的最低权限等级 |
| `permission.list` | int | `3` | 管理假人（add/del/alias/reload 等）的最低权限等级 |

### 2. `bots.json`（假人数据）

```json
{
    "SandBot": {
        "nicknames": ["SandBot", "刷沙机", "shuashaji"],
        "dimension": "minecraft:overworld",
        "position": [-2.44, 70.0, -5.05],
        "facing": [180.0, 30.0]
    }
}
```

- `nicknames`: 假人的所有别名列表（第一项为基础登记名）
- `dimension`: 假人所在维度
- `position`: 假人位置坐标 `[x, y, z]`
- `facing`: 假人视线朝向 `[水平角, 垂直角]`
- `confirmed_name`: *（可选）* 插件自动确认并持久化的服务端真实大小写游戏名，通常由插件自动维护，无需手动干预。

### 配置重载与数据安全

- **热重载**：修改配置或假人数据后执行 `!!bk reload` 即可重新加载。若修改了 `prefix_short` 指令前缀，需执行 `!!MCDR plugin reload bot_kikai`。
- **原子保存**：插件采用临时文件与原子替换保存数据，保障文件在并发或异常退出时不损坏、不丢失。
- **历史迁移**：自 v0.6.0 起已采用双文件布局；若从 v0.4.0 以前的旧版本跨版本升级，请先使用 [v0.6.0](https://github.com/Jerry-FaGe/MCDR-BotKikai/releases/tag/v0.6.0) 完成自动迁移。

## 🔒 权限系统

插件直接接入 MCDR 原生[权限系统](https://docs.mcdreforged.com/zh-cn/latest/permission.html#permission-file)：

| 角色 | 等级 | 默认权限说明 |
|------|------|--------------|
| `guest` | 0 | 查看帮助、浏览列表与搜索、查看假人详情 |
| `user` | 1 | 假人日常操控（`spawn` / `kill` / `use` / `atk` / `stop` / `where`） |
| `helper` | 2 | - |
| `admin` | 3 | 假人登记与管理（`add` / `del` / `alias` / `reload`） |
| `owner` | 4 | 全部最高权限 |

## 📝 注意事项与交互机制

### 💬 聊天栏按钮交互机制与 1.21.5+ 优化规划

- **当前实现（1.19.1 ~ 1.21.4 兼容机制）**：
  - **交互行为**：自 Minecraft 1.19.1 引入聊天签名与安全审查机制后，原版客户端严格限制了 `run_command` 发送非 `/` 开头的原生聊天文本（详见 [MCDReforged #203](https://github.com/MCDReforged/MCDReforged/issues/203)）。为保障跨环境安全兼容，插件聊天栏内所有快捷按钮（如列表中的 `[上线]`、`[下线]`、`[右键]` 及详情面板操作）均采用 `suggest_command`（指令建议）模式。
  - **操作方式**：点击按钮后，对应指令会自动填入玩家聊天输入框，**需玩家手动按下回车（Enter）执行**。
  - **参数微调优势**：此模式虽然多了一次回车确认，但对于带参数的动作（如持续右键 `huse [<interval>]`、持续攻击 `hatk [<interval>]` 或列表搜索），点击后光标会自动定位到参数后方，方便玩家直接修改间隔 gt 数值或搜索词，避免无参盲发。

- **1.21.5+ 机制变革与后续优化重点**：
  - **上游机制演进**：Minecraft 1.21.5（Spring to Life）重构了聊天文本组件（Text Component）的底层规范与点击事件结构，并解除了 `run_command` 对命令必须以 `/` 开头的强制限制。
  - **未来优化规划**：本项目后续将聊天交互体验列为重点优化方向：
    1. **常用动作“真·一键直达”**：针对 `spawn`、`kill`、`use`、`stop`、`where` 及翻页刷新等无需附加参数的固定操作，探索结合 1.21.5+ 文本事件新特性或原生斜杠指令（如 `/` 别名桥接），恢复“点击即执行”的流畅体验；
    2. **分级差异化交互**：无参动作点击直接生效，带参动作（`huse` / `hatk` / `search`）保持自动填入供玩家按需微调，兼顾操作效率与可控性；
    3. **多版本自适应降级**：根据客户端与服务端环境动态兼容，在旧版本客户端上继续安全降级为 `suggest_command` 模式，确保全版本平滑运行。

### 📌 其他注意事项

- **Carpet 前后缀一致性**：若服务端开启了假人前后缀，请务必在 `config.json` 中配置完全一致的前后缀，避免假人身份匹配异常。
- **Carpet 拉杆操作限制**：部分 Carpet 版本中假人右键可能无法正常拨动拉杆，推荐使用音符盒、红石按钮等更稳定的机械开关。
- **假人位置说明**：展示和记录的位置均为登记时的就位点，不会实时追踪假人后续在游戏内被外力位移（如水流冲走）后的位置。

## 🧪 开发与测试

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m mcdreforged pack
```

测试套件完整覆盖了配置校验、原子读写、别名管理、并发任务、命令解析及富文本面板渲染。CI 矩阵覆盖 Python 3.10 / 3.12 及 MCDR 2.12.0 / 2.16.2。

## ⚠️ 声明

本插件实现的功能只要是装了 Carpet Mod 能召唤假人的服务端都可以实现，即便是这样也仍有可能引发**不香草**争议。烦请想装本插件的腐竹实装前务必了解下成员们的意愿。

## 🤝 致谢

- 感谢 [Fallen_Breath](https://github.com/Fallen-Breath) 开发的 [MCDR](https://github.com/Fallen-Breath/MCDReforged) 框架
- 感谢 [Carpet](https://github.com/gnembon/fabric-carpet) 模组提供的假人功能
- 感谢 [AnzhiZhang](https://github.com/AnzhiZhang) 的 [Bot](https://github.com/AnzhiZhang/MCDReforgedPlugins/tree/master/src/bot) 插件提供的灵感

## 📄 开源协议

[GPL-3.0 License](LICENSE)
