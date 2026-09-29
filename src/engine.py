"""聊天系统 - 修复版"""
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

OFFLINE_LIMIT = 100
MUTE_DURATION = timedelta(minutes=10)

# 谐音/变体字映射：归一化时统一替换成规范字
_VARIANTS = {
    "微": "微", "v": "微", "w": "微", "薇": "微", "威": "微", "嶶": "微",
    "信": "信", "訫": "信", "伈": "信", "忄言": "信",
    "加": "加", "茄": "加", "枷": "加",
    "外": "外", "歪": "外",
    "挂": "挂", "掛": "挂", "卦": "挂",
}
_SEPARATORS = re.compile(r"[\s\-_*.,，。、/\\|~·!！?？]+")
_PINYIN = {"jia": "加", "wei": "微", "xin": "信", "wai": "外", "gua": "挂"}

# 频道准入规则
CHANNEL_RULES = {
    "newbie": {"min_level": 0},
    "trade": {"min_level": 5},
    "world": {"min_level": 10},
    "vip": {"min_level": 0, "vip": True},
    "guild": {"min_level": 0, "guild": True},
}


def _normalize(text):
    """归一化：全角转半角、去分隔符、谐音/变体字替换"""
    text = unicodedata.normalize("NFKC", text).lower()
    text = _SEPARATORS.sub("", text)
    for pinyin, char in _PINYIN.items():
        text = text.replace(pinyin, char)
    return "".join(_VARIANTS.get(ch, ch) for ch in text)


@dataclass
class Message:
    mid: str
    sender: str
    channel: str
    content: str
    timestamp: datetime  # 统一 UTC 存储

    def __post_init__(self):
        if isinstance(self.timestamp, (int, float)):
            # 兼容 epoch 秒输入，epoch 与时区无关，直接视为 UTC
            self.timestamp = datetime.fromtimestamp(self.timestamp, tz=timezone.utc)
        elif self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)

    def display_time(self, tz_offset_hours=0):
        """按接收者时区转换显示"""
        tz = timezone(timedelta(hours=tz_offset_hours))
        return self.timestamp.astimezone(tz)


@dataclass
class Player:
    pid: str
    level: int = 1
    vip: bool = False
    guild: bool = False
    tz_offset: int = 0  # 玩家所在时区（小时）
    muted_until: datetime | None = None
    violations: int = 0


class ChatSystem:
    def __init__(self):
        self.messages: list[Message] = []
        self.blocked: dict[str, set] = {}
        self.offline_messages: dict[str, list] = {}
        self.players: dict[str, Player] = {}
        self.sensitive_words = {"加微信", "外挂"}
        # 允许敏感字的字符之间插入少量干扰字符（如"加我威信"）
        self._word_patterns = [
            re.compile(".{0,2}?".join(map(re.escape, _normalize(w))))
            for w in self.sensitive_words
        ]

    # ---- bug1: 模糊敏感词过滤 ----
    def filter_content(self, content):
        normalized = _normalize(content)
        return not any(p.search(normalized) for p in self._word_patterns)

    # ---- bug2: 频道权限检查 + 违规自动禁言 ----
    def register_player(self, pid, level=1, vip=False, guild=False, tz_offset=0):
        self.players[pid] = Player(pid, level, vip, guild, tz_offset)

    def _get_player(self, pid):
        return self.players.setdefault(pid, Player(pid))

    def _is_muted(self, player, now=None):
        if player.muted_until is None:
            return False
        now = now or datetime.now(timezone.utc)
        if now >= player.muted_until:
            player.muted_until = None
            return False
        return True

    def can_speak(self, pid, channel):
        player = self._get_player(pid)
        if self._is_muted(player):
            return False
        rule = CHANNEL_RULES.get(channel, {"min_level": 0})
        if player.level < rule.get("min_level", 0):
            return False
        if rule.get("vip") and not player.vip:
            return False
        if rule.get("guild") and not player.guild:
            return False
        return True

    def _punish(self, pid):
        player = self._get_player(pid)
        player.violations += 1
        player.muted_until = datetime.now(timezone.utc) + MUTE_DURATION

    # ---- bug3: 屏蔽同时生效于 @、组队邀请、私聊 ----
    def block(self, blocker, blocked):
        self.blocked.setdefault(blocker, set()).add(blocked)

    def is_blocked(self, blocker, blocked):
        return blocked in self.blocked.get(blocker, set())

    def can_mention(self, sender, target):
        return not self.is_blocked(target, sender)

    def can_invite_team(self, sender, target):
        return not self.is_blocked(target, sender)

    def can_send_private(self, sender, target):
        return not self.is_blocked(target, sender)

    def invite_team(self, sender, target):
        return self.can_invite_team(sender, target)

    def send_private(self, sender, target, content):
        if not self.can_send_private(sender, target):
            return False
        if not self.filter_content(content):
            return False
        msg = Message(f"m{len(self.messages)}", sender, f"pm:{target}",
                      content, datetime.now(timezone.utc))
        self.messages.append(msg)
        return True

    # ---- bug4: 离线消息上限 + 未读计数 ----
    def add_offline(self, pid, msg):
        queue = self.offline_messages.setdefault(pid, [])
        queue.append(msg)
        if len(queue) > OFFLINE_LIMIT:
            del queue[:len(queue) - OFFLINE_LIMIT]  # 丢弃最早的

    def unread_count(self, pid):
        return len(self.offline_messages.get(pid, []))

    # ---- bug5: UTC 存储 + 发送入口整合 ----
    def send_message(self, sender, channel, content, timestamp=None):
        if not self.can_speak(sender, channel):
            self._punish(sender)  # 违规发言自动禁言
            return False
        if not self.filter_content(content):
            self._punish(sender)
            return False
        # 被屏蔽者的 @ 不生效
        for target in re.findall(r"@(\w+)", content):
            if not self.can_mention(sender, target):
                return False
        ts = timestamp if timestamp is not None else datetime.now(timezone.utc)
        msg = Message(f"m{len(self.messages)}", sender, channel, content, ts)
        self.messages.append(msg)
        return True

    def display_message_time(self, msg, receiver):
        """按接收者时区显示消息时间"""
        player = self._get_player(receiver)
        return msg.display_time(player.tz_offset)
