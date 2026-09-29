"""新增特性的回归测试（不改动原有测试）"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.engine import ChatSystem, Message

class TestChannelPerm:
    def test_level_gate_and_automute(self):
        cs = ChatSystem()
        cs.register_player("newbie", level=1)
        assert not cs.can_speak("newbie", "world")      # 等级不足
        assert not cs.send_message("newbie", "world", "广告")
        assert cs.is_muted("newbie")                    # 违规自动禁言
        cs.register_player("old", level=30)
        assert cs.can_speak("old", "world")

    def test_vip_channel(self):
        cs = ChatSystem()
        cs.register_player("norm", level=50, vip=False)
        cs.register_player("vip", level=1, vip=True)
        assert not cs.can_speak("norm", "vip")
        assert cs.can_speak("vip", "vip")

class TestBlock:
    def test_block_covers_all(self):
        cs = ChatSystem()
        cs.block("a", "b")
        assert not cs.send_private("b", "a", "hi")      # 私聊被屏蔽
        assert not cs.invite_team("b", "a")             # 组队邀请被屏蔽
        cs.register_player("b", level=30)
        cs.send_message("b", "world", "hello @a")
        assert cs.get_mentions(cs.messages[-1]) == []   # @被屏蔽

class TestTimestamp:
    def test_utc_storage_and_display(self):
        cs = ChatSystem()
        cs.register_player("p", level=30)
        # 发送者在 UTC+8，本地 epoch 对应 UTC 12:00
        local_epoch = 1_700_000_000 + 8 * 3600
        cs.send_message("p", "world", "hi", local_epoch, sender_offset=8)
        msg = cs.messages[-1]
        assert msg.timestamp == 1_700_000_000           # 存的是UTC
        assert cs.format_timestamp(msg, 8) == "2023-11-15 06:13:20"
        assert cs.format_timestamp(msg, 0) != cs.format_timestamp(msg, 8)

class TestOfflineExtra:
    def test_drops_oldest_and_unread(self):
        cs = ChatSystem()
        for i in range(150):
            cs.add_offline("p1", f"msg{i}")
        msgs = cs.pop_offline("p1")
        assert msgs[0] == "msg50"                       # 最早的被丢弃
        assert cs.unread_count("p1") == 0               # 读后清零
