"""聊天测试"""
import pytest, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.engine import ChatSystem, Message

class TestFilter:
    def test_fuzzy_filter(self):
        cs = ChatSystem()
        assert not cs.filter_content("加v信"), "谐音变体未过滤"
        assert not cs.filter_content("加 微 信"), "空格拆分未过滤"

class TestOffline:
    def test_offline_limit(self):
        cs = ChatSystem()
        for i in range(200):
            cs.add_offline("p1", f"msg{i}")
        assert len(cs.offline_messages["p1"]) <= 100, "离线消息无上限"
