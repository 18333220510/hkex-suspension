import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import fetch


class ClassificationTests(unittest.TestCase):
    def assertGroup(self, title, category, group, nature=None):
        result = fetch.classify(title, category)
        self.assertIsNotNone(result, title)
        self.assertEqual(group, result[0])
        if nature:
            self.assertEqual(nature, result[1])

    def test_new_suspension(self):
        self.assertGroup("交易所通告 - 停牌", "公告及通告 - [停牌]", fetch.GROUP_NEW, "停牌")
        self.assertGroup("短暫停牌", "公告及通告 - [短暫停牌]", fetch.GROUP_NEW, "短暫停牌")
        self.assertGroup("暫停買賣", "公告及通告 - [短暫停牌]", fetch.GROUP_NEW, "暫停買賣")
        self.assertGroup(
            "(I)延遲刊發年度業績；及(III)暫停買賣",
            "公告及通告 - [內幕消息 &#x2f; 停牌]",
            fetch.GROUP_NEW,
        )

    def test_continued_suspension_is_progress_even_with_resumption_word(self):
        self.assertGroup(
            "(1)復牌指引；(2)有關復牌進展之季度更新；及(3)繼續暫停買賣",
            "公告及通告 - [內幕消息 &#x2f; 停牌]",
            fetch.GROUP_PROGRESS,
            "復牌指引",
        )
        self.assertGroup(
            "季度更新公告及繼續暫停買賣",
            "公告及通告 - [停牌]",
            fetch.GROUP_PROGRESS,
            "繼續停牌",
        )

    def test_resumption_guidance_and_progress_are_not_actual_resumption(self):
        self.assertGroup("額外復牌指引", "監管者發出的公告及消息", fetch.GROUP_PROGRESS, "復牌指引")
        self.assertGroup("復牌進展之季度更新", "公告及通告 - [停牌]", fetch.GROUP_PROGRESS)
        self.assertGroup("獨立調查委員會的組成變更及復牌進度更新", "公告及通告 - [停牌]", fetch.GROUP_PROGRESS)
        self.assertGroup("停牌的最新消息", "公告及通告 - [其他-雜項]", fetch.GROUP_PROGRESS)

    def test_actual_resumption_is_removed(self):
        for title, category in (
            ("交易所通告 - 復牌", "公告及通告 - [復牌]"),
            ("全年業績及恢復買賣", "公告及通告 - [末期業績 &#x2f; 復牌]"),
            ("(1)有關暫停買賣之澄清；及(2)恢復買賣", "公告及通告 - [內幕消息 &#x2f; 復牌]"),
            ("已達成復牌指引及恢復買賣", "公告及通告 - [復牌]"),
        ):
            with self.subTest(title=title):
                self.assertIsNone(fetch.classify(title, category))

    def test_ambiguous_resumption_only_title_is_not_guessed(self):
        self.assertIsNone(fetch.classify("有關復牌之公告", "公告及通告 - [其他-雜項]"))


class DataMaintenanceTests(unittest.TestCase):
    def test_normalize_removes_legacy_resumption_and_reclassifies_progress(self):
        resumed = {"id": "a", "title": "交易所通告 - 復牌", "category": "公告及通告 - [復牌]", "eventType": "復牌"}
        progress = {"id": "b", "title": "額外復牌指引", "category": "監管者發出的公告及消息", "eventType": "復牌"}
        self.assertIsNone(fetch.normalize(resumed))
        normalized = fetch.normalize(progress)
        self.assertEqual(fetch.GROUP_PROGRESS, normalized["group"])
        self.assertNotIn("eventType", normalized)

    def test_merge_deduplicates_by_file_link(self):
        item = {
            "id": "/listedco/example.pdf", "date": "2026-11-01", "time": "09:00",
            "title": "短暫停牌", "category": "公告及通告 - [短暫停牌]",
        }
        with tempfile.TemporaryDirectory() as tmp:
            data_file = Path(tmp) / "announcements.json"
            data_file.write_text(json.dumps([item]), encoding="utf-8")
            with patch.object(fetch, "DATA_FILE", data_file):
                merged = fetch.merge([item])
        self.assertEqual(1, len(merged))

    def test_one_and_five_day_modes_preserve_data_and_drop_resumptions(self):
        old = {
            "id": "/listedco/existing.pdf", "date": "2026-11-01", "time": "09:00",
            "stockName": "示例公司", "stockCode": "00001", "title": "短暫停牌",
            "category": "公告及通告 - [短暫停牌]", "url": "https://www1.hkexnews.hk/listedco/existing.pdf",
        }
        resumed = {
            "id": "/listedco/resumed.pdf", "date": "2026-11-02", "time": "09:00",
            "title": "交易所通告 - 復牌", "category": "公告及通告 - [復牌]",
        }
        fetched_old = dict(old, group=fetch.GROUP_NEW, nature="短暫停牌", attention=[])
        for days in (1, 5):
            with self.subTest(days=days), tempfile.TemporaryDirectory() as tmp:
                data_file = Path(tmp) / "announcements.json"
                data_file.write_text(json.dumps([old, resumed]), encoding="utf-8")
                with patch.object(fetch, "DATA_FILE", data_file), \
                     patch.object(fetch, "fetch_day", return_value=[fetched_old]) as fetch_day, \
                     patch.object(sys, "argv", ["fetch.py", "--days", str(days)]):
                    fetch.main()
                data = json.loads(data_file.read_text(encoding="utf-8"))
                self.assertEqual(days, fetch_day.call_count)
                call_dates = [call.args[0] for call in fetch_day.call_args_list]
                self.assertEqual(call_dates, sorted(call_dates))
                self.assertEqual(days - 1, (call_dates[-1] - call_dates[0]).days)
                self.assertEqual(1, len(data))
                self.assertEqual(old["id"], data[0]["id"])
                self.assertEqual(fetch.GROUP_NEW, data[0]["group"])

    def test_fetch_day_spaces_keyword_requests(self):
        with patch.object(fetch, "request_rows", return_value=[]) as request_rows, \
             patch.object(fetch.time, "sleep") as sleep:
            self.assertEqual([], fetch.fetch_day(fetch.date(2026, 11, 13)))
        self.assertEqual(len(fetch.KEYWORDS), request_rows.call_count)
        self.assertEqual([0.3] * len(fetch.KEYWORDS), [call.args[0] for call in sleep.call_args_list])

    def test_current_json_is_consistent(self):
        data_file = Path(__file__).resolve().parent.parent / "data" / "announcements.json"
        data = json.loads(data_file.read_text(encoding="utf-8"))
        self.assertEqual(len(data), len({item["id"] for item in data}))
        for item in data:
            with self.subTest(item=item["id"]):
                self.assertIn(item["group"], (fetch.GROUP_NEW, fetch.GROUP_PROGRESS))
                self.assertNotIn("eventType", item)
                self.assertEqual((item["group"], item["nature"]), fetch.classify(item["title"], item["category"]))
                self.assertNotRegex(item["category"], r"(?:\[|/|&#x2f;)\s*復牌\s*(?:\]|$)")


if __name__ == "__main__":
    unittest.main()
