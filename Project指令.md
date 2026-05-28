把下面这段完整发给 Claude。

---

# Task 1：实现本地图片扫描系统（禁止实现其他功能）

请严格按照以下要求开发。

---

# 目标

实现：

# 本地图片文件夹扫描模块

当前阶段：
只允许实现“扫描与数据返回”。

禁止实现：

* AI功能
* UI美化
* 缩略图
* 数据库
* 导出
* 多线程优化
* GPU
* 任何额外功能

---

# 技术要求

后端：

* Python

要求：

* 模块化
* 可长期维护
* CLI 可运行
* 可独立测试

---

# 功能要求

实现：

## 1. 扫描指定目录

支持：

* 递归扫描子目录

支持图片格式：

* .jpg
* .jpeg
* .png

暂不支持：

* RAW
* GIF
* WEBP

---

## 2. 返回图片信息

每张图片返回：

```python
{
    "id": "",
    "file_name": "",
    "file_path": "",
    "file_size": 0,
    "created_time": "",
    "width": 0,
    "height": 0
}
```

---

## 3. 自动过滤非法文件

要求：

* 跳过损坏文件
* 跳过非图片文件
* 不允许程序崩溃

---

## 4. 大目录兼容

要求：

* 可扫描5000+图片
* 不一次性加载图片到内存
* 只读取元信息

---

## 5. CLI运行方式

必须支持：

```bash
python image_scanner.py --input "D:/Photos"
```

运行后：

* 输出扫描结果数量
* 输出JSON结果示例

---

# 项目结构要求

请创建：

```text
backend/
├── image_loader/
│   ├── image_scanner.py
│   ├── models.py
│   ├── utils.py
│   ├── README.md
```

---

# README要求

README 必须包含：

* 模块作用
* CLI运行方式
* 示例输入
* 示例输出
* 当前限制
* 后续扩展点

---

# 代码要求

必须：

* 添加类型注解
* 添加必要注释
* 模块解耦
* 不允许写死路径
* 不允许全局变量污染

---

# 当前阶段禁止

禁止：

* Electron UI开发
* React页面开发
* SQLite
* AI模型
* 缩略图
* 导出功能
* 性能优化
* 多线程

只完成：

# 图片扫描模块。
把下面这段完整发给 Claude。

---

# Task 2：实现缩略图缓存系统（禁止实现其他功能）

请严格按照以下要求开发。

---

# 目标

实现：

# 本地缩略图缓存模块

当前阶段：
只允许实现：

* 缩略图生成
* 缓存管理
* CLI测试

禁止实现：

* AI功能
* UI
* 数据库
* Electron
* React
* 导出
* 多线程
* GPU优化

---

# 技术要求

后端：

* Python

图片处理：

* Pillow

要求：

* 模块化
* 可长期维护
* 可独立运行
* CLI可测试

---

# 功能要求

---

## 1. 生成缩略图

输入：

* 原图路径

输出：

* 200px 最大边缩略图

要求：

* 保持宽高比
* 不裁切
* 不拉伸

输出格式：

* JPEG

---

## 2. 缓存目录结构

请创建：

```text id="ok9b0v"
cache/
└── thumbnails/
```

缩略图命名规则：

```text id="szy4n6"
{image_id}.jpg
```

image_id：
使用 image_scanner.py 中已有的稳定 ID。

---

## 3. 重复生成检测

要求：

如果缓存已存在：

* 不重复生成
* 直接返回缓存路径

---

## 4. 错误容错

要求：

* 损坏图片不能导致程序崩溃
* 自动跳过失败图片
* 输出错误日志

---

## 5. 支持批量处理

要求：

实现：

```python id="0pq2dy"
generate_thumbnails(photo_list)
```

支持：

* 批量生成缩略图

但当前阶段：
禁止多线程。

---

## 6. 返回结果格式

每张图片返回：

```python id="6x9v2m"
{
    "image_id": "",
    "source_path": "",
    "thumbnail_path": "",
    "success": true
}
```

---

# CLI要求

必须支持：

```bash id="y0h2m7"
python thumbnail_generator.py --input "D:/Photos"
```

运行后：

* 自动扫描图片
* 自动生成缩略图
* 输出生成数量
* 输出缓存目录位置

---

# 项目结构要求

请创建：

```text id="9i1d4m"
backend/
├── thumbnail_cache/
│   ├── thumbnail_generator.py
│   ├── cache_manager.py
│   ├── models.py
│   ├── utils.py
│   ├── README.md
```

---

# 与 image_loader 的关系

允许：

* import image_loader

禁止：

* 修改 image_loader 现有代码结构

---

# README要求

README必须包含：

* 模块作用
* CLI运行方式
* 示例输入
* 示例输出
* 缓存目录说明
* 当前限制
* 后续扩展点

---

# 代码要求

必须：

