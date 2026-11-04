# 赛博小镇开发计划

状态：Approved v1.0，已于 2026-08-02 确认

需求基线：[REQUIRE.md](./REQUIRE.md)

设计基线：[BRIEF.md](./BRIEF.md) 与 [Design/](./Design/Architecture.md)

## 1. 交付目标

在 `E:/HelloAgents/Breakroom` 独立 Git 仓库内完成一个 Windows 可发布原型：玩家可在原创像素办公室中移动、与张旭、樊玥燚、胡佳烙交谈；对话、关系和长期记忆持久化；默认 mock 模式无需密钥；配置真实模型后启用 AI 回复；最终提供无需安装 Godot 或 Python 的发布目录。

开发只在本计划确认后开始。每个阶段必须通过对应验证门，不能用“代码已写完”代替运行证据。

## 2. 固定工具链

| 工具 | 固定选择 | 原因 |
| --- | --- | --- |
| Python | uv 管理的 CPython 3.11.15 | 本机已存在，依赖兼容面稳定，不使用系统 3.14.6 冒险 |
| Python 环境 | `Backend/.venv` | 与其他章节隔离，已由 Git 忽略 |
| 包管理 | uv 0.12.0 + `uv.lock` | 可复现安装与冻结构建 |
| 后端 | FastAPI + Uvicorn | 满足本地 HTTP API 与 OpenAPI 需求 |
| 数据 | stdlib SQLite + aiosqlite | 不引入 ORM，保留清晰事务边界 |
| HTTP/模型 | httpx | 同时用于测试、健康检查和 OpenAI 兼容接口 |
| 数据校验 | Pydantic / pydantic-settings | API 与 NPC 配置使用统一结构校验 |
| 后端测试 | pytest + pytest-asyncio | 覆盖异步服务、Repository 与 API |
| 静态检查 | Ruff | 格式和常见错误单一工具完成 |
| 后端发布 | PyInstaller one-folder | 无需系统 Python，便于诊断依赖 |
| 游戏引擎 | Godot 4.7.1 | 用户已提供并验证版本 |
| Godot 测试 | 内置 headless 测试脚本 | 首版不引入额外 Godot 测试插件 |

依赖版本由首阶段解析并写入 `uv.lock`；不在计划文档中猜测未来具体补丁版本。

除非命令旁另有说明，所有相对路径命令均从 `E:/HelloAgents/Breakroom` 执行。

## 3. 全程约束

- 不读取、打印、复制或提交 `Backend/.env`。
- 不新增 Python `__init__.py`；使用 namespace package 导入。
- 不依赖或复制 `Chapter11/Helix`，只实现已批准的 Breakroom（第十五章）边界。
- 不实现首版范围外的 Qdrant、Neo4j、任务、多场景、多人或管理后台。
- `Content/NPCProfiles.json` 是 NPC 内容唯一人工编辑源。
- 每个阶段只修改该阶段需要的文件，避免顺手重构其他章节。
- 测试产生的 `.godot`、`__pycache__`、`.pytest_cache`、构建临时目录等在最终交付前删除；发布目录作为交付物保留。
- 阶段提交前运行 `git diff --check`，确认 `.env` 被忽略，并检查没有意外文件进入暂存区。

## 4. 阶段 0：项目基础与可复现环境

### 范围

- 按批准的目标目录迁移当前空骨架，使用 PascalCase 能力目录和文件名。
- 删除被新结构取代的空文件；不删除任何包含用户内容的文件。
- 创建 `Backend/pyproject.toml`、`uv.lock` 和 Python 3.11 `.venv`。
- 建立最小 FastAPI 应用工厂、配置加载和测试框架。
- 调整 Godot 项目为 1280 x 720、像素纹理最近邻过滤和明确的输入映射。
- 创建 `Content/NPCProfiles.json`，写入三名默认虚构角色并完成双端最小校验。
- 填充 `.env.example`，只写变量名和安全示例，不复制现有 `.env`。

### 验证

```powershell
uv sync --project backend --python 3.11
uv run --project backend ruff check backend
uv run --project Backend pytest -q Backend/tests
D:\Godot\Godot_v4.7.1-stable_win64_console.exe --headless --path Game --editor --quit
```

### 阻塞门

- 配置文件合法时 Python 和 Godot 均能加载三名 NPC。
- 故意制造重复 `npc_id` 的测试能返回字段路径明确的错误。
- Godot 无脚本解析或资源导入错误。
- `.env` 仍未被 Git 跟踪。

### 提交

`build: establish Chapter15 project foundation`

## 5. 阶段 1：Mock 后端垂直链路

### 范围

