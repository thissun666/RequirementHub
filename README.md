# 🧠 企业多节点AI智能协同系统

**RequirementHub** —— 让每个节点的声音，被 AI 智慧地听见。

> 一套面向企业的 AI 驱动需求收集与决策协同平台：员工和 AI 对话即可把模糊想法整理成结构化需求，自动流转给管理员处理，全程可跟踪、可统计、可导出报告。

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Beta-orange.svg)]()

---

## 📖 项目简介

在大量 **“一对多”沟通型岗位** —— 行政助理、部门秘书、IT 支持、HRBP、项目经理 —— 日常工作中反复出现同一类困境：

| 痛点 | 描述 |
|------|------|
| 📨 渠道分散 | 需求从微信、口头、邮件、走廊拦人四个渠道涌入，全部混在聊天记录流中 |
| 🗣️ 描述模糊 | 描述者自己也说不清楚要什么，沟通往返 3~5 轮才能拼出完整信息 |
| 📭 无跟踪 | 无优先级、无状态、无留痕，“上周让我办的那件事”靠人脑记忆 |
| 📊 无统计 | 领导要一份“本月处理了什么”的报告，得翻半天聊天记录手工汇总 |

**本系统把这条链路收敛为一个入口：**

> 员工对着 AI 说 → AI 结构化收集 → 自动摘要 + 定级 → 管理员集中处理 → 一键导出报告

---

## 🎯 核心理念

