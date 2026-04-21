# Linux 智能代理 (Linux Agent)

基于大语言模型的Linux服务器智能管理助手，支持自然语言交互，实现服务器运维的"去命令行化"体验。

> AI Hackathon 2026 预赛作品

## 功能特性

### 基础能力
- 磁盘使用情况监测
- 文件/目录检索与管理
- 进程状态查询与管理
- 端口监听状态查询
- 用户创建、删除与查询

### 进阶能力
- 高风险操作识别与预警
- 敏感命令拦截
- 操作二次确认
- 风险行为可解释性说明

### 探索能力
- 多轮对话上下文管理
- 自然语言意图解析
- 多模态交互支持

## 项目结构

```
linuxAgent/
├── agent/              # Agent核心逻辑
│   └── linux_agent.py  # 主Agent类
├── core/               # 核心模块
│   ├── executor.py     # 命令执行器（本地/SSH远程）
│   ├── llm_client.py   # LLM客户端
│   └── security.py     # 安全控制器
├── models/             # 数据模型
│   └── schemas.py      # Pydantic模型定义
├── tools/              # 系统工具集
│   └── system_tools.py # 系统管理工具
├── cli/                # CLI交互界面
│   └── main.py         # Rich终端界面
├── tests/              # 测试模块
├── run.py              # 启动入口
├── requirements.txt    # 依赖包
├── .env                # 配置文件
└── README.md           # 说明文档
```

## 快速开始

### 1. 环境要求
- Python 3.10+
- Linux服务器环境（用于执行命令）

### 2. 安装依赖

```bash
# 创建conda环境
conda create -n linuxAgent python=3.10
conda activate linuxAgent

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置

复制配置模板并编辑：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# LLM配置（支持OpenAI兼容API）
OPENAI_API_KEY=your_api_key
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_MODEL=gpt-4

# SSH配置（远程连接模式）
SSH_HOST=your_server_ip
SSH_PORT=22
SSH_USERNAME=your_username
SSH_PASSWORD=your_password
SSH_KEY_PATH=

# 安全配置
RISK_LEVEL=medium
```

### 4. 运行

```bash
python run.py
```

启动后选择连接方式：
- **选项1**: 本地执行（需要在Linux环境下运行）
- **选项2**: SSH远程连接（手动输入连接信息）
- **选项3**: 使用环境变量配置（读取.env文件）
- **选项4**: 退出

## 使用示例

### 磁盘管理
```
>>> 查看磁盘使用情况
>>> 查看所有磁盘空间
```

### 进程管理
```
>>> 查看进程
>>> 搜索nginx进程
>>> 终止进程 12345
```

### 文件管理
```
>>> 搜索名为nginx.conf的文件
>>> 列出/etc目录内容
```

### 端口管理
```
>>> 查看监听端口
>>> 查看网络状态
```

### 用户管理
```
>>> 查看用户列表
>>> 创建用户 testuser
>>> 删除用户 testuser
```

### 系统监控
```
>>> 查看系统状态
>>> 查看内存使用情况
>>> 查看CPU信息
```

## 安全特性

### 风险级别

| 级别 | 说明 | 处理方式 |
|------|------|----------|
| LOW | 安全操作 | 直接执行 |
| MEDIUM | 一般风险 | 提示警告 |
| HIGH | 高风险操作 | 需确认后执行 |
| CRITICAL | 危险操作 | 禁止执行 |

### 被拦截的危险命令示例
- `rm -rf /` - 删除根目录
- `dd if=/dev/zero of=/dev/sda` - 格式化磁盘
- `chmod 777 /etc/passwd` - 修改关键文件权限
- `> /etc/shadow` - 覆盖密码文件

## CLI命令

| 命令 | 说明 |
|------|------|
| `help` | 显示帮助信息 |
| `status` | 显示连接状态 |
| `history` | 显示对话历史 |
| `clear` | 清屏 |
| `exit` | 退出程序 |

## 支持的LLM

本系统支持OpenAI兼容的API：
- OpenAI GPT-4
- 百度千帆
- 阿里通义千问
- 其他兼容OpenAI格式的模型

## API配置示例

### OpenAI
```env
OPENAI_API_KEY=sk-xxx
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_MODEL=gpt-4
```

### 百度千帆
```env
OPENAI_API_KEY=bce-v3/xxx
OPENAI_API_BASE=https://qianfan.baidubce.com/v2/coding
OPENAI_MODEL=glm-5
```

## 测试

运行测试脚本：

```bash
python tests/test_agent.py
```

## 技术栈

- **语言**: Python 3.10+
- **LLM**: OpenAI API (兼容接口)
- **SSH**: Paramiko
- **CLI**: Rich + Prompt Toolkit
- **数据验证**: Pydantic
- **配置管理**: python-dotenv

## 许可证

MIT License

## 作者

AI Hackathon 2026 参赛作品