* 完整类型注解
* 必要注释
* 无全局状态污染
* 无硬编码路径
* 模块解耦
* 易于后续增加多线程

---

# 当前阶段禁止

禁止：

* Electron
* React
* SQLite
* AI分析
* 图片评分
* GPU
* ONNX
* 多线程

只完成：

# 缩略图缓存模块。
把下面这段完整发给 Claude。

---

# Task 3：实现 SQLite 图片索引系统（禁止实现其他功能）

请严格按照以下要求开发。

---

# 目标

实现：

# 本地 SQLite 图片索引系统

当前阶段：
只允许实现：

* 数据库初始化
* 图片信息写入
* 图片状态更新
* 基础查询

禁止实现：

* AI功能
* UI
* Electron
* React
* 导出
* 多线程
* ORM框架

---

# 技术要求

后端：

* Python

数据库：

* SQLite3（标准库）

要求：

* 轻量
* 模块化
* 可长期维护
* 不使用 ORM

---

# 功能要求

---

## 1. 自动初始化数据库

首次运行时：
自动创建：

```text id="9tx9vh"
database/
└── photoflow.db
```

---

## 2. 创建 photos 表

字段：

```sql id="9y9gmc"
CREATE TABLE photos (
    image_id TEXT PRIMARY KEY,
    file_name TEXT,
    file_path TEXT,
    thumbnail_path TEXT,
    file_size INTEGER,
    width INTEGER,
    height INTEGER,
    created_time TEXT,

    blur_score REAL DEFAULT NULL,
    eye_score REAL DEFAULT NULL,
    duplicate_group TEXT DEFAULT NULL,

    is_blur INTEGER DEFAULT 0,
    is_closed_eye INTEGER DEFAULT 0,
    is_duplicate INTEGER DEFAULT 0,

    star_rating INTEGER DEFAULT NULL,

    created_at TEXT,
    updated_at TEXT
);
```

---

## 3. 插入图片数据

实现：

```python id="11vwnp"
insert_photo(photo_info)
```

要求：

* 支持单条插入
* 支持批量插入
* image_id 冲突时自动跳过
* 不允许程序崩溃

---

## 4. 查询图片数据

实现：

```python id="ljlwm5"
get_all_photos()
get_photo_by_id(image_id)
```

---

## 5. 更新图片状态

实现：

```python id="sdlvje"
update_blur_status()
update_eye_status()
update_duplicate_status()
update_star_rating()
```

---

## 6. 数据库连接管理

要求：

* 自动关闭连接
* 不允许连接泄漏
* 使用 context manager

---

# CLI要求

必须支持：

```bash id="b5v3kq"
python db_manager.py --init
```

以及：

```bash id="b4x9tv"
python db_manager.py --import "D:/Photos"
```

要求：

* 自动调用 image_loader
* 自动写入数据库
* 输出导入数量

---

# 项目结构要求

请创建：

```text id="cl7m24"
database/
├── db_manager.py
├── models.py
├── repository.py
├── connection.py
├── README.md
```

---

# 与现有模块关系

允许：

* import image_loader
* import thumbnail_cache

禁止：

* 修改已有模块结构

---

# README要求

README必须包含：

* 数据库作用
* 表结构说明
* CLI运行方式
* 示例输入
* 示例输出
* 当前限制
* 后续扩展点

---

# 代码要求

必须：

* 完整类型注解
* 模块解耦
* 无全局连接
* 无硬编码路径
* Repository 模式
* 不使用 ORM

---

# 当前阶段禁止

禁止：

* SQLAlchemy
* Peewee
* AI分析
* Electron
* React
* 导出
* 多线程
* Redis
* 云同步

只完成：

# SQLite 图片索引系统。
把下面这段完整发给 Claude。

---

# Task 4：实现 Electron + React 图片浏览 UI（禁止实现其他功能）

请严格按照以下要求开发。

---

# 目标

实现：

# 本地图片浏览 UI

当前阶段：
只允许实现：

* Electron窗口
* React界面
* 图片网格浏览
* SQLite 数据读取
* 缩略图展示

禁止实现：

* AI功能
* 图片分析
* 导出
* 修图
* 状态筛选
* 多窗口
* UI美化

---

# 技术要求

桌面端：

* Electron

前端：

* React
* TypeScript

要求：

* Windows优先
* 模块化
* 长期可维护
* 前后端解耦

---

# UI目标

实现：

# “可稳定浏览5000张图片”

这是当前唯一目标。

不要实现：

* 炫酷动画
* 复杂交互
* 自定义主题

---

# 功能要求

---

## 1. Electron 主窗口

要求：

窗口启动后：
自动加载 React 页面。

窗口要求：

* 最小宽度：1200
* 最小高度：800

---

## 2. React 图片网格

要求：

显示：

* 缩略图
* 文件名
* 星级占位（先写死）
* 图片尺寸

---

## 3. 数据来源

要求：

前端不得直接读取 SQLite。

必须：

