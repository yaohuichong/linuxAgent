from core.executor import ExecutorManager
from core.llm_client import LLMClient
from core.security import SecurityController
from tools.system_tools import SystemTools
from models.schemas import ParsedIntent, CommandResult, RiskLevel, OperationCategory, SystemInfo
from typing import Dict, Any, List, Optional, Tuple
import json
import time


class LinuxAgent:
    SYSTEM_PROMPT = """你是一个专业的Linux系统智能代理。用户通过自然语言与你交互，你需要理解意图并执行相应操作。

## 可用工具
1. disk_info - 查看磁盘使用情况
2. file_list [path] - 列出目录内容
3. file_find [pattern] [path] - 搜索文件
4. file_read [path] - 读取文件内容
5. file_write [path] [content] - 写入文件
6. process_list [filter] - 查看进程列表
7. process_kill [pid] - 终止进程
8. port_list - 查看监听端口
9. user_list - 查看用户列表
10. user_create [username] - 创建用户
11. user_delete [username] - 删除用户
12. memory_info - 查看内存信息
13. cpu_info - 查看CPU信息
14. network_info - 查看网络信息
15. system_status - 系统整体状态
16. shell [command] - 执行任意shell命令
17. chat [message] - 回答用户问题或解释概念（当用户只是提问、追问或需要解释时使用）

## 响应格式
分析用户输入后，返回JSON：
```json
{
    "tool": "工具名称",
    "args": {"参数名": "参数值"},
    "explanation": "操作说明",
    "risk_level": "low/medium/high/critical"
}
```

## 重要规则
- 总是返回JSON格式
- 结合对话上下文理解用户意图
- 如果用户追问"这是什么意思"、"代表什么"等，使用chat工具并结合上下文详细解释
- 如果用户只是在提问、追问或需要解释，使用chat工具
- 如果用户请求不明确，选择最合适的工具
- 文件写入操作需要用户确认
- 危险命令(rm -rf /等)标记为critical
- 用中文回复用户
- 路径使用$HOME变量，例如：$HOME/桌面、$HOME/文档

## 示例
用户: "查看磁盘" -> {"tool": "disk_info", "args": {}, "explanation": "查看磁盘使用情况", "risk_level": "low"}
用户: "列出桌面的文件" -> {"tool": "file_list", "args": {"path": "$HOME/桌面"}, "explanation": "列出桌面目录内容", "risk_level": "low"}
用户: "写一首诗保存到桌面" -> {"tool": "file_write", "args": {"path": "$HOME/桌面/poem.txt", "content": "春眠不觉晓，处处闻啼鸟。夜来风雨声，花落知多少。"}, "explanation": "创建诗歌文件", "risk_level": "low"}
用户: "只显示文件名" -> {"tool": "shell", "args": {"command": "ls -1"}, "explanation": "仅列出文件名", "risk_level": "low"}
用户: "代表什么意思" -> {"tool": "chat", "args": {"message": "结合上一次执行结果，详细解释每个字段的含义..."}, "explanation": "解释上一次输出结果", "risk_level": "low"}"""

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
        self.last_result: Dict[str, Any] = {}
        
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
        
    def parse_and_execute(self, user_input: str) -> Tuple[str, bool, str]:
        if not self.connected:
            return "未连接到服务器", False, ""
            
        context_info = ""
        if self.conversation_context:
            last_msgs = self.conversation_context[-4:]
            context_info = "\n## 最近对话记录:\n"
            for msg in last_msgs:
                role = "用户" if msg["role"] == "user" else "助手"
                content = msg["content"][:500]
                context_info += f"{role}: {content}\n"
            
        prompt = f"{context_info}\n当前用户输入: {user_input}\n\n请分析意图并返回JSON格式的执行计划。"
        
        for attempt in range(3):
            response = self.llm_client.chat_with_json_response(prompt)
            
            if not response:
                return "无法理解您的请求，请换种方式描述", False, ""
                
            tool = response.get("tool", "")
            args = response.get("args", {})
            explanation = response.get("explanation", "")
            risk_level = response.get("risk_level", "low")
            
            result, success, executed_tool = self._execute_tool(tool, args, explanation, risk_level)
            
            if success:
                return result, True, executed_tool
                
            if attempt < 2:
                prompt = f"{context_info}\n当前用户输入: {user_input}\n\n上一次执行失败:\n工具: {tool}\n错误: {result}\n\n请尝试其他方法，返回JSON格式的执行计划。"
            else:
                return result, False, executed_tool
                
        return "执行失败，已尝试多种方法", False, ""
        
    def _execute_tool(self, tool: str, args: Dict[str, Any], explanation: str, risk_level: str) -> Tuple[str, bool, str]:
        if not self.tools:
            return "工具未初始化", False, tool
            
        try:
            if tool == "disk_info":
                output = self.tools.get_disk_info()
                return output, True, tool
                
            elif tool == "file_list":
                path = args.get("path", ".")
                path = self._expand_path(path)
                success, output = self.tools.execute_custom_command(f"ls -la {path}")
                if success:
                    return f"目录 {path} 内容:\n{output}", True, tool
                return output, False, tool
                
            elif tool == "file_list_simple":
                path = args.get("path", ".")
                path = self._expand_path(path)
                success, output = self.tools.execute_custom_command(f"ls -1 {path}")
                if success:
                    return f"文件列表:\n{output}", True, tool
                return output, False, tool
                
            elif tool == "file_find":
                pattern = args.get("pattern", "*")
                path = self._expand_path(args.get("path", "/"))
                files, error = self.tools.find_files(pattern, path)
                if error:
                    return f"搜索失败: {error}", False, tool
                return f"找到 {len(files)} 个匹配 '{pattern}' 的文件:\n" + "\n".join(f"  📄 {f}" for f in files[:20]), True, tool
                
            elif tool == "file_read":
                path = self._expand_path(args.get("path", ""))
                success, output = self.tools.execute_custom_command(f"cat {path}")
                if success:
                    return f"文件内容:\n{output}", True, tool
                return output, False, tool
                
            elif tool == "file_write":
                path = self._expand_path(args.get("path", ""))
                content = args.get("content", "").replace("'", "'\"'\"'")
                risk, warning = self.security.analyze_command(f"write {path}")
                if risk in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                    return f"⚠️ 安全警告: {warning}", False, tool
                success, output = self.tools.execute_custom_command(f'echo \'{content}\' | tee {path}')
                if success:
                    return f"✅ 文件已保存到 {path}", True, tool
                return f"写入失败: {output}", False, tool
                
            elif tool == "process_list":
                filter_name = args.get("filter", "")
                if filter_name:
                    processes = self.tools.get_process_list(filter_name)
                    if processes and "error" in processes[0]:
                        return f"查询进程失败: {processes[0].get('error', '未知错误')}", False, tool
                    if not processes:
                        return f"没有找到匹配 '{filter_name}' 的进程", True, tool
                else:
                    processes = self.tools.get_process_list()
                    if not processes or "error" in processes[0]:
                        return "无法获取进程信息", False, tool
                output = "进程列表:\n"
                for p in processes[:15]:
                    output += f"  PID:{p.get('pid',''):>6} CPU:{p.get('cpu',''):>5}% MEM:{p.get('mem',''):>5}% {p.get('command','')[:40]}\n"
                return output, True, tool
                
            elif tool == "process_kill":
                pid = args.get("pid", "")
                success, msg = self.tools.kill_process(pid)
                return msg, success, tool
                
            elif tool == "port_list":
                ports = self.tools.get_port_list()
                if not ports or "error" in ports[0]:
                    return "无法获取端口信息", False, tool
                output = "监听端口:\n"
                for p in ports:
                    output += f"  🔌 {p.get('protocol','')} {p.get('address','')}:{p.get('port','')}\n"
                return output, True, tool
                
            elif tool == "user_list":
                output = self.tools.get_user_info()
                return output, True, tool
                
            elif tool == "user_create":
                username = args.get("username", "")
                success, msg = self.tools.create_user(username)
                return msg, success, tool
                
            elif tool == "user_delete":
                username = args.get("username", "")
                success, msg = self.tools.delete_user(username)
                return msg, success, tool
                
            elif tool == "memory_info":
                output = self.tools.get_memory_info()
                return output, True, tool
                
            elif tool == "cpu_info":
                output = self.tools.get_cpu_info()
                return output, True, tool
                
            elif tool == "network_info":
                output = self.tools.get_network_info()
                return output, True, tool
                
            elif tool == "system_status":
                output = self.tools.get_system_status()
                return output, True, tool
                
            elif tool == "chat":
                message = args.get("message", "")
                return message, True, tool
                
            elif tool == "shell":
                command = args.get("command", "")
                risk, warning = self.security.analyze_command(command)
                if risk == RiskLevel.CRITICAL:
                    return f"⛔ 危险操作已阻止: {warning}", False, tool
                if risk == RiskLevel.HIGH:
                    return f"⚠️ 高风险操作: {warning}\n如需执行，请直接输入命令", False, tool
                success, output = self.tools.execute_custom_command(command)
                if success:
                    return f"执行结果:\n{output}", True, tool
                return f"执行失败: {output}", False, tool
                
            else:
                return f"未知工具: {tool}", False, tool
                
        except Exception as e:
            return f"执行错误: {str(e)}", False, tool
            
    def _add_explanation(self, user_input: str, result: str, tool: str) -> str:
        if tool == "chat":
            return result
            
        explain_prompt = f"""用户请求: {user_input}
执行工具: {tool}
原始输出:
{result}

请用简洁友好的中文回复，包括：
1. 简要说明执行了什么操作
2. 解释输出结果的关键信息（如果输出较长，只解释重要部分）
3. 如果发现问题或建议，可以提示用户

直接返回解释内容，不要JSON格式。"""
        
        try:
            explanation = self.llm_client.chat(explain_prompt)
            if explanation:
                return explanation
        except:
            pass
        return result
            
    def _expand_path(self, path: str) -> str:
        if path.startswith("~") or "$HOME" in path:
            pass
        return path
        
    def process_user_input(self, user_input: str) -> str:
        start_time = time.time()
        
        self.conversation_context.append({
            "role": "user",
            "content": user_input,
            "timestamp": start_time
        })
        
        if not self.connected:
            return "❌ 未连接到服务器，请先建立连接"
            
        result, success, tool = self.parse_and_execute(user_input)
        
        if success and result:
            result = self._add_explanation(user_input, result, tool)
        
        execution_time = time.time() - start_time
        status = "✅" if success else "❌"
        
        response = f"{status} {result}\n\n⏱️ 耗时: {execution_time:.2f}秒"
        
        self.conversation_context.append({
            "role": "assistant",
            "content": response,
            "timestamp": time.time()
        })
        
        return response
        
    def get_welcome_message(self) -> str:
        if self.system_info:
            info = self.system_info
            return f"""👋 欢迎使用Linux智能代理！

🖥️  服务器: {info.hostname}
📦 系统: {info.os_version or info.os_type}
🔧 内核: {info.kernel_version}
💾 内存: {info.memory_total}
💿 磁盘: {info.disk_total}

💬 请用自然语言描述您的需求，例如:
   "查看磁盘空间"
   "列出桌面文件"
   "写一首诗保存到桌面"
   "查看进程"
   "搜索nginx进程"
"""
        return "👋 欢迎使用Linux智能代理！请输入您的指令。"
        
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        return self.conversation_context.copy()
        
    def clear_conversation(self):
        self.conversation_context = []
        self.llm_client.clear_history()
        self.llm_client.set_system_prompt(self.SYSTEM_PROMPT)
