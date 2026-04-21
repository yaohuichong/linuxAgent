from models.schemas import RiskLevel, ParsedIntent, CommandResult
from typing import List, Dict, Tuple, Optional
import re


class SecurityController:
    CRITICAL_PATHS = [
        "/", "/bin", "/boot", "/dev", "/etc", "/lib", "/lib64",
        "/proc", "/root", "/sbin", "/sys", "/usr", "/var"
    ]
    
    CRITICAL_FILES = [
        "/etc/passwd", "/etc/shadow", "/etc/sudoers", "/etc/fstab",
        "/etc/hosts", "/etc/resolv.conf", "/etc/ssh/sshd_config",
        "/boot/vmlinuz", "/boot/initrd"
    ]
    
    DANGEROUS_PATTERNS = [
        (r"rm\s+-rf\s+/(?!\S)", "Attempting to delete root filesystem", RiskLevel.CRITICAL),
        (r"rm\s+-rf\s+/(?:bin|boot|etc|lib|lib64|root|sbin|sys|usr|var)", "Attempting to delete critical system directory", RiskLevel.CRITICAL),
        (r">\s*/etc/passwd", "Attempting to overwrite password file", RiskLevel.CRITICAL),
        (r">\s*/etc/shadow", "Attempting to overwrite shadow file", RiskLevel.CRITICAL),
        (r"chmod\s+777\s+/", "Attempting to set world-writable permissions on root", RiskLevel.CRITICAL),
        (r"chmod\s+-R\s+777", "Attempting recursive world-writable permissions", RiskLevel.HIGH),
        (r"chown\s+-R\s+\S+\s+/", "Attempting recursive ownership change on root", RiskLevel.HIGH),
        (r"dd\s+if=.*of=/dev/", "Attempting to write directly to device", RiskLevel.CRITICAL),
        (r"mkfs\.", "Attempting to format filesystem", RiskLevel.CRITICAL),
        (r"fdisk\s+/dev/", "Attempting to modify disk partition", RiskLevel.HIGH),
        (r"userdel\s+-r\s+root", "Attempting to delete root user", RiskLevel.CRITICAL),
        (r"passwd\s+root", "Attempting to change root password", RiskLevel.HIGH),
        (r"shutdown", "System shutdown command", RiskLevel.HIGH),
        (r"reboot", "System reboot command", RiskLevel.HIGH),
        (r"init\s+[06]", "Attempting to change runlevel to halt/reboot", RiskLevel.HIGH),
        (r":()\s*{\s*:\s*;\s*}\s*;:", "Fork bomb detected", RiskLevel.CRITICAL),
        (r"curl.*\|\s*bash", "Piping remote content to bash", RiskLevel.HIGH),
        (r"wget.*\|\s*bash", "Piping remote content to bash", RiskLevel.HIGH),
        (r"iptables\s+-F", "Flushing firewall rules", RiskLevel.HIGH),
        (r"systemctl\s+(stop|disable)\s+(sshd|firewall|iptables)", "Stopping critical service", RiskLevel.MEDIUM),
    ]
    
    SENSITIVE_FILES = [
        "/etc/passwd", "/etc/shadow", "/etc/sudoers", "/etc/ssh/",
        "/root/.ssh/", "/var/log/auth.log", "/var/log/secure"
    ]
    
    def __init__(self, max_risk_level: str = "high"):
        self.max_risk_level = RiskLevel[max_risk_level.upper()]
        self.confirmation_required_levels = {
            RiskLevel.LOW: False,
            RiskLevel.MEDIUM: False,
            RiskLevel.HIGH: True,
            RiskLevel.CRITICAL: True
        }
        
    def analyze_command(self, command: str) -> Tuple[RiskLevel, Optional[str]]:
        command_lower = command.lower().strip()
        
        for pattern, message, risk_level in self.DANGEROUS_PATTERNS:
            if re.search(pattern, command_lower):
                return risk_level, message
                
        for path in self.CRITICAL_PATHS:
            if re.search(rf"rm\s+(-[rf]+\s+)?{re.escape(path)}(?:\s|$)", command):
                return RiskLevel.CRITICAL, f"Attempting to remove critical path: {path}"
                
        for file in self.CRITICAL_FILES:
            if re.search(rf">\s*{re.escape(file)}", command):
                return RiskLevel.CRITICAL, f"Attempting to overwrite critical file: {file}"
                
        if re.search(r"rm\s+", command_lower):
            if any(path in command for path in self.CRITICAL_PATHS):
                return RiskLevel.HIGH, "Removing files in critical system directory"
                
        if re.search(r"chmod|chown", command_lower):
            if any(path in command for path in self.CRITICAL_PATHS):
                return RiskLevel.HIGH, "Modifying permissions in critical system directory"
                
        return RiskLevel.LOW, None
        
    def check_user_operation(self, operation: str, username: str = "") -> Tuple[RiskLevel, Optional[str]]:
        operation_lower = operation.lower()
        
        critical_users = ["root", "admin", "administrator"]
        if username.lower() in critical_users:
            if "delete" in operation_lower or "remove" in operation_lower:
                return RiskLevel.CRITICAL, f"Attempting to delete critical user: {username}"
            if "modify" in operation_lower or "change" in operation_lower:
                return RiskLevel.HIGH, f"Attempting to modify critical user: {username}"
                
        if "create" in operation_lower or "add" in operation_lower:
            if username.lower() in critical_users:
                return RiskLevel.MEDIUM, f"Creating privileged user: {username}"
                
        return RiskLevel.LOW, None
        
    def requires_confirmation(self, risk_level: RiskLevel) -> bool:
        return self.confirmation_required_levels.get(risk_level, False)
        
    def is_allowed(self, risk_level: RiskLevel) -> bool:
        risk_order = {
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.CRITICAL: 3
        }
        return risk_order.get(risk_level, 0) <= risk_order.get(self.max_risk_level, 2)
        
    def get_safe_alternative(self, command: str, risk_level: RiskLevel) -> Optional[str]:
        if risk_level == RiskLevel.CRITICAL:
            return None
            
        command_lower = command.lower()
        
        if "rm" in command_lower:
            if "--no-preserve-root" in command_lower:
                return command.replace("--no-preserve-root", "").strip()
                
        if "chmod 777" in command_lower:
            match = re.search(r"chmod\s+777\s+(\S+)", command)
            if match:
                path = match.group(1)
                return f"chmod 755 {path}  # More secure alternative to 777"
                
        return None
        
    def generate_warning_message(self, risk_level: RiskLevel, reason: str, command: str) -> str:
        warnings = {
            RiskLevel.MEDIUM: f"⚠️  警告: 此操作可能存在风险。\n原因: {reason}\n命令: {command}\n建议: 请确认后再执行。",
            RiskLevel.HIGH: f"🚨 高风险警告: 此操作具有较高风险！\n原因: {reason}\n命令: {command}\n建议: 请仔细评估后确认是否继续执行。",
            RiskLevel.CRITICAL: f"⛔ 危险操作: 此操作被禁止执行！\n原因: {reason}\n命令: {command}\n说明: 此命令可能对系统造成不可逆的损害，已被安全策略阻止。"
        }
        return warnings.get(risk_level, "")
        
    def sanitize_path(self, path: str) -> str:
        path = path.replace("../", "")
        path = path.replace(";", "")
        path = path.replace("|", "")
        path = path.replace("&", "")
        path = path.replace("$", "")
        return path.strip()
        
    def validate_input(self, user_input: str) -> Tuple[bool, Optional[str]]:
        injection_patterns = [
            r";\s*rm",
            r"\|\s*rm",
            r"`.*`",
            r"\$\(.*\)",
            r"&&\s*rm",
            r"\|\|.*rm",
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, user_input.lower()):
                return False, "Potential command injection detected"
                
        return True, None