Electron Main Process
↓
IPC
↓
Python Backend
↓
SQLite

---

# 必须实现：

## Python API 层

例如：

```python id="9lfd6d"
get_photos(limit=100)
```

返回：
数据库中的图片数据。

---

# Electron IPC层

例如：

```typescript id="j48t9v"
window.api.getPhotos()
```

---

# React 页面层

调用：

* IPC
* 获取图片列表
* 渲染UI

---

## 4. 虚拟列表（非常重要）

必须使用：

* react-window

或者：

* react-virtualized

要求：

* 5000张图片流畅滚动
* 不允许一次性渲染全部DOM

---

## 5. 图片卡片

每张图片显示：

* 缩略图
* 文件名
* 宽高
* 占位评分（固定值即可）

---

## 6. 加载状态

要求：

实现：

* loading 状态
* 空目录状态
* 错误状态

---

# 项目结构要求

请创建：

```text id="xx2l8n"
frontend/
├── electron/
│   ├── main.ts
│   ├── preload.ts
│
├── src/
│   ├── api/
│   ├── components/
│   ├── pages/
│   ├── hooks/
│   ├── types/
│   ├── App.tsx
│
backend/
├── api/
│   ├── photo_service.py
```

---

# API要求

Python API层：

```python id="f7q7ha"
get_photos(limit: int = 100)
```

返回：

```python id="d7rj86"
[
    {
        "image_id": "",
        "file_name": "",
        "thumbnail_path": "",
        "width": 0,
        "height": 0
    }
]
```

---

# Electron要求

必须：

* contextIsolation = true
* preload 暴露安全 API
* 禁止 nodeIntegration

---

# React要求

必须：

* TypeScript
* Functional Component
* Hooks
* 不允许 class component

---

# README要求

README必须包含：

* 启动方式
* Electron架构说明
* IPC流程图
* 当前限制
* 后续扩展点

---

# 当前阶段禁止

禁止：

* AI分析
* 图片评分逻辑
* 图片筛选
* 图片删除
* 导出
* Redux
* Zustand
* Tailwind
* UI框架
* 多窗口
* GPU优化

只完成：

# 可稳定浏览图片的本地桌面UI。
把下面这段完整发给 Claude。

---

# Task 5：实现“导入照片目录”完整工作流（禁止实现其他功能）

请严格按照以下要求开发。

---

# 目标

实现：

# 用户选择照片目录

→ 自动扫描
→ 自动生成缩略图
→ 自动写入 SQLite
→ React UI 自动刷新显示

当前阶段：

目标是：

# 完成真正可用的“导入照片”流程。

禁止实现：

* AI分析
* 修图
* 导出
* 图片删除
* 图片移动
* 图片评分算法

---

# 功能要求

---

## 1. Electron 文件夹选择

要求：

用户点击：

# “导入照片目录”

然后：

* 打开系统目录选择器
* 用户选择照片文件夹

---

# Electron Main Process

必须：

使用：

```typescript id="mqmngj"
dialog.showOpenDialog()
```

要求：

* 仅允许目录选择
* 返回绝对路径

---

## 2. IPC 导入流程

实现：

```typescript id="m2ahbq"
window.electronAPI.importPhotos()
```

返回：

```typescript id="jov5wt"
{
    success: true,
    imported: 1200
}
```

---

## 3. Python 导入服务

请创建：

```text id="zq2utj"
backend/importer/
├── import_service.py
├── workflow.py
├── README.md
```

---

# 导入完整流程

workflow.py：

必须按以下顺序执行：

---

## Step1

扫描图片目录

调用：

* image_loader

---

## Step2

生成缩略图

调用：

* thumbnail_cache

---

## Step3

写入 SQLite

调用：

* database repository

---

## Step4

返回统计结果

例如：

```python id="mj9yhf"
{
    "total": 1200,
    "imported": 1180,
    "skipped": 20,
    "errors": 0
}
```

---

# 4. UI 导入按钮

React 页面：

新增：

# “导入照片目录”按钮

位置：

* 顶部工具栏即可

无需美化。

---

# 5. 导入进度状态

要求：

React 必须显示：

* importing...
* imported count
* error state

---

# 6. 导入完成自动刷新

要求：

导入完成后：

自动重新调用：

```typescript id="2dzt2k"
getPhotos()
```

刷新图片网格。

---

# 7. 重复导入保护

要求：

重复导入同一目录：

* 不允许重复插入数据库
* 不允许重复生成缩略图

必须依赖：

* image_id
* INSERT OR IGNORE

---

# 8. 错误容错

要求：

单张图片失败：

* 不影响整体导入

必须输出：

* logs/import.log

---

# UI要求

当前阶段：

不要：

* 动画
* Toast
* Modal
* UI框架

只要求：

* 稳定
* 清晰
* 可用

---

# README要求

README必须包含：

