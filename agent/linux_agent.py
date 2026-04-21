from core.executor import ExecutorManager
from core.llm_client import LLMClient
from core.security import SecurityController
from tools.system_tools import SystemTools
from models.schemas import ParsedIntent, CommandResult, RiskLevel, OperationCategory, SystemInfo
from typing import Dict, Any, List, Optional, Tuple
import json
import time


class LinuxAgent:
    SYSTEM_PROMPT = """你是一个专业的Linux系统智能代理助手。你的职责是帮助用户通过自然语言管理和操作Linux服务器。

## 核心能力
1. 磁盘管理：查看磁盘使用情况、磁盘空间监控
2. 文件管理：搜索文件、查看目录内容、文件检索
3. 进程管理：查看进程、终止进程、进程状态监控
4. 端口管理：查看监听端口、网络连接状态
5. 用户管理：创建用户、删除用户、查看用户列表
6. 系统监控：CPU、内存、网络状态查询

## 安全规则
- 高风险操作需要用户确认
- 禁止执行危险命令（如 rm -rf /、格式化磁盘等）
- 对于敏感操作提供风险提示
- 所有操作需要有清晰的原因说明

## 响应格式
当用户请求执行操作时，请以JSON格式返回：
```json
{
    "intent": "用户意图描述",
    "category": "操作类别(disk/file/process/port/user/system)",
    "action": "要执行的动作",
    "parameters": {},
    "requires_confirmation": false,
    "risk_level": "low/medium/high/critical",
    "explanation": "操作说明"
}
```

## 交互原则
- 使用中文回复
- 保持友好、专业的语气
- 提供清晰的执行结果反馈
- 对复杂操作提供步骤说明
- 遇到错误时给出解决建议"""

    def __init__(self, api_key: str = "", api_base: str = "", model: str = "",
                 ssh_config: Dict[str, Any] = None, risk_level: str = "high"):
        self.llm_client = LLMClient()
        if api_key:
            self.llm_client.client.api_key = api_key
        if api_base:
            self.llm_client.client.base_url = api_base
        if model:
            self.llm_client.model = model
            
        self.llm_client.set_system_prompt(self.SYSTEM_PROMPT)
        
        self.executor = ExecutorManager()
        self.security = SecurityController(max_risk_level=risk_level)
        self.tools: Optional[SystemTools] = None
        
        self.conversation_context: List[Dict[str, Any]] = []
        self.system_info: Optional[SystemInfo] = None
        self.connected = False
        
    def connect_local(self) -> Tuple[bool, str]:
        success, message = self.executor.setup_local()
        if success:
            self.tools = SystemTools(self.executor)
            self.system_info = self.executor.get_system_info()
            self.connected = True
        return success, message
        
    def connect_remote(self, host: str, port: int = 22, username: str = "",
                       password: str = "", key_path: str = "") -> Tuple[bool, str]:
        success, message = self.executor.setup_remote(host, port, username, password, key_path)
        if success:
            self.tools = SystemTools(self.executor)
            self.system_info = self.executor.get_system_info()
            self.connected = True
        return success, message
        
    def disconnect(self):
        self.executor.disconnect()
        self.connected = False
        
    def parse_intent(self, user_input: str) -> ParsedIntent:
        is_valid, validation_error = self.security.validate_input(user_input)
        if not is_valid:
            return ParsedIntent(
                original_input=user_input,
                intent="invalid",
                category=OperationCategory.UNKNOWN,
                confidence=0.0,
                explanation=f"输入验证失败: {validation_error}"
            )
            
        prompt = f"""请分析以下用户输入，返回JSON格式的意图分析结果：

用户输入: {user_input}

请返回符合要求的JSON格式响应。"""
        
        response = self.llm_client.chat_with_json_response(prompt)
        
        if not response:
            return ParsedIntent(
                original_input=user_input,
                intent="unknown",
                category=OperationCategory.UNKNOWN,
                confidence=0.0,
                explanation="无法解析用户意图"
            )
            
        try:
            category_str = response.get("category", "unknown").upper()
            category = OperationCategory[category_str] if category_str in OperationCategory.__members__ else OperationCategory.UNKNOWN
            
            risk_str = response.get("risk_level", "low").upper()
            risk_level = RiskLevel[risk_str] if risk_str in RiskLevel.__members__ else RiskLevel.LOW
            
            return ParsedIntent(
                original_input=user_input,
                intent=response.get("intent", ""),
                category=category,
                parameters=response.get("parameters", {}),
                confidence=0.9,
                requires_confirmation=response.get("requires_confirmation", False),
                risk_level=risk_level,
                explanation=response.get("explanation", "")
            )
        except Exception as e:
            return ParsedIntent(
                original_input=user_input,
                intent="parse_error",
                category=OperationCategory.UNKNOWN,
                confidence=0.0,
                explanation=f"解析错误: {str(e)}"
            )
            
    def execute_intent(self, intent: ParsedIntent) -> Tuple[bool, str, Optional[CommandResult]]:
        if not self.connected or not self.tools:
            return False, "未连接到服务器，请先建立连接", None
            
        result = None
        
        if intent.category == OperationCategory.DISK:
            if "查询" in intent.intent or "查看" in intent.intent or "使用" in intent.intent:
                output = self.tools.get_disk_info()
                return True, output, None
            elif "所有" in intent.intent or "全部" in intent.intent:
                disks = self.tools.get_disk_usage_all()
                output = "所有磁盘使用情况:\n"
                for d in disks:
                    output += f"  {d['mount_point']}: {d['used']}/{d['total']} ({d['used_percent']})\n"
                return True, output, None
                
        elif intent.category == OperationCategory.FILE:
            if "搜索" in intent.intent or "查找" in intent.intent:
                pattern = intent.parameters.get("pattern", intent.parameters.get("name", "*"))
                path = intent.parameters.get("path", "/")
                files, error = self.tools.find_files(pattern, path)
                if error:
                    return False, f"搜索失败: {error}", None
                output = f"找到 {len(files)} 个匹配 '{pattern}' 的文件:\n"
                for f in files[:20]:
                    output += f"  📄 {f}\n"
                return True, output, None
            elif "列出" in intent.intent or "目录" in intent.intent:
                path = intent.parameters.get("path", ".")
                output = self.tools.list_directory(path)
                return True, output, None
                
        elif intent.category == OperationCategory.PROCESS:
            if "查看" in intent.intent or "列表" in intent.intent or "进程" in intent.intent:
                filter_name = intent.parameters.get("name", "")
                if filter_name:
                    processes = self.tools.get_process_list(filter_name)
                    output = f"匹配 '{filter_name}' 的进程:\n"
                else:
                    output = self.tools.get_process_info()
                    return True, output, None
                for p in processes:
                    output += f"  PID:{p['pid']} {p['command']}\n"
                return True, output, None
            elif "终止" in intent.intent or "结束" in intent.intent or "kill" in intent.intent.lower():
                pid = intent.parameters.get("pid", "")
                force = intent.parameters.get("force", False)
                success, message = self.tools.kill_process(pid, force)
                return success, message, None
                
        elif intent.category == OperationCategory.PORT:
            output = self.tools.get_port_info()
            return True, output, None
            
        elif intent.category == OperationCategory.USER:
            if "创建" in intent.intent or "添加" in intent.intent:
                username = intent.parameters.get("username", "")
                shell = intent.parameters.get("shell", "/bin/bash")
                success, message = self.tools.create_user(username, shell)
                return success, message, None
            elif "删除" in intent.intent:
                username = intent.parameters.get("username", "")
                remove_home = intent.parameters.get("remove_home", False)
                risk, warning = self.security.check_user_operation("delete", username)
                if risk in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                    return False, self.security.generate_warning_message(risk, warning, f"删除用户 {username}"), None
                success, message = self.tools.delete_user(username, remove_home)
                return success, message, None
            elif "查看" in intent.intent or "列表" in intent.intent:
                output = self.tools.get_user_info()
                return True, output, None
                
        elif intent.category == OperationCategory.SYSTEM:
            if "状态" in intent.intent or "概览" in intent.intent:
                output = self.tools.get_system_status()
                return True, output, None
            elif "内存" in intent.intent:
                output = self.tools.get_memory_info()
                return True, output, None
            elif "cpu" in intent.intent.lower() or "CPU" in intent.intent:
                output = self.tools.get_cpu_info()
                return True, output, None
            elif "网络" in intent.intent:
                output = self.tools.get_network_info()
                return True, output, None
                
        return False, f"暂不支持该操作: {intent.intent}", None
        
    def process_user_input(self, user_input: str) -> str:
        start_time = time.time()
        
        self.conversation_context.append({
            "role": "user",
            "content": user_input,
            "timestamp": start_time
        })
        
        intent = self.parse_intent(user_input)
        
        if intent.category == OperationCategory.UNKNOWN:
            response = self.llm_client.chat(user_input)
            self.conversation_context.append({
                "role": "assistant",
                "content": response,
                "timestamp": time.time()
            })
            return response
            
        if intent.requires_confirmation or intent.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            warning = self.security.generate_warning_message(
                intent.risk_level,
                intent.explanation,
                user_input
            )
            if intent.risk_level == RiskLevel.CRITICAL:
                self.conversation_context.append({
                    "role": "assistant",
                    "content": warning,
                    "timestamp": time.time()
                })
                return warning
                
        success, message, result = self.execute_intent(intent)
        
        execution_time = time.time() - start_time
        response = self._format_response(intent, success, message, execution_time)
        
        self.conversation_context.append({
            "role": "assistant",
            "content": response,
            "timestamp": time.time(),
            "intent": intent,
            "result": result
        })
        
        return response
        
    def _format_response(self, intent: ParsedIntent, success: bool, 
                         message: str, execution_time: float) -> str:
        status_icon = "✅" if success else "❌"
        response = f"{status_icon} {message}\n\n"
        response += f"📊 执行耗时: {execution_time:.2f}秒\n"
        
        if intent.explanation:
            response += f"💡 说明: {intent.explanation}"
            
        return response
        
    def get_welcome_message(self) -> str:
        if self.system_info:
            info = self.system_info
            return f"""👋 欢迎使用Linux智能代理！

🖥️  服务器信息:
   主机名: {info.hostname}
   系统: {info.os_version or info.os_type}
   内核: {info.kernel_version}
   CPU核心: {info.cpu_cores}
   内存: {info.memory_total}
   磁盘: {info.disk_total}
   运行时间: {info.uptime}

📝 可用功能:
   • 磁盘管理: 查看磁盘使用情况
   • 文件管理: 搜索文件、查看目录
   • 进程管理: 查看进程、终止进程
   • 端口管理: 查看监听端口
   • 用户管理: 创建/删除/查看用户
   • 系统监控: CPU、内存、网络状态

💬 请输入自然语言指令，例如：
   "查看磁盘使用情况"
   "搜索名为nginx的进程"
   "创建一个test用户"
   "查看监听端口"
"""
        return "👋 欢迎使用Linux智能代理！请输入您的指令。"
        
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        return self.conversation_context.copy()
        
    def clear_conversation(self):
        self.conversation_context = []
        self.llm_client.clear_history()
        self.llm_client.set_system_prompt(self.SYSTEM_PROMPT)
