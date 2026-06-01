# Duplicate Detection Module

检测重复照片（相似图片 + 连拍去重），基于 **Perceptual Hash (phash)** 算法。

> **Pipeline role (L4 — last detection step)**: Runs last in the cascade.
> Only photos not already classified as closed-eye, blurry, or burst are
> checked for duplicates. This avoids redundant detection and ensures
> each photo has a single primary label.

## Perceptual Hash 原理

[pHash](https://en.wikipedia.org/wiki/Perceptual_hashing) 是一种感知哈希算法，通过以下步骤为每张图片生成一个 64-bit 指纹：

1. 缩小图片至 32×32 像素，忽略高频细节
2. 转为灰度图
3. 应用离散余弦变换（DCT），提取低频信息
4. 取左上 8×8 的 DCT 系数
5. 以中位数为阈值，生成 64-bit 二进制哈希值

**直觉**：相似的图片具有相似的 pHash 值，差异越小说明图片越相似。

## Hamming Distance 规则

- `Hamming Distance <= 5` → 判定为重复图片
- `Hamming Distance > 5` → 判定为不同图片

Hamming Distance 是两个哈希值之间不同比特位的数量。阈值 5 在检测连拍照片和相似照片之间取得了良好的平衡。

### 值的选择说明

| 阈值 | 效果 |
|------|------|
| 0 | 仅完全相同图片 |
| 5 | 连拍 + 构图相似（当前默认）|
| 10 | 容忍较大差异（可能误判）|
| 20+ | 几乎全判为重复 |

## duplicate_group_id 机制

同组重复照片共享同一 `duplicate_group_id`：

```
dup_0001 → photo_a.jpg, photo_b.jpg（连拍）
dup_0002 → photo_c.jpg, photo_d.jpg, photo_e.jpg（相似构图）
```

- 格式：`dup_NNNN`（从 0001 开始自增）
- GROUP 内所有照片的 `is_duplicate = 1`
- 无重复的照片：`is_duplicate = 0`, `duplicate_group = NULL`

## 数据流

```ascii
用户点击「检测重复照片」
         │
         ▼
POST /api/ai/duplicate-detect  { photo_ids: [...] }
         │
         ▼
service.run_duplicate_detection()
         │
         ├── Step 1: 逐一计算 pHash
         │     ├── Pillow 读取原图（禁用缩略图）
         │     └── imagehash.phash() → 64-bit hash
         │
         ├── Step 2: 两两比较 Hamming Distance
         │     └── Union-Find 分组
         │
         ├── Step 3: 分配 group_id
         │     └── dup_0001, dup_0002, ...
         │
         └── Step 4: 写入数据库
               ├── repo.update_duplicate_status(id, 1, group_id)
               └── 日志记录到 logs/duplicate_detection.log
```

## API 说明

### `POST /api/ai/duplicate-detect`

请求：
```json
{
    "photo_ids": ["id1", "id2", "..."]
}
```

响应：
```json
{
    "processed": 1000,
    "duplicate_groups": 128,
    "duplicates": 642
}
```

### `GET /api/photos/duplicate?limit=100&offset=0`

返回 `is_duplicate == 1` 的照片，分页格式与 `/api/photos` 一致。

### `GET /api/photos/duplicate/count`

```json
{ "count": 642 }
```

## 当前限制

- Threshold 写死为 5，不可调
- O(n²) 两两比较（大数据集较慢，3000 张约 450 万次比较）
- 不支持多线程 / GPU 加速
- 单张失败不影响整体（自动跳过）
- **不做最佳照片选择** — 只检测和标记，不自动保留哪张
- 不区分「连拍重复」和「相似照片」
- 无分组 UI（无彩色边框、连线、动画）
- 不处理旋转/翻转/裁剪变体

## 后续扩展点

- Threshold 可调参数（API 参数 + UI 滑块）
- 使用 FAISS 或类似向量检索引擎加速（替代 O(n²) 比较）
- 多线程批量处理
- 自动保留最佳照片（基于 blur_score + eye_score 综合评分）
- 分组 UI（彩色边框标记同组照片）
- 批量操作（全选同组、一键保留最佳）
- 导出时自动排除重复
- 深度学习 Embedding 升级路径
- 人脸聚类去重

---

## Compare Mode（双图对比选片模式）

在完成重复检测后，摄影师可对同一 `duplicate_group` 内的照片进行双图对比，快速决定保留/淘汰。

### 进入 Compare Mode

1. 点击某张**带有 `duplicate_group` 标记**的照片（即被判定为重复的照片）
2. 按键盘 **C** 键
3. 进入双图对比界面

### UI 布局

```
┌──────────────────────────────────────────────────────┐
│ COMPARE MODE    dup_0001    2 / 5    ← → · Tab · ESC │
├──────────────────────────┬───────────────────────────┤
│                          │                           │
│     LEFT PHOTO           │       RIGHT PHOTO         │
│     (active border)      │                           │
│                          │                           │
│  filename      ★        │  filename                 │
└──────────────────────────┴───────────────────────────┘
```

- 左右各占 50% 空间
- 当前激活的一侧有**红色边框**（`#e94560`）
- 激活侧底部显示「当前」标签

### 键盘快捷键

| 按键 | 功能 |
|------|------|
| `C` | 进入 Compare Mode（需选中带 duplicate_group 的照片）|
| `←` / `→` | 在 duplicate group 内切换对比照片对 |
| `Tab` | 切换激活侧（LEFT ↔ RIGHT）|
| `Space` | 对**当前激活照片**切换星标（★）|
| `X` | 对**当前激活照片**切换 Reject 标记 |
| `ESC` | 退出 Compare Mode，返回浏览模式 |

### 对比照片对导航

- 场景：`dup_0001` 包含 A、B、C、D、E 五张照片
- 初始进入选中 B：显示 B vs C
- 按 `→`：C vs D
- 按 `→`：D vs E
- 按 `←`：B vs C
- 依此类推
- **不会跨组** — 只能在当前 `duplicate_group` 内切换
- 当当前照片在组内最后一张时，无法继续右移

### Space / X 规则

- **始终作用于当前激活的照片**
- 按 `Tab` 切换激活侧后再按 Space/X，作用于另一张
- 星标在 0 和 1 之间切换
- Reject 在 0 和 1 之间切换
- 更新后即时在 UI 中反映

### 状态机

```
[浏览模式] ──C──→ [Compare Mode]
                   │
                   ├── ←/→ → 导航组内照片
                   ├── Tab  → 切换激活侧
                   ├── Space → 标星/取消
                   ├── X    → Reject/取消
                   └── ESC  → [浏览模式]（刷新网格）
```

### 安全性处理

- 当前激活照片被 Reject → 不会崩溃，UI 显示 REJECT 标签
- 当前激活照片取消星标 → 不会崩溃，星标图标更新
- Compare pair 因数据变更消失 → 不会崩溃
- 加载失败 → 显示错误信息和退出按钮

### 当前限制

- 仅支持**双图**对比（不支持多图）
- 自动选择同组下一张作为对比对象（不支持手动选择）
- 无对比列表 UI
- 无 fancy 动画、split drag、resize
- 无 AI 最佳推荐
- 无鼠标同步缩放
- 进入 Compare Mode 后隐藏 Detail Panel
- 不处理照片删除场景

### 后续扩展点

- 多图对比（3+ 张并列）
- 手动选择对比对象
- Compare list UI（缩略图列表）
- Filmstrip 底部条
- 自动同步缩放 / 鼠标拖拽
- AI 辅助推荐（blur_score + eye_score）
- 快捷键自定义
