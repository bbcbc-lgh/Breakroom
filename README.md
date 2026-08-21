# Cyber Town

![License](https://img.shields.io/badge/license-MIT-blue.svg)

Cyber Town 是一个 Windows x86_64 俯视角像素游戏原型：玩家可以在办公室中移动，和拥有独立人格、关系与持续记忆的 NPC 对话。游戏由 Godot 驱动，FastAPI 后端负责对话、关系和记忆；默认使用本地 mock 回复，不需要 API Key。

> 当前状态：首版原型，目标平台为 Windows x86_64。发布包和运行数据不提交到 Git。

## 先试试看

如果只想运行游戏，请从仓库的 [Releases](../../releases) 下载最新 Windows 压缩包，解压后双击 `CyberTown.exe`。发布包不要求安装 Python、Godot 或模型服务。

操作：使用 `WASD` 或方向键移动，靠近 NPC 后按 `E` 交互；在对话框中按 `Enter` 发送，按 `Esc` 关闭。

## 本地开发

### 环境要求

- Windows x86_64
- [Godot 4.7.1](https://godotengine.org/download/archive/4.7.1-stable/)（开发和导出使用同一版本）
- Python 3.11
- [uv](https://docs.astral.sh/uv/)

### 安装与启动

在仓库根目录执行：

```powershell
uv sync --project Backend --python 3.11
Backend\.venv\Scripts\python.exe Backend\RunBackend.py
```

另开一个终端启动 Godot 编辑器：

```powershell
godot --editor --path Game
```

如果 `godot` 不在 PATH 中，将它替换为本机 Godot 可执行文件路径。后端启动后可访问 <http://127.0.0.1:8765/health> 检查状态；在编辑器中运行游戏时，游戏也会尝试自动启动和管理后端子进程。

## 常见修改

### 修改 NPC 内容

编辑 [`Content/NPCProfiles.json`](Content/NPCProfiles.json)，保存后重启游戏即可生效。可以修改姓名、职业、性格和说话风格等字段。

请保留已有的 `npc_id`：它是历史对话、关系和记忆的稳定关联键。字段定义和校验规则见 [`Docs/Design/NPCConfiguration.md`](Docs/Design/NPCConfiguration.md)。

### 启用真实模型（可选）

开发环境使用被 Git 忽略的 `Backend/.env`。复制 [`Backend/.env.example`](Backend/.env.example) 后填写以下配置：

```dotenv
CYBER_TOWN_MODEL_BASE_URL=https://your-provider.example/v1
CYBER_TOWN_MODEL_NAME=your-model-name
CYBER_TOWN_MODEL_API_KEY=your-api-key
CYBER_TOWN_MODEL_TIMEOUT_SECONDS=15
```

Base URL、模型名和 API Key 必须同时存在，否则自动回退到 mock。不要提交 `.env` 或 API Key。发布版的配置文件位置为 `%APPDATA%\CyberTown\.env`。

兼容变量名为 `LLM_BASE_URL`、`LLM_MODEL_ID` 和 `LLM_API_KEY`。本地日志位于 `%APPDATA%\CyberTown\Logs\CyberTown.log`，对话数据库位于 `%APPDATA%\CyberTown\Data\CyberTown.db`。

## 验证改动

提交前建议运行完整检查：

```powershell
Backend\.venv\Scripts\python.exe -m ruff check Backend\src Backend\tests Backend\RunBackend.py
Backend\.venv\Scripts\python.exe -m pytest -q Backend\tests
godot --headless --path Game --script res://Tests/TestRunner.gd
```

若 Godot 不在 PATH 中，同样替换为本机可执行文件路径。

## 构建 Windows 发布包

先安装 Godot 4.7.1 的 Windows export templates，然后执行：

```powershell
powershell -ExecutionPolicy Bypass -File Build\BuildRelease.ps1 `
  -Version 0.1.0 `
  -GodotPath 'C:\Path\To\Godot_v4.7.1-stable_win64.exe'
```

脚本会依次运行 Ruff、pytest、PyInstaller、Godot 导出和发布包冒烟测试，并生成：

- `Release/CyberTown-v0.1.0-windows-x86_64/`
- 对应 ZIP 压缩包
- `.sha256` 校验文件

脚本默认要求 Git 工作区干净；本地开发验证可以明确传入 `-AllowDirty`。发布包内的玩家说明位于 `README.txt`。

## 项目结构

| 路径 | 用途 |
| --- | --- |
| `Game/` | Godot 游戏、场景、角色、对话 UI 和 Godot 测试 |
| `Backend/` | FastAPI 服务、对话 Agent、SQLite 持久化和 Python 测试 |
| `Content/` | 前后端共享的 NPC 配置源 |
| `Build/` | PyInstaller、Windows 导出和发布包脚本 |
| `Acceptance/` | 验收探针、运行记录和截图 |
| `Docs/` | 需求、架构、API 契约和设计文档 |

更详细的边界和接口说明：[`Docs/Design/Architecture.md`](Docs/Design/Architecture.md)、[`Docs/Design/APIContract.md`](Docs/Design/APIContract.md)。

## 遇到问题

- 8765 端口被占用时，关闭占用程序后重试启动。
- 后端无法连接模型服务时会自动降级到 mock，游戏仍可继续运行。
- 启动和对话日志位于 `%APPDATA%\CyberTown\Logs\CyberTown.log`；提交 Issue 时请附上复现步骤和相关日志片段，并先移除 API Key 等敏感信息。

## 参与开发

欢迎提交 Issue 和 Pull Request。提交前请：

1. 说明问题的复现步骤，或清楚描述改动解决的用户场景。
2. 为行为变化补充或更新测试。
3. 运行上面的 Ruff、pytest 和 Godot headless 检查。
4. 不提交 `.env`、密钥、`Backend/.venv`、`.godot` 缓存或本地发布产物。

首版明确暂不包含：多人、任务系统、游戏内 NPC 编辑器、Qdrant、Neo4j，以及 Windows 以外的平台支持。

## 许可证

本项目基于 [MIT License](LICENSE) 开源。
