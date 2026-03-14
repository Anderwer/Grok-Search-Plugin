# Grok Search Plugin

为 MaiBot 提供基于高时效性模型的联网检索、图片理解增强搜索与事实归纳能力的插件。  
该插件主要面向 **Grok** 场景设计，同时兼容 **Gemini** 等支持 OpenAI 兼容接口的模型服务。

---

## 功能简介

Grok Search Plugin 目前提供三类能力：

### 1. 普通联网搜索 Tool：`grounded_search`
供 MaiBot / LLM 在需要时自动调用，适用于：

- 热点事件
- 近期新闻
- 版本更新
- 外部事实核查
- 网络梗、流行话题、争议问题

---

### 2. 图片增强搜索 Tool：`recent_image_search`
当用户的问题与图片有关时，插件会优先尝试：

1. 获取当前消息中的图片
2. 如果当前消息没有图片，则回溯当前用户最近发送的图片
3. 如果是表情包，则尝试从：
   - emoji 主表
   - EmojiDescriptionCache
   - `data/emoji/` 缓存文件  
   中恢复原始资源
4. 对图片做视觉分析
5. 再结合用户问题做搜索或归纳

适用于：

- 这是谁
- 这张图里的人物是谁
- 这是什么梗
- 这图出自哪里
- 图里写了什么

如果未找到可用视觉资源，会自动降级为普通联网搜索。

---

### 3. 手动命令：`/search`
用户可以手动触发搜索：

```text
/search 今日新闻
/search Gemini 最近有哪些更新
/search 这个图里的人物是谁
/search 这个梗出自哪
```

命令模式同样支持：

- 当前消息图片
- 最近图片回溯
- 表情包恢复
- 图片分析缓存

---

## 当前版本新增能力

相较于早期版本，新版插件新增了以下能力：

- ✅ 普通文本搜索与图片增强搜索分离
- ✅ 支持当前消息图片与最近图片回溯
- ✅ 支持普通图片 `picid -> data/images/<picid>.png`
- ✅ 支持表情包从 emoji 主表恢复原始文件
- ✅ 支持从 `EmojiDescriptionCache + data/emoji/` 恢复未注册表情包
- ✅ 支持图片视觉分析结果缓存，避免重复分析相同图片
- ✅ 支持普通搜索 prompt 与图片搜索 prompt 分离
- ✅ 兼容更多 OpenAI 兼容接口返回格式（对象 / dict / str）

---

## 适用场景

当用户提问具有以下特征时，插件尤其有用：

### 普通搜索场景
- 需要**最新信息**
- 需要**外部事实核查**
- 需要**确认近期版本 / 公告 / 更新**
- 需要**整理热点事件**
- 需要**搜索网络梗、流行话题、争议问题**

### 图片搜索场景
- 用户先发图，再问：
  - “这是谁”
  - “这张图里的人物是谁”
  - “这是什么梗”
  - “这图出自哪里”
- 用户发送表情包后询问图中角色或来源
- 需要对图片中的角色、作品、梗图、界面内容做进一步确认

---

## 项目结构

```text
grok_search_plugin/
├─ __init__.py
├─ _manifest.json
├─ plugin.py
├─ prompts.py
├─ models.py
├─ README.md
├─ LICENSE
├─ services/
│  ├─ __init__.py
│  ├─ search_service.py
│  ├─ vision_service.py
│  ├─ image_resolver.py
│  └─ analysis_cache.py
├─ components/
│  ├─ __init__.py
│  ├─ tools.py
│  └─ commands.py
└─ utils/
   ├─ __init__.py
   ├─ formatter.py
   └─ model_response.py
```

---

## 安装方式

1. 将插件放入 MaiBot 的 `plugins` 目录
2. 安装依赖：

```bash
pip install openai aiohttp
```

3. 启动 MaiBot
4. 配置搜索模型与视觉模型参数
5. 重载插件或重启 MaiBot

---

## 配置示例

```toml
# 插件基本信息
[plugin]

# 插件名称
name = "grok_search_plugin"

# 插件版本
version = "1.0.2"

# 配置文件版本
config_version = "1.0.2"

# 是否启用插件
enabled = true


# 模型配置
[model]

# 兼容 OpenAI Chat Completions 的接口地址
base_url = "https://api.x.ai/v1"

# 模型 API 密钥
api_key = ""

# 使用的模型名称
model = "grok-4"

# 生成温度
temperature = 0.2


# 搜索配置
[search]

# 搜索归纳方向
direction = "请优先关注近期热点、互联网讨论、模型更新、版本变化、公告、新闻和事实准确性。"

# 是否附带最近聊天上下文
enable_context = true

# 读取最近多少秒内的聊天记录
time_gap = 270

# 最多读取多少条聊天记录
max_limit = 10

# 单次请求超时时间（秒）
timeout = 25.0

# 最大并发搜索请求数
max_concurrency = 3

# 失败重试次数
retry_attempts = 3

# 最小重试等待时间（秒）
retry_wait_min = 1.5

# 最大重试等待时间（秒）
retry_wait_max = 8.0

# 输出模式：brief / structured / raw
output_mode = "brief"

# 命令回复最大长度
max_output_length = 1200


# 提示词配置
[prompt]

# 系统提示词
system_prompt = "你是专业的实时信息检索助手，擅长结合外部最新信息进行事实核查、热点整理与简明总结。"


# 图片识别与缓存配置
[vision]

# 是否启用图片视觉分析
enabled = true

# 视觉模型接口地址
base_url = "https://api.openai.com/v1"

# 视觉模型 API 密钥
api_key = ""

# 视觉模型名称
model = "grok-4"

# 视觉分析温度
temperature = 0.1

# 视觉分析超时时间（秒）
timeout = 20.0

# 视觉分析提示词
prompt = "请准确识别图片中的人物、角色、作品线索、文字信息和可能的梗来源，不要编造。"

# 当前消息无图时，是否回退查找最近图片
fallback_to_recent_image = true

# 是否优先查找当前用户最近发送的图片
prefer_same_user_recent_image = true

# 回溯最近图片的时间范围（秒）
recent_image_time_gap = 120

# 最多检查最近多少条消息
recent_image_scan_limit = 15

# 图片分析缓存文件路径
cache_file = "data/plugins/grok_search_plugin/image_analysis_cache.json"

# 图片分析缓存有效期（秒）
cache_ttl_seconds = 2592000
```

