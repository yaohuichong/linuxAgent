from agent.linux_agent import LinuxAgent
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.markdown import Markdown
from rich import print as rprint
import os
import sys
from typing import Optional


class CLIInterface:
    def __init__(self):
        self.console = Console()
        self.agent: Optional[LinuxAgent] = None
        
    def print_banner(self):
        banner = """
██╗     ██╗███╗   ██╗██╗   ██╗██╗  ██╗     ██╗    ██╗██╗  ██╗
██║     ██║████╗  ██║██║   ██║╚██╗██╔╝     ██║    ██║╚██╗██╔╝
██║     ██║██╔██╗ ██║██║   ██║ ╚███╔╝█████╗██║ █╗ ██║ ╚███╔╝ 
██║     ██║██║╚██╗██║██║   ██║ ██╔██╗╚════╝██║███╗██║ ██╔██╗ 
███████╗██║██║ ╚████║╚██████╔╝██╔╝ ██╗    ╚███╔███╔╝██╔╝ ██╗
╚══════╝╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝  ╚═╝     ╚══╝╚══╝ ╚═╝  ╚═╝
                                                               
        Linux 智能代理 v1.0 | AI Hackathon 2026
        """
        self.console.print(Panel(banner, style="bold blue"))
        
    def setup_connection(self) -> bool:
        self.console.print("\n[bold cyan]请选择连接方式:[/bold cyan]")
        self.console.print("  1. 本地执行 (需要Linux环境)")
        self.console.print("  2. SSH远程连接")
        self.console.print("  3. 使用环境变量配置")
        self.console.print("  4. 退出")
        
        choice = Prompt.ask("\n请选择", choices=["1", "2", "3", "4"], default="1")
        
        if choice == "1":
            return self._setup_local()
        elif choice == "2":
            return self._setup_ssh()
        elif choice == "3":
            return self._setup_from_env()
        else:
            return False
            
    def _setup_local(self) -> bool:
        self.agent = LinuxAgent()
        success, message = self.agent.connect_local()
        if success:
            self.console.print(f"[green]✓ {message}[/green]")
            return True
        else:
            self.console.print(f"[red]✗ {message}[/red]")
            return False
            
    def _setup_ssh(self) -> bool:
        self.console.print("\n[bold cyan]SSH连接配置:[/bold cyan]")
        host = Prompt.ask("主机地址", default="localhost")
        port = int(Prompt.ask("端口", default="22"))
        username = Prompt.ask("用户名")
        
        auth_choice = Prompt.ask("认证方式", choices=["password", "key"], default="password")
        
        if auth_choice == "password":
            import getpass
            password = getpass.getpass("密码: ")
            key_path = ""
        else:
            password = ""
            key_path = Prompt.ask("密钥文件路径", default="~/.ssh/id_rsa")
            key_path = os.path.expanduser(key_path)
            
        self.agent = LinuxAgent()
        success, message = self.agent.connect_remote(host, port, username, password, key_path)
        
        if success:
            self.console.print(f"[green]✓ {message}[/green]")
            return True
        else:
            self.console.print(f"[red]✗ {message}[/red]")
            return False
            
    def _setup_from_env(self) -> bool:
        from dotenv import load_dotenv
        load_dotenv()
        
        ssh_host = os.getenv("SSH_HOST", "")
        
        if ssh_host:
            self.console.print(f"[cyan]检测到SSH配置: {ssh_host}[/cyan]")
            self.agent = LinuxAgent(
                api_key=os.getenv("OPENAI_API_KEY", ""),
                api_base=os.getenv("OPENAI_API_BASE", ""),
                model=os.getenv("OPENAI_MODEL", "gpt-4"),
                risk_level=os.getenv("RISK_LEVEL", "high")
            )
            
            success, message = self.agent.connect_remote(
                host=ssh_host,
                port=int(os.getenv("SSH_PORT", "22")),
                username=os.getenv("SSH_USERNAME", ""),
                password=os.getenv("SSH_PASSWORD", ""),
                key_path=os.getenv("SSH_KEY_PATH", "")
            )
            
            if success:
                self.console.print(f"[green]✓ {message}[/green]")
                return True
            else:
                self.console.print(f"[red]✗ {message}[/red]")
                return False
        else:
            self.console.print("[cyan]未检测到SSH配置，尝试本地连接...[/cyan]")
            self.agent = LinuxAgent(
                api_key=os.getenv("OPENAI_API_KEY", ""),
                api_base=os.getenv("OPENAI_API_BASE", ""),
                model=os.getenv("OPENAI_MODEL", "gpt-4"),
                risk_level=os.getenv("RISK_LEVEL", "high")
            )
            success, message = self.agent.connect_local()
            if success:
                self.console.print(f"[green]✓ {message}[/green]")
                return True
            else:
                self.console.print(f"[red]✗ {message}[/red]")
                return False
                
    def run(self):
        self.print_banner()
        
        if not self.setup_connection():
            self.console.print("[red]连接失败，程序退出[/red]")
            return
            
        self.console.print(self.agent.get_welcome_message())
        
        while True:
            try:
                user_input = Prompt.ask("\n[bold green]>>>[/bold green]")
                
                if not user_input.strip():
                    continue
                    
                if user_input.lower() in ["exit", "quit", "退出", "q"]:
                    self.console.print("[yellow]再见！[/yellow]")
                    break
                    
                if user_input.lower() in ["clear", "清屏"]:
                    self.console.clear()
                    self.print_banner()
                    continue
                    
                if user_input.lower() in ["help", "帮助", "?"]:
                    self.show_help()
                    continue
                    
                if user_input.lower() in ["status", "状态"]:
                    self.show_status()
                    continue
                    
                if user_input.lower() in ["history", "历史"]:
                    self.show_history()
                    continue
                    
                with self.console.status("[bold blue]处理中...[/bold blue]"):
                    response = self.agent.process_user_input(user_input)
                    
                self.console.print(Panel(Markdown(response), title="响应", border_style="blue"))
                
            except KeyboardInterrupt:
                self.console.print("\n[yellow]使用 'exit' 退出程序[/yellow]")
            except Exception as e:
                self.console.print(f"[red]错误: {str(e)}[/red]")
                
        if self.agent:
            self.agent.disconnect()
            
    def show_help(self):
        help_text = """
## 可用命令

### 系统管理
- `查看磁盘使用情况` - 显示磁盘空间使用情况
- `查看内存状态` - 显示内存使用情况
- `查看CPU信息` - 显示CPU详细信息
- `查看系统状态` - 显示系统概览

### 文件管理
- `搜索文件 [名称]` - 搜索指定名称的文件
- `列出目录 [路径]` - 列出目录内容
- `查看文件 [路径]` - 查看文件内容

### 进程管理
- `查看进程` - 显示运行中的进程
- `搜索进程 [名称]` - 搜索指定名称的进程
- `终止进程 [PID]` - 终止指定进程

### 端口管理
- `查看端口` - 显示监听端口
- `查看网络状态` - 显示网络配置

### 用户管理
- `查看用户` - 显示系统用户列表
- `创建用户 [用户名]` - 创建新用户
- `删除用户 [用户名]` - 删除用户

### 其他
- `help` - 显示帮助信息
- `status` - 显示连接状态
- `history` - 显示对话历史
- `clear` - 清屏
- `exit` - 退出程序
        """
        self.console.print(Panel(Markdown(help_text), title="帮助", border_style="green"))
        
    def show_status(self):
        if not self.agent or not self.agent.connected:
            self.console.print("[red]未连接到服务器[/red]")
            return
            
        info = self.agent.system_info
        if info:
            table = Table(title="服务器状态")
            table.add_column("项目", style="cyan")
            table.add_column("值", style="green")
            
            table.add_row("主机名", info.hostname)
            table.add_row("操作系统", info.os_version or info.os_type)
            table.add_row("内核版本", info.kernel_version)
            table.add_row("CPU核心", str(info.cpu_cores))
            table.add_row("内存", info.memory_total)
            table.add_row("磁盘", info.disk_total)
            table.add_row("运行时间", info.uptime)
            
            self.console.print(table)
        else:
            self.console.print("[yellow]无法获取系统信息[/yellow]")
            
    def show_history(self):
        if not self.agent:
            self.console.print("[red]代理未初始化[/red]")
            return
            
        history = self.agent.get_conversation_history()
        if not history:
            self.console.print("[yellow]暂无对话历史[/yellow]")
            return
            
        self.console.print("\n[bold cyan]对话历史:[/bold cyan]")
        for i, msg in enumerate(history, 1):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            
            if role == "user":
                self.console.print(f"\n[bold blue]用户:[/bold blue] {content[:100]}{'...' if len(content) > 100 else ''}")
            else:
                self.console.print(f"[bold green]助手:[/bold green] {content[:100]}{'...' if len(content) > 100 else ''}")


def main():
    cli = CLIInterface()
    cli.run()


if __name__ == "__main__":
    main()
