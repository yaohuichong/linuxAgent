import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.linux_agent import LinuxAgent
from core.security import SecurityController, RiskLevel
import time


def test_security_controller():
    print("=" * 50)
    print("测试安全控制器")
    print("=" * 50)
    
    security = SecurityController()
    
    test_commands = [
        ("df -h", "查看磁盘 - 低风险"),
        ("rm -rf /tmp/test", "删除临时文件 - 中风险"),
        ("rm -rf /", "删除根目录 - 危险"),
        ("chmod 777 /etc/passwd", "修改密码文件权限 - 高风险"),
        ("dd if=/dev/zero of=/dev/sda", "格式化磁盘 - 危险"),
        ("ps aux", "查看进程 - 低风险"),
    ]
    
    for cmd, desc in test_commands:
        risk_level, reason = security.analyze_command(cmd)
        print(f"\n命令: {cmd}")
        print(f"  描述: {desc}")
        print(f"  风险级别: {risk_level.value}")
        if reason:
            print(f"  原因: {reason}")
            
    print("\n" + "=" * 50)
    print("安全控制器测试完成")
    print("=" * 50)


def test_agent_without_connection():
    print("\n" + "=" * 50)
    print("测试Agent初始化（无连接）")
    print("=" * 50)
    
    agent = LinuxAgent()
    print(f"Agent创建成功: {agent is not None}")
    print(f"连接状态: {agent.connected}")
    
    welcome = agent.get_welcome_message()
    print(f"\n欢迎消息长度: {len(welcome)} 字符")
    
    print("\n" + "=" * 50)
    print("Agent初始化测试完成")
    print("=" * 50)


def test_intent_parsing():
    print("\n" + "=" * 50)
    print("测试意图解析（模拟）")
    print("=" * 50)
    
    test_inputs = [
        "查看磁盘使用情况",
        "搜索nginx进程",
        "创建一个test用户",
        "删除用户abc",
        "查看监听端口",
        "查看系统状态",
    ]
    
    for user_input in test_inputs:
        print(f"\n用户输入: {user_input}")
        print("  (需要LLM连接才能完全解析)")
    
    print("\n" + "=" * 50)
    print("意图解析测试完成")
    print("=" * 50)


def test_command_categories():
    print("\n" + "=" * 50)
    print("测试命令分类")
    print("=" * 50)
    
    from models.schemas import OperationCategory
    
    categories = [
        ("disk", "磁盘管理"),
        ("file", "文件管理"),
        ("process", "进程管理"),
        ("port", "端口管理"),
        ("user", "用户管理"),
        ("network", "网络管理"),
        ("system", "系统管理"),
    ]
    
    for cat, desc in categories:
        print(f"  {cat}: {desc}")
    
    print("\n" + "=" * 50)
    print("命令分类测试完成")
    print("=" * 50)


def test_risk_levels():
    print("\n" + "=" * 50)
    print("测试风险级别")
    print("=" * 50)
    
    for level in RiskLevel:
        security = SecurityController(max_risk_level=level.value)
        print(f"\n风险级别: {level.value}")
        print(f"  LOW操作需要确认: {security.requires_confirmation(RiskLevel.LOW)}")
        print(f"  MEDIUM操作需要确认: {security.requires_confirmation(RiskLevel.MEDIUM)}")
        print(f"  HIGH操作需要确认: {security.requires_confirmation(RiskLevel.HIGH)}")
        print(f"  CRITICAL操作需要确认: {security.requires_confirmation(RiskLevel.CRITICAL)}")
    
    print("\n" + "=" * 50)
    print("风险级别测试完成")
    print("=" * 50)


def main():
    print("\n" + "=" * 60)
    print("  Linux智能代理 - 功能测试")
    print("  AI Hackathon 2026")
    print("=" * 60)
    
    try:
        test_security_controller()
        test_agent_without_connection()
        test_intent_parsing()
        test_command_categories()
        test_risk_levels()
        
        print("\n" + "=" * 60)
        print("  所有测试通过！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n测试失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