* 导入流程图
* 模块调用关系
* 错误处理机制
* 当前限制
* 后续扩展点

---

# 当前阶段禁止

禁止：

* AI分析
* 导出
* 图片删除
* 标签系统
* 多线程
* 队列系统
* Redis
* WebSocket
* GPU

只完成：

# 真正可用的照片导入工作流。
把下面这段完整发给 Claude。

---

# Task 6：实现图片详情预览系统（禁止实现其他功能）

请严格按照以下要求开发。

---

# 目标

实现：

# 图片选中

→ 图片详情面板
→ 大图预览

当前阶段：

目标是：

# 建立“当前选中图片”系统。

这是后续：

* AI评分
* 模糊检测
* 闭眼检测
* 星标
* 标签
* 筛选

的核心基础设施。

---

# 当前阶段禁止

禁止实现：

* AI分析
* 修图
* 导出
* 图片删除
* 标签
* 收藏系统
* 多窗口
* 图片编辑

只完成：

# 浏览 → 选中 → 预览。

---

# 功能要求

---

## 1. 图片选中状态

要求：

用户点击缩略图后：

* 当前图片进入 selected 状态
* UI高亮当前图片

---

# React要求

必须：

* 使用 hooks
* 不允许 Redux
* 不允许 Zustand

当前阶段：
使用：

* useState
* useContext

即可。

---

## 2. 图片详情面板

页面右侧新增：

# Detail Panel

显示：

* 缩略图
* 文件名
* 图片尺寸
* 文件大小
* 创建时间
* image_id

---

## 3. 大图预览

要求：

点击图片后：

右侧显示：

# 原图预览（不是缩略图）

---

# 后端要求

新增：

```python
GET /api/photo/{image_id}
```

返回：

```python
{
    "image_id": "",
    "file_name": "",
    "file_path": "",
    "width": 0,
    "height": 0,
    "file_size": 0,
    "created_time": "",
    "thumbnail_path": ""
}
```

---

# 原图访问

新增：

```python
GET /api/fullsize/{image_id}
```

要求：

* 后端读取原图
* 安全返回图片流
* 不允许前端直接访问磁盘路径

---

# Electron要求

仍然必须：

* contextIsolation = true
* preload 暴露 API
* 禁止 nodeIntegration

---

# IPC要求

新增：

```typescript
window.electronAPI.getPhotoDetail(imageId)
```

---

## 4. Detail Panel 布局

要求：

整体布局：

```text
| 图片网格 | 详情面板 |
```

详情面板固定宽度：

```text
380px
```

---

# Detail Panel 内容结构

```text
-------------------
原图预览
-------------------
文件名
尺寸
文件大小
创建时间
image_id
-------------------
```

---

## 5. 原图加载优化

要求：

* 不允许一次性加载所有原图
* 只有选中时才加载
* 切换图片时自动释放旧资源

---

## 6. Loading 状态

要求：

详情面板必须支持：

* loading
* empty state
* error state

---

## 7. 图片选中高亮

要求：

当前选中图片：

* 边框高亮
* 不需要动画
* 不需要复杂UI

---

# 项目结构要求

请新增：

```text
frontend/src/
├── context/
│   ├── PhotoSelectionContext.tsx

├── components/
│   ├── DetailPanel.tsx
│   ├── FullsizePreview.tsx
```

---

# 后端结构要求

新增：

```text
backend/api/
├── detail_service.py
```

---

# README要求

README必须包含：

* Detail Panel 架构
* 图片加载流程
* IPC流程
* 当前限制
* 后续扩展点

---

# 当前阶段禁止

禁止：

* AI分析
* 图片编辑
* 多选
* 键盘快捷键
* 标签
* 收藏
* 导出
* 修图
* GPU
* WebGL

只完成：

# 图片详情预览系统。
把下面这段完整发给 Claude。

---

# Task 7：实现键盘快速选片系统（禁止实现其他功能）

请严格按照以下要求开发。

---

# 目标

实现：

# 键盘驱动的摄影师选片工作流

这是：

# 第一个真正开始“像专业摄影软件”的阶段。

当前阶段：

目标是：

# 不用鼠标，

# 仅靠键盘即可高速浏览照片。

---

# 当前阶段禁止

禁止实现：

* AI分析
* 自动评分
* 删除文件
* 导出
* 修图
* 多选
* 标签系统
* 收藏系统
* 快捷键自定义

只完成：

# 键盘浏览图片。

---

# 功能要求

---

## 1. 左右方向键切图

要求：

```text
← 上一张
→ 下一张
```

行为：

* 自动切换当前 selected photo
* Detail Panel 自动更新
* 大图自动更新

---

## 2. 空格键：1星/取消星标

要求：

```text
Space
```

行为：

* 当前图片：
  0星 ↔ 1星 切换

---

# 数据库要求

更新：

```sql
star_rating
```

值：

```text
0 或 1
```

---

# UI要求

图片卡片：

显示：

