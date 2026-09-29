"""聊天系统 - 5个bug已修复"""
import re
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

# bug1: 谐音/变体字映射（键为敏感字，值为可互相替换的字）
_VARIANTS = {
    "微": "微vV薇威徴",
    "信": "信訫",
    "挂": "挂掛卦",
}
# 允许插入在敏感字之间的噪声字符（空格、标点、符号等）
_SEP = r"[\s\-_.·*~,，、/\\|]*"

# bug2: 频道准入规则
CHANNEL_RULES = {
    "world": {"min_level": 10, "vip": False},
    "trade": {"min_level": 5, "vip": False},
    "vip": {"min_level": 1, "vip": True},
    "newbie": {"min_level": 1, "vip": False},
}

OFFLINE_LIMIT = 100          # bug4: 离线消息上限
MUTE_SECONDS = 300           # bug2: 违规自动禁言时长


@dataclass
class Message:
    mid: str
    sender: str
    channel: str
    content: str
    timestamp: float  # 修复bug5: 统一存UTC epoch


class ChatSystem:
    def __init__(self):
        self.messages: list[Message] = []
        self.blocked: dict[str, set] = {}
        self.offline_messages: dict[str, deque] = {}
        self.unread: dict[str, int] = {}
        self.sensitive_words = {"加微信", "外挂"}
        self._patterns = [self._build_pattern(w) for w in self.sensitive_words]
        # bug2: 玩家资料与禁言状态
        self.players: dict[str, dict] = {}
        self.muted_until: dict[str, float] = {}

    # ---------- bug1: 模糊敏感词过滤 ----------
    @staticmethod
    def _build_pattern(word):
        parts = []
        for ch in word:
            variants = _VARIANTS.get(ch, ch)
            parts.append("[" + re.escape(variants) + "]")
        return re.compile(_SEP.join(parts))

    def filter_content(self, content):
        """内容合法返回True，命中敏感词（含谐音/空格拆分/变体）返回False"""
        return not any(p.search(content) for p in self._patterns)

    # ---------- bug2: 频道权限 + 违规禁言 ----------
    def register_player(self, pid, level=1, vip=False):
        self.players[pid] = {"level": level, "vip": vip}

    def is_muted(self, pid):
        until = self.muted_until.get(pid, 0)
        return until > time.time()

    def mute(self, pid, seconds=MUTE_SECONDS):
        self.muted_until[pid] = time.time() + seconds

    def can_speak(self, pid, channel):
        if self.is_muted(pid):
            return False
        rule = CHANNEL_RULES.get(channel)
        if rule is None:
            return False
        info = self.players.get(pid, {"level": 1, "vip": False})
        if info["level"] < rule["min_level"]:
            return False
        if rule["vip"] and not info["vip"]:
            return False
        return True

    # ---------- bug3: 屏蔽（消息 + @ + 组队邀请 + 私聊）----------
    def block(self, blocker, blocked):
        self.blocked.setdefault(blocker, set()).add(blocked)

    def is_blocked(self, receiver, sender):
        """receiver 是否屏蔽了 sender"""
        return sender in self.blocked.get(receiver, set())

    def send_private(self, sender, receiver, content, timestamp=None):
        if self.is_blocked(receiver, sender):
            return False
        if not self.filter_content(content):
            return False
        msg = Message(f"m{len(self.messages)}", sender, "private", content,
                      self._to_utc(timestamp))
        self.messages.append(msg)
        return True

    def invite_team(self, inviter, invitee):
        if self.is_blocked(invitee, inviter):
            return False
        return True

    def get_mentions(self, msg):
        """消息中@到、且未屏蔽发送者的玩家"""
        return [name for name in re.findall(r"@(\w+)", msg.content)
                if not self.is_blocked(name, msg.sender)]

    # ---------- bug4: 离线消息上限 + 未读计数 ----------
    def add_offline(self, pid, msg):
        q = self.offline_messages.setdefault(pid, deque(maxlen=OFFLINE_LIMIT))
        q.append(msg)  # 超出上限自动丢弃最早的
        self.unread[pid] = len(q)

    def unread_count(self, pid):
        return self.unread.get(pid, 0)

    def pop_offline(self, pid):
        """上线取走离线消息并清零未读"""
        msgs = list(self.offline_messages.get(pid, ()))
        self.unread[pid] = 0
        return msgs

    # ---------- bug5: UTC 存储，按接收者时区显示 ----------
    @staticmethod
    def _to_utc(timestamp, sender_offset=0.0):
        """发送者本地epoch + 时区偏移(小时) -> UTC epoch"""
        if timestamp is None:
            return time.time()
        return timestamp - sender_offset * 3600

    @staticmethod
    def format_timestamp(msg, receiver_offset=0.0):
        """把UTC时间戳按接收者时区(偏移小时)格式化显示"""
        tz = timezone(timedelta(hours=receiver_offset))
        return datetime.fromtimestamp(msg.timestamp, tz).strftime("%Y-%m-%d %H:%M:%S")

    # ---------- 发送 ----------
    def send_message(self, sender, channel, content, timestamp=None,
                     sender_offset=0.0):
        if not self.can_speak(sender, channel):
            self.mute(sender)  # 违规发言自动禁言
            return False
        if not self.filter_content(content):
            return False
        msg = Message(f"m{len(self.messages)}", sender, channel, content,
                      self._to_utc(timestamp, sender_offset))
        self.messages.append(msg)
        return True
