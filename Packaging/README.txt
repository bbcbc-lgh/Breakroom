Cyber Town 0.1.0 - Windows x86_64
=================================

运行
----
1. 解压整个压缩包，保留目录结构。
2. 双击 CyberTown.exe。首次启动会同时启动本地后端。
3. 使用 WASD 或方向键移动，靠近 NPC 后按 E 交互。
4. 在对话框中输入文字，Enter 或“发送”提交，Esc 或“关闭”退出对话。

默认模式
--------
无需 Python、Godot、网络或 API Key。没有完整模型配置时，程序自动使用 mock 回复。
本地对话与日志保存在 %APPDATA%\CyberTown，不写入发布目录。

真实模型（可选）
----------------
在 %APPDATA%\CyberTown\.env 创建 UTF-8 文本文件，填入：

CYBER_TOWN_MODEL_BASE_URL=https://your-provider.example/v1
CYBER_TOWN_MODEL_NAME=your-model-name
CYBER_TOWN_MODEL_API_KEY=your-api-key
CYBER_TOWN_MODEL_TIMEOUT_SECONDS=15

也可以使用兼容别名 LLM_BASE_URL、LLM_MODEL_ID、LLM_API_KEY。
三项模型配置必须同时存在；缺少任一项会安全回退到 mock。修改后重启游戏。

NPC 配置
--------
Content\NPCProfiles.json 是唯一人工编辑源。可修改姓名、职业、性格、说话风格等字段，
保存后重启游戏生效。请保持 npc_id 不变，否则已有对话、关系与记忆不会关联到新 ID。
JSON 格式或字段错误会阻止后端启动，并在启动界面显示不可用状态。

故障排查
--------
- 8765 端口被其他程序占用时，关闭占用程序后在启动界面重试。
- 日志：%APPDATA%\CyberTown\Logs\CyberTown.log
- 数据库：%APPDATA%\CyberTown\Data\CyberTown.db
- 若模型服务不可用，NPC 会给出降级回复，游戏场景仍可操作。

已知限制
--------
- 首版仅支持 Windows x86_64、单人、本地 SQLite 和一个办公室场景。
- 不包含 Qdrant、Neo4j、多人、任务系统或游戏内 NPC 编辑器。
- 占位像素美术为原创原型资源，后续可以替换。

许可证信息见 LICENSES 目录。