```text
★
```

仅：

* 1星显示
* 0星不显示

Detail Panel：
也显示当前星标状态。

---

## 3. Enter 键

行为：

```text
Enter
```

切换：

* Fit 模式
* 100% 模式

---

# FullsizePreview要求

新增：

```text
fit
zoom100
```

两种模式。

---

# 当前阶段：

不要实现：

* 任意缩放
* 鼠标缩放
* 平移
* 手势

只实现：

# Fit / 100%

---

## 4. Home / End

行为：

```text
Home → 第一张
End → 最后一张
```

---

## 5. 自动滚动到当前图片

要求：

当前 selected 图片：

必须自动滚动到可视区域。

即：

键盘切图时：

左侧网格：
自动定位当前图片。

---

# react-window要求

必须兼容：

* virtualized list

不能因为快捷键：
导致性能退化。

---

## 6. 快捷键作用域

要求：

只有：

* 主页面 focus 时生效

禁止：

* 输入框误触
* Electron 全局快捷键

---

## 7. Selection Hook

请新增：

```text
frontend/src/hooks/
├── useKeyboardNavigation.ts
```

---

# 状态要求

必须支持：

* 当前索引
* 当前图片
* 当前星标状态

---

# API要求

新增：

```python
PATCH /api/photo/{image_id}/star
```

请求：

```json
{
    "star_rating": 1
}
```

---

# Electron IPC要求

新增：

```typescript
window.electronAPI.updateStarRating()
```

---

# UI要求

当前阶段：

不要：

* 动画
* Toast
* 音效

只要求：

* 快
* 稳
* 专业

---

# README要求

README必须包含：

* 快捷键列表
* 键盘导航流程
* react-window 自动定位实现
* 当前限制
* 后续扩展点

---

# 项目结构要求

请新增：

```text
frontend/src/hooks/
├── useKeyboardNavigation.ts
```

---

# 当前阶段禁止

禁止：

* 删除文件
* AI评分
* AI筛选
* 标签
* 多选
* Shift选择
* Ctrl选择
* 鼠标框选
* 导出
* GPU
* WebGL

只完成：

# 摄影师键盘高速选片系统。
把下面这段完整发给 Claude。

---

# Task 8：实现“仅查看已选照片”工作流（禁止实现其他功能）

请严格按照以下要求开发。

---

# 目标

实现：

# 摄影师真正开始“选片”

当前阶段：

用户已经可以：

* 浏览
* 键盘切图
* 打星

现在：

需要进入：

# “筛片工作流”。

---

# 当前阶段禁止

禁止实现：

* AI分析
* 删除文件
* 导出
* 标签
* 多选
* 修图
* 项目系统
* 高级筛选

只完成：

# 已选 / 全部

切换浏览。

---

# 功能要求

---

## 1. 顶部筛选栏

新增：

```text
[全部照片] [已选照片]
```

默认：

```text
全部照片
```

---

# UI要求

当前阶段：

不要：

* Tabs组件库
* 动画
* UI框架

只要：

* 简单按钮
* 清晰状态

---

## 2. 已选照片定义

规则：

```text
star_rating == 1
```

即：

* Space 打星
  → 进入已选照片

取消星标：
→ 自动从已选照片消失

---

## 3. SQLite查询支持

新增：

```python
get_starred_photos()
```

---

# API要求

新增：

```python
GET /api/photos/starred
```

返回：

```json
[
  {
    "image_id": "",
    "file_name": "",
    "thumbnail_path": ""
  }
]
```

---

# Electron IPC要求

新增：

```typescript
window.electronAPI.getStarredPhotos()
```

---

## 4. React筛选状态

新增：

```typescript
type PhotoFilterMode =
  | "all"
  | "starred"
```

---

# BrowserPage要求

必须支持：

```text
全部照片
↔
已选照片
```

实时切换。

---

## 5. 已选照片数量显示

顶部显示：

```text
已选：128
```

要求：

实时更新。

---

## 6. 当前图片失效处理

场景：

用户当前正在：

```text
已选照片
```

然后：

Space取消星标。

要求：

* 当前图片自动消失
* 自动切换到下一张
* 不允许空引用崩溃

---

## 7. react-window兼容

要求：

筛选后：

* 网格正常刷新
* 自动定位当前图片
* 不允许滚动错乱

---

## 8. 空状态

要求：

如果：

```text
已选照片 = 0
```

显示：

```text
暂无已选照片
按 Space 可标记照片
```

---

# 状态管理要求

当前阶段：

继续：

* useState
* useContext

禁止：

* Redux
* Zustand
* MobX

---

# README要求

README必须包含：

* 筛选工作流
* 已选照片逻辑
* 当前图片失效处理机制
* react-window 刷新机制
* 当前限制
* 后续扩展点

---

# 项目结构要求

允许：

新增：

```text
frontend/src/types/
frontend/src/hooks/
frontend/src/components/
```

