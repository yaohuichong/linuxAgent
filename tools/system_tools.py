from core.executor import ExecutorManager
from models.schemas import CommandResult, RiskLevel
from typing import Dict, Any, List, Optional, Tuple
import re


class SystemTools:
    def __init__(self, executor: ExecutorManager):
        self.executor = executor
        
    def get_disk_usage(self, path: str = "/") -> Dict[str, Any]:
        result = self.executor.execute(f"df -h {path}")
        if not result.success:
            return {"error": result.stderr, "success": False}
            
        lines = result.stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            if len(parts) >= 6:
                return {
                    "success": True,
                    "filesystem": parts[0],
                    "total": parts[1],
                    "used": parts[2],
                    "available": parts[3],
                    "used_percent": parts[4],
                    "mount_point": parts[5]
                }
        return {"error": "Unable to parse disk usage", "success": False}
        
    def get_disk_usage_all(self) -> List[Dict[str, Any]]:
        result = self.executor.execute("df -h")
        if not result.success:
            return [{"error": result.stderr}]
            
        disks = []
        lines = result.stdout.strip().split("\n")
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 6:
                disks.append({
                    "filesystem": parts[0],
                    "total": parts[1],
                    "used": parts[2],
                    "available": parts[3],
                    "used_percent": parts[4],
                    "mount_point": parts[5]
                })
        return disks
        
    def get_disk_info(self) -> str:
        disks = self.get_disk_usage_all()
        if not disks:
            return "无法获取磁盘信息"
            
        output = "磁盘使用情况:\n"
        for disk in disks:
            if "error" in disk:
                return f"错误: {disk['error']}"
            output += f"  📁 {disk['mount_point']}: {disk['used']}/{disk['total']} ({disk['used_percent']} 已用)\n"
        return output.strip()
        
    def find_files(self, pattern: str, path: str = "/", max_depth: int = 3) -> Tuple[List[str], str]:
        safe_path = path.replace(";", "").replace("|", "").replace("&", "")
        safe_pattern = pattern.replace(";", "").replace("|", "").replace("&", "")
        
        cmd = f"find {safe_path} -maxdepth {max_depth} -name '*{safe_pattern}*' 2>/dev/null"
        result = self.executor.execute(cmd, timeout=60)
        
        if not result.success:
            return [], result.stderr
            
        files = result.stdout.strip().split("\n")
        files = [f for f in files if f]
        return files[:50], ""
        
    def search_in_files(self, pattern: str, path: str = "/etc") -> Tuple[List[str], str]:
        safe_path = path.replace(";", "").replace("|", "").replace("&", "")
        safe_pattern = pattern.replace(";", "").replace("|", "").replace("&", "")
        
        cmd = f"grep -r -l '{safe_pattern}' {safe_path} 2>/dev/null"
        result = self.executor.execute(cmd, timeout=30)
        
        if not result.success:
            return [], result.stderr
            
        files = result.stdout.strip().split("\n")
        files = [f for f in files if f]
        return files[:20], ""
        
    def list_directory(self, path: str = ".", long_format: bool = True) -> str:
        safe_path = path.replace(";", "").replace("|", "").replace("&", "")
        cmd = f"ls -la {safe_path}" if long_format else f"ls {safe_path}"
        result = self.executor.execute(cmd)
        
        if not result.success:
            return f"无法列出目录: {result.stderr}"
        return result.stdout
        
    def get_process_list(self, filter_name: str = "") -> List[Dict[str, str]]:
        if filter_name:
            cmd = f"ps aux | grep {filter_name} | grep -v grep"
        else:
            cmd = "ps aux --sort=-%mem | head -20"
            
        result = self.executor.execute(cmd)
        if not result.success:
            return []
            
        processes = []
        lines = result.stdout.strip().split("\n")
        for line in lines[1:]:
            parts = line.split(None, 10)
            if len(parts) >= 11:
                processes.append({
                    "user": parts[0],
                    "pid": parts[1],
                    "cpu": parts[2],
                    "mem": parts[3],
                    "vsz": parts[4],
                    "rss": parts[5],
                    "stat": parts[7],
                    "start": parts[8],
                    "time": parts[9],
                    "command": parts[10]
                })
        return processes
        
    def get_process_info(self) -> str:
        processes = self.get_process_list()
        if not processes:
            return "无法获取进程信息"
        if "error" in processes[0]:
            return f"错误: {processes[0]['error']}"
            
        output = "进程列表 (按内存排序):\n"
        for p in processes[:15]:
            output += f"  🔄 PID:{p['pid']:>6} CPU:{p['cpu']:>5}% MEM:{p['mem']:>5}% {p['command'][:40]}\n"
        return output.strip()
        
    def kill_process(self, pid: str, force: bool = False) -> Tuple[bool, str]:
        if not pid.isdigit():
            return False, "无效的进程ID"
            
        signal = "-9" if force else "-15"
        result = self.executor.execute(f"kill {signal} {pid}")
        
        if result.success:
            return True, f"已终止进程 {pid}"
        return False, f"终止进程失败: {result.stderr}"
        
    def get_port_list(self, filter_port: str = "") -> List[Dict[str, str]]:
        cmd = "ss -tuln" if not filter_port else f"ss -tuln | grep {filter_port}"
        result = self.executor.execute(cmd)
        
        if not result.success:
            return [{"error": result.stderr}]
            
        ports = []
        lines = result.stdout.strip().split("\n")
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 5:
                local_addr = parts[3]
                if ":" in local_addr:
                    addr, port = local_addr.rsplit(":", 1)
                else:
                    addr, port = local_addr, ""
                    
                ports.append({
                    "protocol": parts[0],
                    "state": parts[1],
                    "address": addr,
                    "port": port,
                    "process": parts[4] if len(parts) > 4 else ""
                })
        return ports
        
    def get_port_info(self) -> str:
        ports = self.get_port_list()
        if not ports:
            return "无法获取端口信息"
        if "error" in ports[0]:
            return f"错误: {ports[0]['error']}"
            
        output = "监听端口:\n"
        for p in ports:
            output += f"  🔌 {p['protocol']} {p['address']}:{p['port']} ({p['state']})\n"
        return output.strip()
        
    def create_user(self, username: str, shell: str = "/bin/bash", 
                    create_home: bool = True) -> Tuple[bool, str]:
        if not re.match(r'^[a-z_][a-z0-9_-]*$', username):
            return False, "无效的用户名格式"
            
        cmd = f"useradd -m -s {shell} {username}" if create_home else f"useradd -s {shell} {username}"
        result = self.executor.execute(cmd)
        
        if result.success:
            return True, f"用户 {username} 创建成功"
        return False, f"创建用户失败: {result.stderr}"
        
    def delete_user(self, username: str, remove_home: bool = False) -> Tuple[bool, str]:
        if not re.match(r'^[a-z_][a-z0-9_-]*$', username):
            return False, "无效的用户名格式"
            
        if username.lower() in ["root", "admin"]:
            return False, "不能删除系统关键用户"
            
        cmd = f"userdel -r {username}" if remove_home else f"userdel {username}"
        result = self.executor.execute(cmd)
        
        if result.success:
            return True, f"用户 {username} 已删除"
        return False, f"删除用户失败: {result.stderr}"
        
    def list_users(self) -> List[Dict[str, str]]:
        result = self.executor.execute("cat /etc/passwd")
        if not result.success:
            return [{"error": result.stderr}]
            
        users = []
        for line in result.stdout.strip().split("\n"):
            parts = line.split(":")
            if len(parts) >= 7:
                users.append({
                    "username": parts[0],
                    "uid": parts[2],
                    "gid": parts[3],
                    "home": parts[5],
                    "shell": parts[6]
                })
        return users
        
    def get_user_info(self) -> str:
        users = self.list_users()
        if not users:
            return "无法获取用户信息"
        if "error" in users[0]:
            return f"错误: {users[0]['error']}"
            
        normal_users = [u for u in users if int(u["uid"]) >= 1000 and u["shell"] not in ["/sbin/nologin", "/bin/false"]]
        
        output = "系统用户:\n"
        for u in normal_users:
            output += f"  👤 {u['username']} (UID:{u['uid']}, Home:{u['home']})\n"
        return output.strip()
        
    def get_memory_info(self) -> str:
        result = self.executor.execute("free -h")
        if not result.success:
            return f"无法获取内存信息: {result.stderr}"
            
        lines = result.stdout.strip().split("\n")
        output = "内存使用情况:\n"
        for line in lines:
            output += f"  {line}\n"
        return output.strip()
        
    def get_cpu_info(self) -> str:
        result = self.executor.execute("lscpu | grep -E '^(Model name|CPU\\(s\\)|CPU MHz|CPU max)'")
        if not result.success:
            return f"无法获取CPU信息: {result.stderr}"
        return f"CPU信息:\n{result.stdout.strip()}"
        
    def get_network_info(self) -> str:
        result = self.executor.execute("ip addr show | grep -E 'inet |link/ether'")
        if not result.success:
            return f"无法获取网络信息: {result.stderr}"
            
        lines = result.stdout.strip().split("\n")
        output = "网络配置:\n"
        for line in lines:
            output += f"  {line.strip()}\n"
        return output.strip()
        
    def get_system_status(self) -> str:
        disk = self.get_disk_info()
        memory = self.get_memory_info()
        processes = self.get_process_info()
        
        return f"{disk}\n\n{memory}\n\n{processes}"
        
    def execute_custom_command(self, command: str) -> Tuple[bool, str]:
        result = self.executor.execute(command)
        if result.success:
            return True, result.stdout if result.stdout else "命令执行成功（无输出）"
        return False, f"命令执行失败:\n{result.stderr}"
