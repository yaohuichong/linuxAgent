from models.schemas import SystemInfo, CommandResult
import subprocess
import platform
import shutil
import os
import time
import re
from typing import Optional, Tuple


class LocalExecutor:
    def __init__(self):
        self.system_info: Optional[SystemInfo] = None
        
    def get_system_info(self) -> SystemInfo:
        info = SystemInfo()
        try:
            info.hostname = platform.node()
            info.os_type = platform.system()
            info.os_version = platform.version()
            
            if info.os_type == "Linux":
                try:
                    with open("/etc/os-release", "r") as f:
                        content = f.read()
                        match = re.search(r'PRETTY_NAME="([^"]+)"', content)
                        if match:
                            info.os_version = match.group(1)
                except:
                    pass
                    
                info.kernel_version = platform.release()
                
                try:
                    with open("/proc/cpuinfo", "r") as f:
                        cpu_count = f.read().count("processor")
                        info.cpu_cores = cpu_count
                except:
                    info.cpu_cores = os.cpu_count() or 1
                    
                try:
                    with open("/proc/meminfo", "r") as f:
                        for line in f:
                            if line.startswith("MemTotal:"):
                                mem_kb = int(line.split()[1])
                                info.memory_total = f"{mem_kb // 1024 // 1024}GB"
                                break
                except:
                    pass
                    
                try:
                    result = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
                    lines = result.stdout.strip().split("\n")
                    if len(lines) >= 2:
                        parts = lines[1].split()
                        if len(parts) >= 2:
                            info.disk_total = parts[1]
                except:
                    pass
                    
                try:
                    with open("/proc/uptime", "r") as f:
                        uptime_seconds = float(f.read().split()[0])
                        days = int(uptime_seconds // 86400)
                        hours = int((uptime_seconds % 86400) // 3600)
                        info.uptime = f"{days}d {hours}h"
                except:
                    pass
        except Exception as e:
            pass
            
        self.system_info = info
        return info
        
    def execute(self, command: str, timeout: int = 30) -> CommandResult:
        start_time = time.time()
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            execution_time = time.time() - start_time
            return CommandResult(
                success=result.returncode == 0,
                command=command,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                execution_time=execution_time
            )
        except subprocess.TimeoutExpired:
            return CommandResult(
                success=False,
                command=command,
                stderr=f"Command timed out after {timeout} seconds",
                exit_code=-1,
                execution_time=timeout
            )
        except Exception as e:
            return CommandResult(
                success=False,
                command=command,
                stderr=str(e),
                exit_code=-1,
                execution_time=time.time() - start_time
            )
            
    def is_available(self) -> bool:
        return platform.system() == "Linux"


class RemoteExecutor:
    def __init__(self, host: str, port: int = 22, username: str = "", 
                 password: str = "", key_path: str = ""):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_path = key_path
        self.client = None
        self.system_info: Optional[SystemInfo] = None
        
    def connect(self) -> Tuple[bool, str]:
        try:
            import paramiko
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            connect_kwargs = {
                "hostname": self.host,
                "port": self.port,
                "username": self.username,
                "timeout": 10
            }
            
            if self.key_path and os.path.exists(self.key_path):
                connect_kwargs["key_filename"] = self.key_path
            elif self.password:
                connect_kwargs["password"] = self.password
            else:
                return False, "No authentication method provided"
                
            self.client.connect(**connect_kwargs)
            return True, "Connected successfully"
        except ImportError:
            return False, "paramiko not installed. Run: pip install paramiko"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
            
    def disconnect(self):
        if self.client:
            self.client.close()
            self.client = None
            
    def execute(self, command: str, timeout: int = 30) -> CommandResult:
        if not self.client:
            return CommandResult(
                success=False,
                command=command,
                stderr="Not connected to remote host",
                exit_code=-1
            )
            
        start_time = time.time()
        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            execution_time = time.time() - start_time
            
            return CommandResult(
                success=exit_code == 0,
                command=command,
                stdout=stdout.read().decode('utf-8', errors='replace'),
                stderr=stderr.read().decode('utf-8', errors='replace'),
                exit_code=exit_code,
                execution_time=execution_time
            )
        except Exception as e:
            return CommandResult(
                success=False,
                command=command,
                stderr=str(e),
                exit_code=-1,
                execution_time=time.time() - start_time
            )
            
    def get_system_info(self) -> SystemInfo:
        info = SystemInfo()
        info.hostname = self.host
        info.os_type = "Linux"
        
        result = self.execute("cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d'\"' -f2")
        if result.success and result.stdout:
            info.os_version = result.stdout.strip()
            
        result = self.execute("uname -r")
        if result.success:
            info.kernel_version = result.stdout.strip()
            
        result = self.execute("nproc")
        if result.success:
            info.cpu_cores = int(result.stdout.strip())
            
        result = self.execute("free -h | awk '/^Mem:/ {print $2}'")
        if result.success:
            info.memory_total = result.stdout.strip()
            
        result = self.execute("df -h / | tail -1 | awk '{print $2}'")
        if result.success:
            info.disk_total = result.stdout.strip()
            
        result = self.execute("uptime -p 2>/dev/null || uptime")
        if result.success:
            info.uptime = result.stdout.strip().replace("up ", "")
            
        self.system_info = info
        return info
        
    def is_available(self) -> bool:
        return self.client is not None


class ExecutorManager:
    def __init__(self):
        self.executor = None
        self.mode = "local"
        
    def setup_local(self) -> Tuple[bool, str]:
        executor = LocalExecutor()
        if not executor.is_available():
            return False, "Local execution requires Linux system"
        self.executor = executor
        self.mode = "local"
        return True, "Local executor initialized"
        
    def setup_remote(self, host: str, port: int = 22, username: str = "",
                     password: str = "", key_path: str = "") -> Tuple[bool, str]:
        executor = RemoteExecutor(host, port, username, password, key_path)
        success, message = executor.connect()
        if success:
            self.executor = executor
            self.mode = "remote"
        return success, message
        
    def execute(self, command: str, timeout: int = 30) -> CommandResult:
        if not self.executor:
            return CommandResult(
                success=False,
                command=command,
                stderr="No executor configured",
                exit_code=-1
            )
        return self.executor.execute(command, timeout)
        
    def get_system_info(self) -> SystemInfo:
        if self.executor:
            return self.executor.get_system_info()
        return SystemInfo()
        
    def is_connected(self) -> bool:
        return self.executor is not None
        
    def get_username(self) -> str:
        if isinstance(self.executor, RemoteExecutor):
            return self.executor.username
        return ""
        
    def disconnect(self):
        if isinstance(self.executor, RemoteExecutor):
            self.executor.disconnect()
        self.executor = None