但：

禁止大规模重构。

---

# 当前阶段禁止

禁止：

* AI筛选
* 多标签
* Reject状态
* 颜色标记
* 多选
* Shift选择
* Ctrl选择
* 导出
* 删除文件
* 云同步

只完成：

# 摄影师“选片”核心工作流。
把下面这段完整发给 Claude。

---

# Task 9：实现 AI 模糊检测（Blur Detection）基础版（禁止实现其他功能）

请严格按照以下要求开发。

---

# 目标

实现：

# 第一版 AI 选片能力：

# 模糊照片检测。

这是：

# 软件第一次真正进入“AI选片”。

当前阶段：

只做：

* 模糊检测
* 模糊评分
* 模糊筛选

禁止：

* 闭眼检测
* 表情检测
* 人脸评分
* 美学评分
* AI排序

---

# 当前阶段禁止

禁止：

* 深度学习
* ONNX
* GPU
* YOLO
* TensorRT
* 云端模型

只允许：

# OpenCV + Laplacian Variance

实现传统稳定方案。

---

# 技术要求

后端：

* Python
* OpenCV

允许新增依赖：

```text id="1d7tv7"
opencv-python
numpy
```

---

# 模糊检测算法

使用：

# Laplacian Variance

例如：

```python id="rn40z9"
cv2.Laplacian(gray, cv2.CV_64F).var()
```

---

# 判定规则

要求：

```text id="1i5b72"
variance < threshold
→ 模糊照片
```

---

# 当前阶段：

threshold：

```text id="blb2o6"
100
```

先写死。

后续再做可调参数。

---

# 功能要求

---

## 1. 新增 blur_detector 模块

请创建：

```text id="vqgm9v"
backend/ai/
├── blur_detector/
│   ├── detector.py
│   ├── models.py
│   ├── service.py
│   ├── README.md
```

---

## 2. Blur Detection API

新增：

```python id="6e7hwy"
POST /api/ai/blur-detect
```

请求：

```json id="e6gm4l"
{
    "photo_ids": []
}
```

---

返回：

```json id="c1m9gf"
{
    "processed": 100,
    "blurred": 12
}
```

---

# 检测流程

对每张图片：

---

## Step1

读取原图。

禁止：

* 使用缩略图检测。

---

## Step2

转灰度。

---

## Step3

计算：

```python id="bik1zk"
laplacian variance
```

---

## Step4

写入数据库：

```text id="vw7l3k"
blur_score
is_blur
```

---

# 数据库规则

例如：

```text id="zjv9fy"
blur_score = 53.2
is_blur = 1
```

---

## 3. Repository支持

新增：

```python id="sqt7dr"
update_blur_analysis()
```

---

## 4. Electron IPC

新增：

```typescript id="rt3jwd"
window.electronAPI.runBlurDetection()
```

---

## 5. React顶部按钮

新增：

```text id="7jlwm0"
[检测模糊照片]
```

点击后：

* 开始检测
* 显示 processing 状态

---

## 6. UI显示

图片卡片：

新增：

```text id="l7dg0f"
BLUR
```

仅：

```text id="ndnqkt"
is_blur == 1
```

时显示。

---

# 当前阶段：

不要：

* 红色警告
* 动画
* 图标

只显示：

```text id="53mfwy"
BLUR
```

---

## 7. Blur筛选模式

新增：

```text id="w3z0h6"
[模糊照片]
```

---

# 筛选规则

```text id="yxpr0k"
is_blur == 1
```

---

# FilterMode更新

新增：

```typescript id="gz00hq"
"blur"
```

---

## 8. Detail Panel显示

新增：

```text id="ewr52d"
Blur Score: 53.2
Status: BLUR
```

---

## 9. 批量处理要求

要求：

* 不允许一次性加载全部原图
* 顺序处理
* 单张失败不影响整体

---

## 10. 日志

新增：

```text id="2mjgdm"
logs/blur_detection.log
```

记录：

* 开始时间
* 图片数量
* 失败数量
* 平均耗时

---

# README要求

README必须包含：

* Laplacian Variance 原理
* Threshold 规则
* 数据流
* API说明
* 当前限制
* 后续扩展点

---

# 当前阶段禁止

禁止：

* GPU
* 多线程
* ONNX
* 深度学习
* AI排序
* 自动删除
* 自动筛选
* 美学评分
* 闭眼检测

只完成：

# 第一版 AI 模糊检测系统。
把下面这段完整发给 Claude。

---

# Task 10：实现“Reject（废片）”工作流（禁止实现其他功能）

请严格按照以下要求开发。

---

# 目标

实现：

# 摄影师真正的“筛废片”流程。

现在软件已经具备：

* 浏览
* 键盘选片
* 星标
* 模糊检测

下一步：

需要实现：

# Reject（废片标记）

这是专业摄影软件核心工作流。

---

# 当前阶段禁止