```text
员工（子节点）                      管理员（父节点）
      │
      │ 对话式描述需求
      ▼
   AI 追问收集（最多 N 轮）
      │
      │ 信息足够 → 自动生成摘要
      ▼
   需求入库（标题/描述/优先级） ──实时推送──▶ 需求列表（按优先级/状态筛选）
      │                                              │
      │ ←─────── 跟进对话（管理员回复）←─────────────┘
      ▼                                              ▼
 员工查看进度                                   标记解决 + 解决方案
                                                       │
                                                       ▼
                                                 解决报告（月报/年报）
三个关键设计
设计	说明
🧠 AI 结构化收集	多轮追问 → 摘要 → 优先级建议，员工零学习成本
🔒 隐私分层	员工可开启“助手模式”自由提问（含企业知识库问答），此类对话对管理员不可见；需求跟进对话管理员可见 —— 公私分明
📚 企业知识库	管理员上传制度文档，AI 回答员工咨询时自动引用，减少重复答疑
✨ 功能特性
员工端（子节点）
功能	说明
💬 AI 对话式需求提交	与 AI 对话，自动生成结构化需求
📝 需求跟进	随时补充消息，管理员实时同步
🤖 自由 AI 助手	可切换“助手模式”，自由提问（支持企业知识库问答）
🔑 个人专属模型	自带 API Key，支持 11+ 种模型提供商，仅本人生效
📋 需求列表	按时间/状态查看自己的所有需求
✏️ 需求重命名	自定义需求标题
管理员端（父节点）
功能	说明
📋 需求列表	按状态/优先级筛选查看所有子节点需求
💬 需求详情与回复	查看完整沟通记录，回复子节点
✅ 标记解决	提交解决方案，反馈给子节点确认
📊 解决报告	趋势图/状态分布/排行，月报年报自动生成
👥 账号管理	子节点账号增删改、职位管理
📚 企业知识库	上传 txt/md/docx 文档，向量化检索
⚙️ 模型设置	全局模型配置，支持多模型切换
🔔 实时通知	WebSocket 推送新需求/新消息
技术特性
特性	说明
🚀 异步高性能	FastAPI + WebSocket 实时通信
💾 零配置数据库	SQLite 文件数据库，开箱即用
🧩 多模型支持	智谱、硅基、Ollama、DeepSeek、OpenAI 等 11+ 种
🔄 模型热切换	Web 界面实时切换，无需重启
📦 一键打包	PyInstaller 打包，双击运行
🔒 数据本地化	所有数据存储在本地，自主可控
🧩 支持的服务商
服务商	说明	默认模型
智谱	国内领先大模型	glm-4-flash
硅基流动	开源模型 API 平台	Qwen/Qwen2.5-7B-Instruct
Ollama	本地运行开源模型	qwen2.5:3b
DeepSeek	深度求索	deepseek-chat
OpenAI	国际主流	gpt-3.5-turbo
Kimi	月之暗面	moonshot-v1-8k
通义千问	阿里云	qwen-turbo
火山引擎	字节跳动	—
文心一言	百度	—
讯飞星火	科大讯飞	—
LM Studio	本地模型	—
📦 安装与运行
方式一：Windows 打包版本（推荐非开发用户）
下载 RequirementHub.zip

解压到任意目录

双击 RequirementHub.exe

浏览器自动打开 http://127.0.0.1:8000

方式二：源码运行（开发环境）
环境要求：Python 3.9+

bash
# 1. 克隆项目
git clone https://github.com/thissun666/RequirementHub.git
cd RequirementHub

# 2. 创建虚拟环境
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate   # Mac/Linux

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置 .env（可选）
cp backend/.env.example backend/.env
# 编辑 .env，填入你的 API Key

# 5. 启动服务
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# 6. 浏览器访问
# http://127.0.0.1:8000
方式三：Docker 运行（待支持）
bash
# 后续提供 Docker 镜像
# docker run -p 8000:8000 requirementhub:latest
🔑 API Key 配置
全局配置（管理员）
在父节点界面 → 模型设置 中配置：

字段	说明
服务商	选择智谱/硅基/Ollama/DeepSeek 等
API Key	填入对应平台的 API Key
模型名称	填入具体的模型名称
Base URL	API 地址（通常自动填充）
个人专属模型（员工）
员工可在子节点界面 个人设置 中配置自己的 API Key，仅对自己生效，不影响其他用户。

免费模型推荐：

服务商	免费模型	说明
智谱	glm-4-flash	速度快，适合日常对话
硅基流动	Qwen/Qwen2.5-7B-Instruct	开源模型，质量高
Kimi	moonshot-v1-8k	上下文长
DeepSeek	deepseek-chat	性价比高
🗂️ 项目结构
text
RequirementHub/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI 入口
│   │   ├── config.py                   # 环境配置
│   │   ├── database.py                 # 数据库连接
│   │   ├── models.py                   # SQLAlchemy 模型
│   │   ├── schemas.py                  # Pydantic 模型
│   │   ├── auth.py                     # JWT 认证
│   │   ├── routers/                    # API 路由
│   │   │   ├── auth_router.py          # 登录注册
│   │   │   ├── user_router.py          # 用户管理
│   │   │   ├── requirement_router.py   # 需求管理
│   │   │   ├── conversation_router.py  # 对话管理
│   │   │   ├── settings_router.py      # 模型设置
│   │   │   └── report_router.py        # 报告
│   │   ├── services/                   # 核心服务
│   │   │   ├── llm_service.py          # 模型调用封装
│   │   │   ├── ask_ai_service.py       # 询问 AI 逻辑
│   │   │   ├── summarize_ai_service.py # 整理 AI 逻辑
│   │   │   ├── priority_service.py     # 优先级评估
│   │   │   └── websocket_manager.py    # WebSocket 管理
│   │   └── static/                     # 前端静态文件
│   ├── data/
│   │   └── requirementhub.db           # SQLite 数据库
│   └── requirements.txt
├── frontend/
│   ├── index.html                      # 入口页
│   ├── login.html                      # 登录页
│   ├── parent.html                     # 父节点主界面
│   ├── child.html                      # 子节点主界面
│   ├── css/
│   │   ├── style.css
│   │   ├── parent.css
│   │   └── child.css
│   ├── js/
│   │   ├── api.js                      # API 封装
│   │   ├── auth.js                     # 认证
│   │   ├── parent.js                   # 父节点逻辑
│   │   ├── child.js                    # 子节点逻辑
│   │   ├── websocket.js                # WebSocket 客户端
│   │   └── settings.js                 # 设置
│   └── assets/
├── docs/
│   ├── API.md                          # API 文档
│   └── DESIGN.md                       # 设计文档
├── run.py                              # 打包入口
├── README.md
└── .gitignore
🚀 打包为 EXE
bash
pip install pyinstaller

pyinstaller --name RequirementHub --onedir --clean \
  --add-data "frontend;frontend" \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.protocols.websockets.auto \
  --hidden-import uvicorn.lifespan.on \
  --hidden-import uvicorn.lifespan.off \
  --hidden-import sqlalchemy.dialects.sqlite \
  run.py
产物在 dist/RequirementHub/，整个文件夹即为交付物。

💾 数据备份
数据库文件：*.db（运行目录下）

知识库文件：uploads/ 文件夹（如有）

备份方法：复制这两个文件/文件夹即可。恢复时替换回原位置。

🤝 贡献与反馈
欢迎提交 Issue 和 Pull Request。

Fork 本项目

创建你的功能分支 (git checkout -b feature/AmazingFeature)

提交你的更改 (git commit -m 'Add some AmazingFeature')

推送到分支 (git push origin feature/AmazingFeature)

打开一个 Pull Request

📄 许可证
MIT License

Copyright (c) 2026

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

🙏 致谢
项目	用途
FastAPI	高性能 Web 框架
SQLAlchemy	ORM 框架
智谱 AI	GLM 模型
硅基流动	开源模型 API
Ollama	本地模型运行
DeepSeek	开发辅助
Font Awesome	图标库
⚠️ 免责声明
内网工具定位：本系统面向团队内部部署使用，未做公网级安全加固（防DDoS、渗透防护等），请勿直接暴露于公网；如需公网访问，请自行前置 Nginx 并配置 HTTPS 与访问控制。

数据出域提示：AI 功能通过调用第三方大模型服务商 API 实现，用户输入的文本内容会传输至相应服务商进行推理。涉及商业机密、个人敏感信息的需求描述，请自行评估并遵守所在组织的数据合规要求。可优先选用本地模型（Ollama/LM Studio）实现数据不出内网。

API Key 安全：系统内配置的 API Key 存储于本地数据库，请妥善保管服务器与数据库文件的访问权限；因 Key 泄露导致的用量损失由配置者自行承担。

默认账号：系统首次启动会创建管理员种子账号（admin / admin123），部署后请立即修改默认密码；因未修改默认凭证造成的任何后果由部署方承担。

无担保：本软件按“现状”提供，作者不对功能适用性、数据完整性、服务连续性作任何明示或默示担保。使用本软件产生的任何直接或间接损失，作者不承担责任。

使用范围：仅供学习、研究与企业内部使用，未经许可请勿用于商业转售。

