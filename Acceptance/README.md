# CyberTown（第十五章）阶段七验收记录

> 2026-11：项目已更名为 Breakroom（茶水间）。本文是当时的验收存档，路径、产物名和提交信息保留原文。

验收时间：2026-08-03（Asia/Shanghai）

基线提交：`ed13be9 build: package Windows CyberTown prototype`

平台：Windows，Godot 4.7.1 stable，Python 3.11.15

## 总结

`AC-01` 至 `AC-10` 全部通过。验收期间发现并修复了 Godot 干净缓存首次解析依赖全局类缓存的问题；`DialogueUI.gd` 与 `Player.gd` 现在显式预加载其脚本依赖。

2026-08-03 按职责重组为 `Docs / Game / Backend / Build`，随后将项目根改名为 `CyberTown`、Python 包改名为 `Backend/src`，并执行完整重建与回归。当前 Release ZIP SHA-256 为：

`db89273b1ba7be1547221e5b45afd58ee3cea5bf73ab0f0fd0d97b56ea3d0dc1`

## 自动化结果

| 检查 | 命令 | 实际结果 |
| --- | --- | --- |
| Ruff | `Backend\.venv\Scripts\python.exe -m ruff check --no-cache Backend\src Backend\tests Backend\RunBackend.py Acceptance\BackendProbe.py` | `All checks passed!` |
| 后端回归 | `python -m pytest -q -p no:cacheprovider Backend\tests`（`PYTHONDONTWRITEBYTECODE=1`） | `73 passed in 5.32s` |
| Godot 干净导入 | `Godot_v4.7.1-stable_win64_console.exe --headless --import --path Game` | 5 个 SVG 全部导入，脚本类注册完成，退出码 0 |
| Godot 测试 | `Godot_v4.7.1-stable_win64_console.exe --headless --path Game --script res://Tests/TestRunner.gd` | content、movement、collision、interaction、dialogue、health、runtime command、startup layout 全部通过，无脚本或资源错误 |
| 运行模式探针 | `Backend\.venv\Scripts\python.exe Acceptance\BackendProbe.py` | `passed: true`；三 NPC 的 mock、真实模型、fallback 及 SQLite 重启全部通过 |
| Release 烟测 | `Build\SmokeTest.ps1 -ReleaseDirectory Release\CyberTown-v0.1.0-windows-x86_64` | 冻结后端、外部内容、历史、干净 PATH、两次游戏启动、进程清理全部通过 |
| ZIP 扫描 | PowerShell `System.IO.Compression.ZipFile` 扫描 | 91 个条目，禁用项 0；SHA-256 与阶段六一致 |
| 清理状态 | `Get-Process` 与 `Get-NetTCPConnection -LocalPort 8765` | 相关进程 0，8765 监听 0 |

## 结构重组复验

| 检查 | 实际结果 |
| --- | --- |
| 后端 | `Backend/src` 通过 Ruff；完整构建中 `73 passed in 5.88s` |
| Godot | 从空 `Game/.godot` 导入成功；完整交互测试通过 |
| 运行模式 | 三 NPC 的 mock、真实模型和 fallback 全部通过；SQLite 重启与隔离通过 |
| 完整构建 | `Build/BuildRelease.ps1 -Version 0.1.0 -AllowDirty` 成功完成 PyInstaller、Godot 导出、ZIP 和烟测 |
| 路径与包名 | 新根目录 `E:/HelloAgents/CyberTown`；Python 导入根为 `src`；旧 `E:/HelloAgents/Chapter15` 不存在 |
| Release | 91 个 ZIP 条目，禁用项 0；相关进程 0，8765 监听 0 |

## AC 验收矩阵

| 标准 | 结果与可复查证据 |
| --- | --- |
| AC-01 | 通过。Release 烟测在全新临时 `APPDATA`/数据目录连续启动两次；主场景截图显示 1280 x 720 办公室、玩家与张旭/樊玥燚/胡佳烙三名 NPC。证据：`Screenshots/main-1280x720.png`、`Screenshots/main-1600x900.png`。 |
| AC-02 | 通过。Godot 测试使用真实 `Player.tscn` 验证移动、静态碰撞阻挡、对话期间移动锁定；既有键盘测试覆盖最近 NPC 选择、E 键、发送、收到回复、重试和 Esc 关闭。 |
| AC-03 | 通过。运行模式探针对三个 NPC 分别请求，均返回 HTTP 200、`reply_source=mock`、`degraded=false`；73 项后端测试覆盖 NPC 独立关系与历史。三个 NPC 的工程、产品、视觉提示与 mock 回复模板彼此独立。 |
| AC-04 | 通过。UTF-8 探针保存“我喜欢蓝色”，重启应用和 SQLite 连接后同 NPC 能召回，其他 NPC 不引用，历史为 4 条消息。结果见 `RuntimeModes.json`。 |
| AC-05 | 通过。Release 烟测从外部 `Content/NPCProfiles.json` 修改张旭名称与性格，重启后 `/npcs` 和新对话均使用新配置，原 `npc_id` 历史仍为 4 条。 |
| AC-06 | 通过。`test_relationship_service.py` 覆盖正向、中性、负向、分数边界与重复中性消息；`test_persistence.py` 覆盖关系重启恢复。全套 pytest 通过。 |
| AC-07 | 通过。fallback 探针对三 NPC 均返回 HTTP 200、`reply_source=fallback`、`degraded=true`；Godot 测试覆盖失败后可重试和关闭，移动锁定可恢复。离线 UI 文案与可用控件见 `Screenshots/dialogue-offline-1280x720.png`。 |
| AC-08 | 通过。pytest 覆盖对话/关系/长期记忆重启恢复、跨 NPC 和跨玩家隔离、事务失败无半条数据；独立探针再次确认 SQLite 重启与跨 NPC 隔离。 |
| AC-09 | 通过。Ruff、73 项后端测试、Godot 干净导入与场景测试均通过；1280 x 720 与 1600 x 900 的主场景和对话截图均已人工检查，画面非空、文字清晰、控件无越界或重叠。 |
| AC-10 | 通过。Release 目录烟测扫描及独立 ZIP 扫描均确认不含 `.env`、密钥、日志、SQLite 数据、测试、Python 源码/缓存、Godot 导入缓存；重组后 ZIP 仍为 91 个条目，禁用项 0。 |

## 截图证据

- `Screenshots/main-1280x720.png`
- `Screenshots/dialogue-1280x720.png`
- `Screenshots/dialogue-offline-1280x720.png`
- `Screenshots/main-1600x900.png`
- `Screenshots/dialogue-1600x900.png`

截图通过 `CYBER_TOWN_CAPTURE_KIND` 测试钩子生成；该钩子只在显式设置环境变量时加载，不进入 Release。

## 运行模式说明

`RuntimeModes.json` 不包含模型地址、模型名或密钥。真实模型探针只记录 HTTP 状态、`reply_source`、`degraded` 和尝试次数。外部模型出现降级时，`BackendProbe.py` 按游戏 UI 的“再次尝试”行为最多重试一次；最终仍降级则验收失败。
