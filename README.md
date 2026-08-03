# 赛博小镇（Cyber Town）

第十五章 CyberTown 的 Windows 2D 像素风 AI NPC 架构原型。玩家在原创办公室场景中移动，
与张旭、樊玥燚、胡佳烙对话；对话历史、关系和长期记忆保存在本地 SQLite。
项目不依赖 Helix，默认 mock 模式无需网络或密钥，也支持 OpenAI Chat Completions
兼容接口。

## 目录导航

- `Docs/`：需求、产品简报、计划和详细设计。
- `Content/`：前后端共同读取的唯一 NPC 内容源。
- `Game/`：Godot 项目，按 Integration、World、Character、Dialogue 功能组织。
- `Backend/`：FastAPI、Agent、SQLite 和自动化测试。
- `Build/`：构建脚本、PyInstaller 配置、用户说明和许可证。
- `Acceptance/`：最终验收探针、运行记录和截图。
- `Release/`：可直接交付的 Windows 构建，Git 忽略。

## 当前能力

- Godot 4.7.1 桌面游戏：移动、碰撞、NPC 巡逻、交互提示和异步对话 UI。
- FastAPI 后端：角色化回复、确定性关系规则、结构化记忆、幂等请求和脱敏日志。
- `Content/NPCProfiles.json` 统一配置 NPC 的稳定 ID、姓名、性格、外观和场景参数。
- PyInstaller one-folder 后端与 Godot Windows 发布包，不要求玩家安装开发工具。

## 开发环境

- Windows x86_64
- Godot `D:\Godot\Godot_v4.7.1-stable_win64.exe`
- Python 3.11.15、uv 0.12+（环境位于 `Backend/.venv`）

首次安装：

```powershell
uv sync --project Backend --python 3.11
```

分别启动后端与 Godot 编辑器：

```powershell
Backend\.venv\Scripts\python.exe Backend\RunBackend.py
D:\Godot\Godot_v4.7.1-stable_win64.exe --editor --path Game
```

后端健康检查为 `http://127.0.0.1:8765/health`。在编辑器中直接运行游戏时，
游戏也会尝试启动并管理当前项目的后端子进程。

## 配置

开发环境读取被 Git 忽略的 `Backend/.env`；发布版读取
`%APPDATA%\CyberTown\.env`。默认不需要配置。启用真实模型时写入：

```dotenv
CYBER_TOWN_MODEL_BASE_URL=https://your-provider.example/v1
CYBER_TOWN_MODEL_NAME=your-model-name
CYBER_TOWN_MODEL_API_KEY=your-api-key
CYBER_TOWN_MODEL_TIMEOUT_SECONDS=15
```

兼容别名为 `LLM_BASE_URL`、`LLM_MODEL_ID`、`LLM_API_KEY`。Base URL、模型名和
API Key 必须同时存在，否则自动回退到 mock。不要提交 `.env`。

NPC 内容只编辑 `Content/NPCProfiles.json`。修改显示名称或性格后重启即可生效；
保留原 `npc_id` 可继续关联既有历史、关系和记忆。

## 验证

```powershell
Backend\.venv\Scripts\python.exe -m ruff check Backend\src Backend\tests Backend\RunBackend.py
Backend\.venv\Scripts\python.exe -m pytest -q Backend\tests
D:\Godot\Godot_v4.7.1-stable_win64.exe --headless --path Game --script res://Tests/TestRunner.gd
```

## Windows 发布

先安装 Godot 4.7.1 Windows export templates，然后执行：

```powershell
powershell -ExecutionPolicy Bypass -File Build\BuildRelease.ps1 -Version 0.1.0
```

脚本运行后端检查和测试、冻结后端、导出 Godot、扫描发布内容，并在精简 PATH
下完成两次启动/退出冒烟。输出位于 `Release/CyberTown-v0.1.0-windows-x86_64`，
同时生成 ZIP 与 `.sha256`。开发中的脏工作区需要显式加 `-AllowDirty`；正式发布
应从干净提交构建。

最终用户说明位于发布包的 `README.txt`。本地数据和日志位于
`%APPDATA%\CyberTown`，不会写入发布目录。

## 首版边界

当前仅包含 Windows x86_64、单人、一个办公室场景和 SQLite。Qdrant、Neo4j、
多人、任务系统、游戏内 NPC 编辑器均不在首版范围。
