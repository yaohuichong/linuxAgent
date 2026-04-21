from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OperationCategory(str, Enum):
    DISK = "disk"
    FILE = "file"
    PROCESS = "process"
    PORT = "port"
    USER = "user"
    NETWORK = "network"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class CommandResult(BaseModel):
    success: bool
    command: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    execution_time: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW
    warning_message: Optional[str] = None


class ParsedIntent(BaseModel):
    original_input: str
    intent: str
    category: OperationCategory
    parameters: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    requires_confirmation: bool = False
    risk_level: RiskLevel = RiskLevel.LOW
    suggested_commands: List[str] = Field(default_factory=list)
    explanation: str = ""


class ConversationMessage(BaseModel):
    role: str
    content: str
    timestamp: float
    intent: Optional[ParsedIntent] = None
    result: Optional[CommandResult] = None


class SystemInfo(BaseModel):
    hostname: str = ""
    os_type: str = ""
    os_version: str = ""
    kernel_version: str = ""
    cpu_cores: int = 0
    memory_total: str = ""
    disk_total: str = ""
    uptime: str = ""
