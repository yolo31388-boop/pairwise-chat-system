"""聊天系统 - 带5个bug"""
from dataclasses import dataclass, field

@dataclass
class Message:
    mid: str
    sender: str
    channel: str
    content: str
    timestamp: float  # bug5: 发送者本地时间

class ChatSystem:
    def __init__(self):
        self.messages: list[Message] = []
        self.blocked: dict[str, set] = {}
        self.offline_messages: dict[str, list] = {}
        self.sensitive_words = {"加微信", "外挂"}

    def filter_content(self, content):
        # bug1: 全匹配
        return content not in self.sensitive_words

    def can_speak(self, pid, channel):
        # bug2: 不检查权限
        return True

    def block(self, blocker, blocked):
        self.blocked.setdefault(blocker, set()).add(blocked)
        # bug3: 只屏蔽消息

    def add_offline(self, pid, msg):
        # bug4: 无数量限制
        self.offline_messages.setdefault(pid, []).append(msg)

    def send_message(self, sender, channel, content, timestamp):
        if not self.filter_content(content):
            return False
        msg = Message(f"m{len(self.messages)}", sender, channel, content, timestamp)
        self.messages.append(msg)
        return True