---

## 配置说明

### `[model]`
搜索模型配置，用于普通联网搜索和搜索总结：

- `base_url`: 搜索模型接口地址
- `api_key`: 搜索模型密钥
- `model`: 搜索模型名称
- `temperature`: 搜索生成温度

---

### `[search]`
搜索行为配置：

- `direction`: 搜索方向偏好
- `enable_context`: 是否带最近聊天上下文
- `time_gap`: 上下文时间窗口
- `max_limit`: 上下文最大消息数
- `timeout`: 搜索超时
- `max_concurrency`: 最大并发
- `retry_attempts`: 重试次数
- `retry_wait_min` / `retry_wait_max`: 重试退避参数
- `output_mode`: 输出格式
- `max_output_length`: 命令返回时的最大输出长度

---

### `[vision]`
图片分析与缓存配置：

- `enabled`: 是否启用视觉分析
- `base_url`: 视觉模型接口地址
- `api_key`: 视觉模型密钥
- `model`: 视觉模型名称
- `temperature`: 视觉分析温度
- `timeout`: 视觉分析超时
- `prompt`: 视觉分析提示词
- `fallback_to_recent_image`: 当前消息无图时是否回溯最近图片
- `prefer_same_user_recent_image`: 是否优先使用当前用户最近图片
- `recent_image_time_gap`: 回溯时间窗口
- `recent_image_scan_limit`: 最大回溯消息数
- `cache_file`: 图片分析缓存路径
- `cache_ttl_seconds`: 缓存有效期

---

## 使用方式

### 1. 普通聊天自动调用 Tool
例如：

```text
今天有什么热点新闻
Grok 最近更新了什么
这个梗出自哪
```

模型可能会自动调用：

- `grounded_search`

---

### 2. 图片相关普通问句
例如：

```text
[先发图]
这是谁
这张图里的人物是谁
这是什么梗
```

模型可能会自动调用：

- `recent_image_search`

插件会尝试：

- 当前消息取图
- 最近消息回溯
- 表情包恢复
- 视觉分析 + 搜索

---

### 3. 手动命令
例如：

```text
/search 今日新闻
/search 这张图里的人物是谁
/search 这是什么梗
```

命令模式会优先尝试图片增强搜索，失败后自动降级到普通联网搜索。

---

## 图片与表情包支持说明

### 普通图片
插件支持通过以下方式恢复原图：

- `[picid:xxx]`
- `data/images/<picid>.png`
- `Images` 表中的图片路径
- 某些消息段中的 `file / url / base64`

---

### 表情包
插件支持两类表情包恢复路径：

#### 1. 已注册表情包
从 `Emoji` 表中读取：

- `full_path`
- `description`
- `emotion`

#### 2. 未注册但已缓存表情包
从 `EmojiDescriptionCache` 读取：

- `emoji_hash`
- `description`
- `emotion_tags`

再尝试从以下位置恢复文件：

```text
data/emoji/<hash>.gif
data/emoji/<hash前8位>.gif
```

以及其他常见格式：

- png
- jpg
- jpeg
- webp

---

## 图片分析缓存

插件会对拿到的原始图片内容计算哈希值，并将视觉分析结果缓存到本地 JSON 文件中。

### 缓存好处
- 避免重复分析同一张图
- 降低视觉模型调用成本
- 提高响应速度

### 缓存范围
- 普通图片
- 可恢复原图的表情包

---

## 兼容性说明

该插件主要面向：

- Grok
- Gemini（OpenAI 兼容接口）
- 其他支持 OpenAI Chat Completions 兼容调用的搜索型 / 视觉型模型接口

---

## 开发说明

本插件遵循 MaiBot 插件开发文档要求，包含：

- 标准 `_manifest.json`
- 标准 `BasePlugin` 插件主类
- `Tool` 组件
- `Command` 组件
- 配置与元数据分离
- 多文件工程化结构

---

## 注意事项

- 普通聊天中的 Tool 调用由 LLM 自主决定，不保证每次都触发
- `/search` 命令可作为强制入口
- 如果系统自身已经提供足够的识图描述，模型可能直接回答而不一定调用图片搜索 Tool
- 部分平台下表情包与图片的底层表示不同，插件已尽量兼容，但仍受 Adapter 实现影响
- 建议将视觉模型和搜索模型分开配置，以获得更稳定表现
- 建议将 `temperature` 设为较低值，减少事实性错误

---

## 许可证

本项目使用 [MIT License](./LICENSE)。

---

## 致谢

感谢 MaiBot 项目及其插件系统提供的扩展能力。  
如果你觉得这个插件有帮助，欢迎 Star、反馈 Issue 或继续改进。
