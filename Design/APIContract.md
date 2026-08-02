# API 契约设计

状态：Approved v1.0，已于 2026-08-02 确认

## 1. 通用约定

- 基础地址：`http://127.0.0.1:8765`
- API 前缀：`/api/v1`
- 编码：UTF-8 JSON
- 时间：UTC ISO 8601
- `player_id`：首版固定为 `local-player`，但契约保留字段。
- `client_request_id`：Godot 每次提交生成 UUID，用于幂等。
- `request_id`：后端生成 UUID，用于日志追踪。
- 公共错误不包含堆栈、密钥、SQL 或上游响应正文。

## 2. 健康检查

### `GET /health`

成功 `200`：

```json
{
  "status": "ready",
  "version": "0.1.0",
  "dialogue_mode": "mock",
  "database_ready": true,
  "content_version": "1"
}
```

`status` 为 `starting`、`ready` 或 `degraded`。`dialogue_mode` 为 `mock` 或 `model`。

## 3. NPC 列表

### `GET /api/v1/npcs`

成功 `200`：

```json
{
  "content_version": "1",
  "npcs": [
    {
      "npc_id": "zhang_xu",
      "name": "张旭",
      "title": "Python / AI 工程师",
      "appearance_key": "engineer_teal",
      "spawn": {"x": 284, "y": 206},
      "wander_enabled": true,
      "ambient_line": "正在核对一段测试输出。"
    }
  ]
}
```

API 只返回表现层需要的字段，不返回完整系统提示或行为边界。

## 4. 读取会话

### `GET /api/v1/conversations/{npc_id}?player_id=local-player&limit=20`

成功 `200`：

```json
{
  "npc": {
    "npc_id": "zhang_xu",
    "name": "张旭",
    "title": "Python / AI 工程师"
  },
  "relationship": {
    "score": 10,
    "level": "陌生"
  },
  "messages": [
    {
      "message_id": "0e2bd8f1-7c9d-4a92-b94a-f84ef36fd3a8",
      "role": "npc",
      "content": "你好。你想先聊实现，还是先说目标？",
      "created_at": "2026-08-02T12:00:00Z",
      "reply_source": "mock"
    }
  ]
}
```

- `limit` 默认 20，范围 1 至 50。
- NPC 不存在返回 `404 NPC_NOT_FOUND`。
- 首次会话返回空 `messages` 和初始关系。

## 5. 提交对话

### `POST /api/v1/dialogues`

请求：

```json
{
  "client_request_id": "ea49fb68-fc19-4030-a83e-cd6b7e6bb12f",
  "player_id": "local-player",
  "npc_id": "zhang_xu",
  "message": "我最近在做一个需要长期记忆的游戏。"
}
```

约束：

- `message` 去除首尾空白后长度为 1 至 300 个 Unicode 字符。
- `player_id` 长度 1 至 64，只允许字母、数字、下划线和短横线。
- `npc_id` 必须存在且启用。
- 同一个 `client_request_id` 只能代表一个完全相同的请求。

成功 `200`：

```json
{
  "request_id": "41ac7694-b665-4191-b1fb-02ef7d505c3c",
  "client_request_id": "ea49fb68-fc19-4030-a83e-cd6b7e6bb12f",
  "npc": {
    "npc_id": "zhang_xu",
    "name": "张旭",
    "title": "Python / AI 工程师"
  },
  "reply": "先把记忆的权威来源和检索边界拆开，否则很容易出现上下文串线。",
  "reply_source": "mock",
  "relationship": {
    "score": 12,
    "level": "陌生",
    "delta": 2,
    "reason": "认真交流"
  },
  "memory_saved": true,
  "degraded": false,
  "created_at": "2026-08-02T12:01:00Z"
}
```

`reply_source`：

- `mock`：主动选择的内置 mock 模式。
- `model`：真实模型成功响应。
- `fallback`：真实模型失败后使用的角色化降级回复。

当 `reply_source=fallback` 时，`degraded=true`，关系 `delta=0`，不会把降级回复当作高价值记忆。

## 6. 幂等行为

- 相同 `client_request_id` 和相同请求体再次提交，返回首次保存的完整结果，HTTP `200`。
- 相同 `client_request_id` 配合不同请求体，返回 `409 REQUEST_ID_CONFLICT`。
- Godot 收到重复结果时按 `client_request_id` 去重渲染。

## 7. 公共错误结构

```json
{
  "request_id": "b0ccb048-64af-4362-b27c-cb55a3e00d12",
  "error": {
    "code": "DATABASE_WRITE_FAILED",
    "message": "本次对话未能保存，请重试。",
    "retryable": true
  }
}
```

| HTTP | Code | 场景 | 可重试 |
| --- | --- | --- | --- |
| 400 | `INVALID_REQUEST` | JSON 或字段格式错误 | 否 |
| 404 | `NPC_NOT_FOUND` | NPC 不存在或未启用 | 否 |
| 409 | `REQUEST_ID_CONFLICT` | 幂等 ID 被不同请求复用 | 否 |
| 422 | `MESSAGE_REJECTED` | 空文本、过长或内容不允许 | 修改后可重试 |
| 503 | `DATABASE_UNAVAILABLE` | SQLite 无法访问 | 是 |
| 500 | `INTERNAL_ERROR` | 未分类服务错误 | 是 |

模型超时通常在服务内降级并返回 `200`，只有 mock 和 fallback 都无法产生合法回复时才返回错误。

## 8. 超时与重试

- Godot 对健康检查使用 2 秒超时，对对话使用 20 秒超时。
- 对话 POST 不自动盲重试；UI 使用同一个 `client_request_id` 由玩家主动重试。
- 健康检查允许退避重试。
- 后端模型调用超时应短于 Godot 对话超时，为序列化和写库留下时间。

## 9. 版本策略

首版只提供 `/api/v1`。新增字段必须保持旧客户端可忽略；删除、改名或改变语义需要新 API 版本。`content_version` 与 API 版本独立，用于 NPC 内容诊断。