- 实现 Domain、Schema、NPCConfigLoader 与 NPCService。
- 实现 `BaseDialogueModelClient`、`MockDialogueModelClient`、`NPCContextBuilder` 和 `NPCDialogueAgent`。
- 实现 `GET /health`、`GET /api/v1/npcs` 和 `POST /api/v1/dialogues` 的无持久化垂直链路。
- mock 回复结合 NPC 身份、表达风格和玩家消息，三名角色可区分。
- 建立统一错误结构、`request_id` 和脱敏结构化日志。

### 验证

- API 测试覆盖正常请求、未知 NPC、空消息、超长消息和错误结构。
- 分别向三名 NPC 发送同一消息，断言回复具有不同角色特征。
- 启动服务后 `GET /health` 返回 `ready`、`mock` 和正确内容版本。
- 日志扫描确认不存在环境变量值、认证头或密钥字段。

### 阻塞门

在没有任何模型密钥的环境中，三个 API 均可运行，所有后端测试与 Ruff 检查通过。

### 提交

`feat: add configurable mock NPC dialogue API`

## 6. 阶段 2：SQLite、关系与记忆

### 范围

- 实现显式 SQLite 迁移和 Database 事务边界。
- 实现 DialogueRepository、RelationshipRepository 和 MemoryRepository。
- 实现 DialogueService 幂等处理及 `player_id + npc_id` 进程内锁。
- 实现确定性 RelationshipService：标签白名单、重复抑制、单回合限制和每日正向上限。
- 实现 MemoryService：结构化事实提取、规范化词项、去重、排序和最多三条检索。
- 实现会话读取 API，并将模型调用结果、关系事件和记忆候选一次事务提交。

### 验证

- 单元测试覆盖全部关系等级边界、正负标签、重复消息、每日上限和 fallback 零变化。
- 记忆测试覆盖姓名、偏好、已讨论事件、无关记忆排除和跨 NPC/跨玩家隔离。
- API 测试覆盖相同 `client_request_id` 重放和冲突。
- 故意在事务中制造错误，断言 turn、关系和记忆均未部分写入。
- 重启测试确认历史、关系和记忆可恢复。

### 阻塞门

完成 `AC-04`、`AC-06` 和 `AC-08` 的后端级自动化证据，数据库 schema 与批准的 DataModel 一致。

### 提交

`feat: persist dialogue relationships and memory`

## 7. 阶段 3：Godot 可玩垂直切片

### 范围

- 创建可重复生成的原创占位像素资源：玩家、三名 NPC、办公室图块、家具和 UI 图标。
- 所有角色为原创虚构外观，不使用真人照片或肖像特征。
- 实现 Main、Player、NPC、DialogueUI、InteractionPrompt 和 StartupOverlay 场景。
- 实现 WASD/方向键移动、碰撞、受限巡逻、最近且朝向优先的交互目标选择。
- 实现异步 APIClient、会话打开、发送、等待、重试、关闭和关系变化反馈。
- 后端不可达时仍允许移动和关闭对话。
- 运行时从统一 NPC 配置生成三名场景角色，不按姓名写死分支。

### 验证

- Headless 测试覆盖内容加载、目标选择、对话状态机和重复响应去重。
- Godot 运行日志无 parser error、invalid node path 或缺失资源。
- 在 1280 x 720 和 1600 x 900 截图检查：画面非空、角色可识别、文字不重叠、交互提示不越界、对话面板不遮挡关键目标。
- 手动完成移动、碰撞、E 键交互、发送、回复、关闭和切换 NPC。
- 断开后端后验证场景仍可操作。

### 阻塞门

完成 `AC-01`、`AC-02`、`AC-03` 和 Godot 部分的 `AC-07`；若视觉检查失败，先迭代素材和布局再继续。

### 提交

`feat: deliver playable Godot mock vertical slice`

## 8. 阶段 4：真实模型适配

### 用户输入门

开始本阶段前需要用户提供以下元数据，不提供密钥内容：

- 模型服务商。
- 模型名称。
- 是否兼容 OpenAI Chat Completions API。
- `base_url`。
- API Key、模型名和 base URL 对应的环境变量名称。

密钥由用户自行保存在已忽略的 `Backend/.env` 或系统环境变量中。

### 范围

- 实现 `OpenAICompatibleDialogueModelClient`；如果服务不兼容，则新增对应的具体 Client，而不修改 DialogueService。
- 模型输出限定为回复、互动标签和记忆候选，完成结构校验、长度限制和未知标签过滤。
- 实现上下文预算：最近五个 turn、最多三条长期记忆、关系阶段和 NPC 配置。
- 模型超时、网络错误或无效结构自动走角色化 fallback，关系不变化。
- mock 模式继续作为默认和自动化测试路径。

