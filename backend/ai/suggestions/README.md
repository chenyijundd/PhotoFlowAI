# AI Suggestions Module

AI 建议层 — 第一版规则驱动的辅助选片建议系统。

## 核心哲学

**AI 只能 Suggest，永远不 Decide。**

- AI 建议是辅助信息，不是自动决策
- 用户始终拥有最终控制权
- 建议可接受也可忽略
- 任何用户操作都会触发建议自动失效和重新生成

## 模块结构

```
backend/ai/suggestions/
├── __init__.py    # 模块入口
├── models.py      # 数据模型（SuggestionType 枚举、请求/响应）
├── rules.py       # 规则引擎（纯函数，无副作用）
├── service.py     # 编排服务（分页处理、批量写入）
└── README.md      # 本文件
```

## 建议类型 (Suggestion Types)

### POSSIBLE_BLUR
- **规则：** `is_blur == 1`
- **含义：** 该照片被模糊检测标记，可能不够清晰
- **接受行为：** 自动 Reject

### POSSIBLE_DUPLICATE
- **规则：** `duplicate_group != null`
- **含义：** 该照片属于重复组，可能有更好的选择
- **接受行为：** 无操作（仅信息提示）

### POSSIBLE_BEST (V2)
- **规则：** 非废片 (`is_rejected == 0`) 且 非模糊 (`is_blur == 0`) 且 `blur_score > 200`
- **含义：** 该照片清晰度高，值得优先考虑
- **接受行为：** 自动 Star

### 优先级

每张照片最多一条建议。规则按以下优先级匹配（先匹配先生效）：

1. `POSSIBLE_BEST` — 先判断是否为最佳照片
2. `POSSIBLE_BLUR` — 再判断是否模糊
3. `POSSIBLE_DUPLICATE` — 最后判断是否重复

## API

### POST /api/ai/generate-suggestions

生成 AI 建议。**幂等** — 重复运行覆盖旧建议。

**请求：**
```json
{
  "photo_ids": null   // null = 全部照片；可传入 ID 列表部分生成
}
```

**响应：**
```json
{
  "processed": 1200,
  "suggestions_generated": 342,
  "suggestion_counts": {
    "POSSIBLE_BLUR": 45,
    "POSSIBLE_DUPLICATE": 280,
    "POSSIBLE_BEST": 17
  }
}
```

### 其他 API

- `GET /api/photos/suggested` — 获取有建议的照片（分页）
- `GET /api/photos/suggested/count` — 获取建议数量

## 数据库

新增字段 `ai_suggestion TEXT`（自动 Migration）。

- `NULL` — 无建议
- `"POSSIBLE_BLUR"` — 可能模糊
- `"POSSIBLE_DUPLICATE"` — 可能重复
- `"POSSIBLE_BEST"` — 最佳照片

## 性能

- 分页处理（200 条/批次），不会一次性加载所有照片
- 使用 `update_photos_batch` 批量写入数据库
- 生成 5000 张照片的建议约需数秒

## 建议安全 (Suggestion Safety)

以下操作会自动触发建议失效和重新生成：

- 运行模糊检测
- 运行重复检测
- 手动 Star / Reject（键盘操作）
- 接受 AI 建议（A 键）

## CLI 运行方式

```bash
# 通过 API 端点触发
curl -X POST http://127.0.0.1:8765/api/ai/generate-suggestions \
  -H "Content-Type: application/json" \
  -d '{"photo_ids": null}'
```

## 当前限制

- 仅支持三种建议类型
- 纯规则驱动，无机器学习
- 单建议（每张照片一条），非数组
- 建议接受后自动重新生成（非增量更新）
- 无建议历史/审计日志

## 后续扩展点

- 增加更多建议类型（闭眼、表情、构图）
- 建议置信度评分
- 增量更新（非全量重新生成）
- 用户反馈学习
- ML 模型替代规则引擎
- 多建议支持（数组）
