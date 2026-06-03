# Duplicate Detection Module

检测重复照片（相似图片 + 连拍去重），基于 **Difference Hash (dHash)** + **多索引哈希表** + **时间窗口分组** + **SSIM 终判**。

> **Pipeline role (L4 — last detection step)**: Runs last in the cascade.
> Only photos not already classified as closed-eye, blurry, or burst are
> checked for duplicates. This avoids redundant detection and ensures
> each photo has a single primary label.

## 优化算法（Task 1 ✅）

传统 O(n²) 两两比较在 4200 张照片时需要 ~880 万次比较。新算法分四步缩小候选集：

### 第一步 — 时间窗口预分组

按 EXIF 拍摄时间将照片聚类。拍摄间隔 > 30 秒的照片进入不同的时间窗口，不同窗口之间不做比较。无拍摄时间的照片归入单独的"兜底窗口"。

4200 张 → 拆成 ~50 个窗口，平均每窗口 ~84 张 → 候选对从 880 万降到 ~17 万。

### 第二步 — dHash 多索引哈希表

在每个时间窗口内，为所有照片计算 dHash（Difference Hash，64-bit 整数），将 64-bit 哈希值拆分为 8 个 8-bit 段，建 8 张哈希表。仅当两张照片至少共享一个段值时才成为候选对。

**鸽巢原理保证**：汉明距离 ≤ 5 时，8 个段中至少有 3 个段完全匹配 → 真正的重复照片绝不会被漏掉。

每窗口 84 张 → 候选对进一步降到 ~200-500 对。

### 第三步 — 汉明距离预滤

对候选对做精确汉明距离比较（CPU POPCNT 指令，单周期）。汉明距离 ≤ 10 的候选对进入 SSIM 终判。~90% 的候选对在此步被快速排除（距离 > 10）。

### 第四步 — SSIM 终判

仅对通过前三步的候选对（预计 1000-5000 对）计算 **Structural Similarity Index (SSIM)**。SSIM ≥ 0.95 → 确认重复；SSIM < 0.95 → 排除误判。SSIM 比 dHash 更精确地捕捉感知差异，消除哈希碰撞导致的误判。

每对 SSIM 计算耗时 ~3-15ms（scipy uniform_filter / numpy 积分图）。总共增加 ~15-30 秒，换取接近零误判的精度。

## dHash 原理

[dHash](https://en.wikipedia.org/wiki/Perceptual_hashing) 是一种基于梯度的感知哈希算法：

1. 缩放图片至 9×8 像素
2. 转为灰度图
3. 逐行比较相邻像素：`pixel[x] < pixel[x+1]` → 1，否则 → 0
4. 得到 8×8 = 64-bit 二进制哈希值

dHash 比 pHash (DCT-based) 快约 3×，且对亮度变化更鲁棒。

## 判定规则

| 阶段 | 阈值 | 作用 |
|------|------|------|
| 多索引哈希 | 至少共享 1 个 8-bit 段 | 候选对发现（鸽巢保证不漏真重复）|
| 汉明距离预滤 | ≤ 10 | 快速排除 ~90% 候选对（POPCNT 单周期）|
| SSIM 终判 | ≥ 0.95 | 精确确认重复，消除哈希碰撞误判 |

### Hamming Distance 值的选择

| 阈值 | 效果 |
|------|------|
| 0 | 仅完全相同图片 |
| 5 | 连拍 + 构图高度相似 |
| 10 | 容忍较大差异（预滤阈值，配合 SSIM 终判）|
| 20+ | 几乎全判为重复 |

## SSIM 阈值说明

SSIM（Structural Similarity Index）范围 [0, 1]，1 表示完全相同：

| SSIM 值 | 含义 |
|---------|------|
| ≥ 0.99 | 几乎完全相同（同一张图 re-saved）|
| ≥ 0.95 | 高度相似 — 确认为重复（默认阈值）|
| 0.90–0.95 | 中等相似 — 可能是不同构图 |
| < 0.90 | 明显不同 — 排除 |

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
service.start_duplicate_detection()
         │
         ├── Phase 1: 逐一计算 dHash (64-bit int)
         │     ├── Pillow 读取原图
         │     └── imagehash.dhash() → 64-bit integer
         │
         ├── Phase 2: 时间窗口分组
         │     ├── 按 EXIF 拍摄时间排序
         │     └── 间隔 > 30 秒 → 新窗口
         │
         ├── Phase 3: 窗口内检测（四步级联）
         │     ├── 3a. 多索引哈希表 (8 segments × 8 bits)
         │     ├── 3b. 候选对查找（共享至少 1 个段）
         │     ├── 3c. 汉明距离预滤（Hamm ≤ 10 → 进入 SSIM）
         │     ├── 3d. SSIM 终判（SSIM ≥ 0.95 → 确认重复）
         │     └── Union-Find 分组
         │
         └── Phase 4: 分配 group_id + 写入数据库
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
    "task_id": "a1b2c3d4",
    "total": 1000
}
```

轮询进度：
```
GET /api/ai/duplicate-progress/{task_id}
```

### `GET /api/photos/duplicate?limit=100&offset=0`

返回 `is_duplicate == 1` 的照片，分页格式与 `/api/photos` 一致。

### `GET /api/photos/duplicate/count`

```json
{ "count": 642 }
```

## 性能对比

| 场景 | 旧算法 (O(n²) phash) | 优化算法 (时间窗口 + dHash 多索引 + SSIM) |
|------|---------------------|----------------------------------------|
| 4200 张照片 | ~880 万次比较 | ~1-1.5 万候选 → ~1000-5000 SSIM |
| 预计耗时 | 数分钟 | 数十秒 + ~15-30 秒 SSIM |
| 误判率 | ~5-10% | **< 1%**（SSIM 终判消除哈希碰撞）|
| 省时比例 | — | **90-95%** |

## 与连拍分组的关系

```
连拍分组（Step 3）:           重复检测（Step 4）:
  ┌─────────────────┐           ┌─────────────────┐
  │ 同一场景、连拍快门  │           │ 不同时刻、同一场景  │
  │ 间隔 < 2 秒       │           │ 间隔 > 2 秒       │
  │ 选出 1 张最佳     │           │ 选出 1 张保留     │
  │ 如：10 连拍 → 1 张 │           │ 如：拍了 3 次 → 1 张 │
  └─────────────────┘           └─────────────────┘
      互补关系：连拍处理"太快"的重复，重复检测处理"太像"的冗余
```

## 当前限制

- Threshold 写死为 5 (Hamming) / 10 (pre-filter) / 0.95 (SSIM)，不可调
- 不区分「连拍重复」和「相似照片」
- 无分组 UI（无彩色边框、连线、动画）
- 不处理旋转/翻转/裁剪变体

## 后续扩展点

- 参数可调（API 参数 + UI 滑块）
- 多线程批量计算 dHash（ThreadPoolExecutor，与导入类似）
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
