# SQLite 数据与记忆设计

状态：Approved v1.0，已于 2026-08-02 确认

## 1. 数据边界

SQLite 保存玩家-NPC 对话、关系和长期记忆。NPC 人设本身不写入数据库，以 `Content/NPCProfiles.json` 为权威来源。

数据库位于用户数据目录，不放在安装目录。开发和测试数据库相互隔离。

## 2. 核心表

### `schema_migrations`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `version` | INTEGER | PRIMARY KEY |
| `applied_at` | TEXT | NOT NULL |

使用显式递增迁移，不在启动时用隐式 ORM 自动改表。

### `players`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `player_id` | TEXT | PRIMARY KEY |
| `display_name` | TEXT | NOT NULL |
| `created_at` | TEXT | NOT NULL |

首版创建 `local-player`，但后续可增加玩家而不改其他表主键语义。

### `dialogue_turns`

一次玩家请求及 NPC 回复形成一个 turn。

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `turn_id` | TEXT | PRIMARY KEY UUID |
| `request_id` | TEXT | UNIQUE NOT NULL |
| `client_request_id` | TEXT | UNIQUE NOT NULL |
| `request_fingerprint` | TEXT | NOT NULL |
| `player_id` | TEXT | NOT NULL, FK players |
| `npc_id` | TEXT | NOT NULL |
| `npc_name_snapshot` | TEXT | NOT NULL |
| `player_message` | TEXT | NOT NULL |
| `npc_reply` | TEXT | NOT NULL |
| `reply_source` | TEXT | CHECK mock/model/fallback |
| `interaction_tags_json` | TEXT | NOT NULL |
| `relationship_delta` | INTEGER | NOT NULL |
| `relationship_reason` | TEXT | NOT NULL |
| `memory_saved` | INTEGER | NOT NULL |
| `created_at` | TEXT | NOT NULL |

索引：`(player_id, npc_id, created_at DESC)`。

### `relationships`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `player_id` | TEXT | 复合主键 |
| `npc_id` | TEXT | 复合主键 |
| `score` | INTEGER | CHECK 0..100 |
| `interaction_count` | INTEGER | NOT NULL |
| `positive_points_today` | INTEGER | NOT NULL |
| `positive_points_date` | TEXT | NOT NULL |
| `updated_at` | TEXT | NOT NULL |

初始分数为 10，属于“陌生”。显示等级不冗余存储，由分数计算。

### `relationship_events`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `event_id` | TEXT | PRIMARY KEY UUID |
| `turn_id` | TEXT | UNIQUE NOT NULL, FK turns |
| `player_id` | TEXT | NOT NULL |
| `npc_id` | TEXT | NOT NULL |
| `rule_id` | TEXT | NOT NULL |
| `old_score` | INTEGER | NOT NULL |
| `delta` | INTEGER | NOT NULL |
| `new_score` | INTEGER | NOT NULL |
| `reason` | TEXT | NOT NULL |
| `created_at` | TEXT | NOT NULL |

### `memory_events`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `memory_id` | TEXT | PRIMARY KEY UUID |
| `source_turn_id` | TEXT | FK turns |
| `player_id` | TEXT | NOT NULL |
| `npc_id` | TEXT | NOT NULL |
| `memory_type` | TEXT | CHECK player_fact/preference/shared_topic/commitment/milestone |
| `summary` | TEXT | NOT NULL |
| `normalized_terms_json` | TEXT | NOT NULL |
| `importance` | INTEGER | CHECK 1..5 |
| `created_at` | TEXT | NOT NULL |
| `last_recalled_at` | TEXT | NULL |
| `recall_count` | INTEGER | NOT NULL DEFAULT 0 |

索引：`(player_id, npc_id, importance DESC, created_at DESC)`。

## 3. 关系规则

模型或 mock 分析器只能返回白名单标签。RelationshipService 用规则表计算：

| Rule ID | 标签 | 基础变化 |
| --- | --- | --- |
| `REL_HELPFUL` | `helpful` | +3 |
| `REL_RESPECTFUL` | `respectful` | +2 |
| `REL_PERSONAL` | `shares_personal_fact` | +1 |
| `REL_CURIOUS` | `curious` | +1 |
| `REL_NEUTRAL` | `neutral` | 0 |
| `REL_RUDE` | `rude` | -4 |
| `REL_HOSTILE` | `hostile` | -6 |
| `REL_REPEAT` | 重复消息命中 | 0，并覆盖正向标签 |

规则约束：

- 单回合总变化限制在 -6 至 +4。
- 同一玩家与 NPC 十分钟内重复相同规范化消息不增加关系。
- 每个玩家-NPC 自然日正向累计上限为 +12，负向变化不受该上限保护。
- fallback 回复不改变关系。
- 等级区间保持 0--20、21--40、41--60、61--80、81--100。

规则 ID、权重和上限写在代码中的单一常量表并由测试锁定；首版不提供外部可调规则文件，避免内容修改破坏数据规则。

## 4. 短期上下文

短期上下文不需要独立缓存表。每次从 `dialogue_turns` 读取该 `player_id + npc_id` 最近五个 turn，即最多十条消息，并优先选择 120 分钟内记录。

若 120 分钟内没有记录，只保留最近一个 turn 作为会话衔接，其余历史通过长期记忆进入上下文。

## 5. SQLite 长期记忆检索

首版不假装拥有向量语义检索。采用可解释的结构化词项匹配：

1. 保存前将记忆候选规范化为简短事实，并提取名称、主题和关键短语。
2. 从同一 `player_id + npc_id` 读取最近且重要的最多 50 条候选。
3. 对当前消息与 `normalized_terms_json` 做完全匹配、包含匹配和中文双字词重叠评分。
4. 加入重要性、最近召回时间和创建时间权重。
5. 选取最多三条，且必须超过最低相关阈值。

这能稳定支持“我叫……”“我喜欢……”“上次讨论……”等首版验收场景。未来向量实现替换 MemoryRepository 的检索策略，不改变上层接口。

## 6. 记忆写入策略

- mock 模式通过明确句式和关键词提取玩家事实、偏好与承诺。
- model 模式允许模型提出候选，但必须满足类型白名单、长度、来源和去重规则。
- 普通寒暄不写长期记忆。
- 同一规范化事实已存在时更新重要性或召回信息，不创建无限重复记录。
- NPC 回复本身不能单独成为“玩家事实”。

## 7. 事务边界

模型调用完成后，在一个 SQLite 事务中执行：

1. 再次检查 `client_request_id`。
2. 插入 `dialogue_turns`。
3. 插入或更新 `memory_events`。
4. 更新 `relationships`。
5. 插入 `relationship_events`。
6. 提交并返回持久化后的权威结果。

任何一步失败则全部回滚，API 不返回伪成功。

## 8. 数据生命周期

- 首版不在 UI 提供删除数据功能。
- 开发者可删除用户数据目录中的数据库以重置游戏，README 必须说明路径和后果。
- 发布包不携带开发数据库。
- 日志只记录必要摘要，完整对话以数据库为准。