### 验证

- 使用 httpx 假传输覆盖成功、超时、HTTP 错误、非 JSON、超长回复和未知标签。
- 使用用户配置的真实模型分别测试三名 NPC 的身份区分、上下文隔离和记忆召回。
- 检查发给模型的内容不包含其他 NPC、其他玩家、密钥或完整数据库记录。

### 阻塞门

真实模型冒烟通过，或明确记录外部服务阻塞；不能用 mock 测试冒充真实模型验收。

### 提交

`feat: integrate bounded AI dialogue model`

## 9. 阶段 5：健壮性、体验与可观察性

### 范围

- 完成后端启动、健康轮询、端口冲突、模型降级和配置版本不一致状态。
- Godot 启动后端并只管理本次创建的 PID；关闭游戏时清理该进程。
- 完成请求耗时、记忆命中、关系规则和错误分类日志。
- 调整原创像素资产、色板、字体、焦点顺序、等待动画和错误反馈。
- 添加长期运行测试，检查重复打开对话、快速切换目标和连续请求。

### 验证

- 模拟模型超时、SQLite 锁、后端退出、端口占用和错误 NPC 配置。
- 连续完成至少 30 次 mock 对话，无重复计分、串线、输入永久锁死或子进程泄漏。
- 键盘完成打开、输入、发送、重试和关闭全过程。
- 日志能用一个 `request_id` 串联完整对话过程。

### 阻塞门

完成全部故障降级需求，后端和 Godot 测试通过，视觉复查无文本重叠与明显布局跳动。

### 提交

`fix: harden runtime and dialogue experience`

## 10. 阶段 6：Windows 发布构建

### 范围

- 安装并验证 Godot 4.7.1 Windows export template；这是当前已知缺失前置。
- 提交 `export_presets.cfg`，不提交 `.godot/export_credentials.cfg`。
- 实现 PyInstaller one-folder 后端构建和完整发布组装脚本。
- 填充现有 `README.md`、发布 `README.txt`、许可证与真实模型配置说明。
- 生成 `Breakroom.exe`、`Breakroom.pck`、Backend、Content、LICENSES、ZIP 和 SHA-256。
- 构建脚本扫描并拒绝密钥、数据库、日志、缓存和测试文件。

### 验证

- 用不包含 Python 和 Godot 的精简 PATH 启动发布目录。
- 默认 mock 模式启动并完成一次对话。
- 启动、退出、再次启动后端口可复用且没有遗留子进程。
- 修改发布目录 NPC 名称和性格后重启，显示和对话均更新，原 ID 历史保留。
- 对发布目录执行敏感文件和生成物扫描。

### 阻塞门

完成 `AC-05`、`AC-10` 和发布形态要求；发布包必须在没有开发工具的调用路径下运行。

### 提交

`build: package Windows Breakroom prototype`

## 11. 阶段 7：最终验收与清理

### 验收矩阵

逐条执行 [REQUIRE.md](./REQUIRE.md) 的 `AC-01` 至 `AC-10`，为每项记录命令、结果和必要截图。不得只写“通过”。

最终证据至少包含：

- 后端完整 pytest 输出和 Ruff 输出。
- Godot headless 解析与测试输出。
- 1280 x 720、1600 x 900 主场景和对话状态截图。
- mock 模式、真实模型模式、模型 fallback、后端离线四条交互记录。
- SQLite 重启恢复、跨 NPC 隔离和配置改名证据。
- 发布目录扫描、进程清理和精简 PATH 启动结果。

### 清理

- 删除本次生成且不属于交付物的 `.godot`、`__pycache__`、`.pytest_cache`、`.ruff_cache`、PyInstaller work 目录和临时截图。
- 保留最终 Release 目录、验收截图和必要构建配置。
- 重新运行核心测试，确认清理未破坏交付物。
- 检查 Git 暂存区和工作区；除明确忽略的本地 `.env` 外，交付源文件应全部提交。

### 最终提交

`test: record Chapter15 acceptance evidence`

## 12. 计划执行规则

- 计划确认后按阶段连续推进，阶段门失败时在当前阶段修复，不跳到下一阶段掩盖问题。
- 批准的需求或设计如需改变，先说明原因和影响，再更新对应基线文档；不在代码中悄悄改变范围。
- 每个阶段提交后记录 commit ID；当前仓库没有远程，不执行 push，除非用户后续提供远程并明确要求。
- 真实模型外部服务是唯一预期需要用户后续输入的开发门；美术素材无需用户提供。