禁止：

* 真正删除文件
* 回收站
* 自动删除
* AI自动Reject
* 多标签
* 颜色标记
* 导出

只完成：

# Reject标记工作流。

---

# 功能要求

---

## 1. 数据库新增字段

新增：

```sql id="91r57v"
is_rejected INTEGER DEFAULT 0
```

---

# Migration要求

必须：

自动兼容旧数据库。

要求：

* 已存在数据库自动升级
* 不允许用户删库重建

---

## 2. Reject快捷键

新增：

```text id="93x0lz"
X
```

行为：

```text id="74p50r"
0 ↔ 1
```

即：

* 未Reject
  → Reject

* 已Reject
  → 取消Reject

---

## 3. 图片卡片显示

如果：

```text id="zefztt"
is_rejected == 1
```

显示：

```text id="dwv7cu"
REJECT
```

---

# UI要求

当前阶段：

不要：

* 删除动画
* 红色遮罩
* 复杂UI

只显示：

```text id="rqqolx"
REJECT
```

---

## 4. Reject筛选模式

顶部新增：

```text id="7fsgzv"
[废片]
```

---

# FilterMode新增

```typescript id="7m2xjl"
"rejected"
```

---

# API要求

新增：

```python id="s7hzk6"
GET /api/photos/rejected
```

---

## 5. Reject数量显示

顶部显示：

```text id="l6b58c"
废片：128
```

实时更新。

---

## 6. Detail Panel显示

新增：

```text id="m0c56m"
Status: REJECT
```

---

## 7. Keyboard Workflow

要求：

摄影师现在可以：

```text id="d0rm3f"
← →
浏览

Space
选片

X
废片
```

---

# 重要规则

一张照片：

允许：

```text id="h59eeh"
已选 + Reject
```

同时存在。

当前阶段：

不要互斥逻辑。

后面再决定。

---

## 8. 当前图片失效处理

场景：

用户当前：

```text id="mrtifk"
废片模式
```

然后：

按：

```text id="m1k59l"
X
```

取消Reject。

要求：

* 当前图片自动消失
* 自动切换下一张
* 不允许空引用崩溃

---

## 9. Repository支持

新增：

```python id="54twws"
get_rejected_photos()
update_reject_status()
```

---

## 10. Electron IPC

新增：

```typescript id="ks3vbb"
window.electronAPI.updateRejectStatus()
window.electronAPI.getRejectedPhotos()
```

---

## 11. 空状态

要求：

如果：

```text id="tv4jlwm"
废片 = 0
```

显示：

```text id="ry0z2o"
暂无废片
按 X 可标记废片
```

---

# react-window要求

必须：

* 兼容虚拟列表
* 自动定位当前图片
* 不允许滚动错乱

---

# README要求

README必须包含：

* Reject工作流
* 键盘流程
* Migration方案
* 当前图片失效处理
* 当前限制
* 后续扩展点

---

# 当前阶段禁止

禁止：

* 真删文件
* 回收站
* AI自动删图
* 多选
* Shift选择
* Ctrl选择
* 导出
* 云同步
* AI推荐

只完成：

# 专业摄影 Reject 工作流。
Task 11：实现 Duplicate Detection（重复照片检测）基础版（禁止实现其他功能）

请严格按照以下要求开发。

目标

实现：

第一版重复照片检测系统。

当前阶段：

只做：

相似图片检测
连拍去重
重复筛选

禁止：

AI美学排序
最佳照片推荐
人脸聚类
深度学习Embedding
当前阶段禁止

禁止：

ONNX
GPU
深度学习
TensorRT
FAISS
CLIP
云端模型

只允许：

imagehash + Pillow

实现稳定基础版。

技术要求

允许新增依赖：

imagehash

继续使用：

Pillow
Duplicate算法

使用：

perceptual hash（phash）

例如：

imagehash.phash(image)
判定规则

当前阶段：

Hamming Distance <= 5
→ 判定重复

先写死。

后续再做可调参数。

功能要求
1. 新增 duplicate_detector 模块

创建：

backend/ai/
├── duplicate_detector/
│   ├── detector.py
│   ├── models.py
│   ├── service.py
│   ├── README.md
2. 数据库新增字段

新增：

duplicate_group_id TEXT
is_duplicate INTEGER DEFAULT 0
Migration要求

必须：

兼容旧数据库。

禁止删库重建。

3. Duplicate Detection API

新增：

POST /api/ai/duplicate-detect

请求：

{
    "photo_ids": []
}

返回：

{
    "processed": 1000,
    "duplicate_groups": 128,
    "duplicates": 642
}
检测流程
Step1

读取原图。

不要使用缩略图。

Step2

生成：

phash
Step3

两两比较：

Hamming Distance
Step4

判定：

distance <= 5
Step5

写入数据库：

is_duplicate
duplicate_group_id
duplicate_group_id规则

例如：

