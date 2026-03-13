# Grok Search Plugin

为 MaiBot 提供基于高时效性模型的联网检索与事实归纳能力的插件。  
该插件主要面向 **Grok** 场景设计，同时也兼容 **Gemini** 等支持 OpenAI 兼容接口的模型服务。

## 功能简介

Grok Search Plugin 提供两种能力：

- **Tool 组件：`grounded_search`**
  - 供 MaiBot / LLM 在需要时自动调用
  - 适用于时效性、事实性、争议性较强的问题
  - 例如热点事件、近期新闻、模型更新、版本变更、网络梗出处等

- **Command 组件：`/search`**
  - 用户手动触发联网搜索
  - 例如：
    - `/search 今天 xAI 发布了什么`
    - `/search Gemini 最近有哪些更新`
    - `/search 某个梗的出处`

---

## 适用场景

当用户提问具有以下特征时，插件尤其有用：

- 需要**最新信息**
- 需要**外部事实核查**
- 需要**确认近期版本/公告/更新**
- 需要**整理热点事件**
- 需要**搜索网络梗、流行话题、争议问题**

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
│  └─ search_service.py
├─ components/
│  ├─ __init__.py
│  ├─ tools.py
│  └─ commands.py
└─ utils/
   ├─ __init__.py
   └─ formatter.py