dup_0001
dup_0002

同组照片：

共享 group_id。

4. Repository支持

新增：

update_duplicate_analysis()
get_duplicate_photos()
get_duplicate_groups()
5. Electron IPC

新增：

window.electronAPI.runDuplicateDetection()
window.electronAPI.getDuplicatePhotos()
6. React顶部按钮

新增：

[检测重复照片]
7. Duplicate筛选模式

新增：

[重复照片]
FilterMode新增
"duplicate"
8. UI显示

图片卡片：

新增：

DUP

仅：

is_duplicate == 1

时显示。

当前阶段：

不要：

彩色边框
分组UI
连线
动画

只显示：

DUP
9. Detail Panel显示

新增：

Duplicate Group: dup_0001
10. 当前阶段重要规则

当前阶段：

不要自动决定保留哪张。

只负责：

检测
标记

不做：

best photo selection
11. 批量处理要求

要求：

顺序处理
不一次性加载原图像素
单张失败不影响整体
日志

新增：

logs/duplicate_detection.log

记录：

图片数量
duplicate group 数量
耗时
失败数量
README要求

README必须包含：

perceptual hash 原理
Hamming Distance 规则
duplicate_group_id 机制
API说明
当前限制
后续扩展点
当前阶段禁止

禁止：

自动删图
自动保留最佳图
人脸识别
深度学习
GPU
CLIP
Embedding
多线程
FAISS

只完成：

第一版重复照片检测系统。
Task 12：实现 Compare Mode（双图对比选片模式）（禁止实现其他功能）

请严格按照以下要求开发。

目标

实现：

专业摄影 Compare Mode。

这是：

摄影师筛选连拍照片时：

最高频功能之一。

当前阶段禁止

禁止：

多图 compare
AI最佳图推荐
自动选优
人脸评分
自动同步缩放
鼠标拖拽
GPU

只实现：

双图对比模式。
功能目标

摄影师现在可以：

选中一张照片
↓
按 C
↓
进入 Compare Mode
↓
左右对比两张照片
↓
快速决定：
保留哪张
Reject哪张
Compare Mode规则

当前阶段：

只允许：

2张图对比。
数据来源规则

Compare Mode：

仅在：

duplicate_group_id != null

时可进入。

进入逻辑
1. Keyboard Shortcut

新增：

C
行为

当前选中照片：

如果：

duplicate_group_id 存在

则：

进入 Compare Mode。

否则：

不做任何事。

2. Compare Pair规则

当前阶段：

自动选择：

同 duplicate_group 的下一张

作为对比对象。

例如：

dup_0001:
A
B
C

当前：

A

则 Compare：

A vs B
当前阶段：

不要：

手动选择 compare 对象
compare list UI

后续再做。

3. 新增 CompareMode Context

新增：

frontend/src/context/CompareModeContext.tsx
状态要求

必须包含：

isCompareMode
leftPhoto
rightPhoto
4. Compare Layout

进入 Compare Mode 后：

主区域：

变成：

| LEFT PHOTO | RIGHT PHOTO |
当前阶段：

不要：

fancy UI
动画
split drag
resize

只要求：

稳定
清晰
快
5. Compare FullsizePreview

新增：

ComparePreview.tsx
要求

左右：

分别显示：

原图
文件名
星标
Reject状态
6. Compare Keyboard Workflow

新增快捷键：

Left Arrow / Right Arrow

当前阶段：

作用：

切换 duplicate group 内照片

例如：

A vs B
↓ Right
B vs C
7. Space

当前阶段：

给 LEFT PHOTO 打星
8. X

当前阶段：

给 LEFT PHOTO Reject
9. Tab

新增：

Tab

作用：

切换：

LEFT ACTIVE
RIGHT ACTIVE
当前阶段：

Space / X：

始终作用于：

Active Photo
10. ESC

新增：

ESC

退出：

Compare Mode。

恢复：

普通浏览模式。

11. Duplicate Group Navigation

要求：

Compare Mode：

只能：

在当前 duplicate_group 内切换。

禁止：

跨 group。

12. UI状态显示

顶部显示：

COMPARE MODE
dup_0001
2 / 5
13. Detail Panel

当前阶段：

进入 Compare Mode 后：

隐藏 Detail Panel。

后续再做 Compare Detail。

14. react-window要求

进入 Compare Mode：

暂停 grid keyboard navigation
不允许 background scroll
退出时恢复
15. Current State Safety

必须处理：

场景：

当前 active photo 被 reject
当前 active photo 被取消 star
compare pair 消失

不能崩溃。

16. README要求

README必须包含：

Compare workflow
duplicate group navigation
keyboard workflow
compare state machine
current limitations
future extensions
当前阶段禁止

禁止：

AI选优
自动排序
鼠标同步缩放
多图 compare
Filmstrip
GPU
WebGL
动画
AI评分

只完成：

第一版专业摄影 Compare Mode。
