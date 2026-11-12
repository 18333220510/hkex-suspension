#!/usr/bin/env python3
"""从披露易（HKEXnews）标题搜寻抓取每日「停牌 / 复牌」公告。

用法:
  python3 scripts/fetch.py                # 抓最近 1 天（今天）并合并进 data/announcements.json
  python3 scripts/fetch.py 20261020 20261104   # 抓指定日期范围（含首尾，YYYYMMDD）

数据与页面分离：本脚本只维护 data/announcements.json，页面代码无需改动。

数据字段:
  eventType  事件类型：停牌 / 复牌
  nature     性质细分（停牌 / 短暫停牌 / 暫停買賣 / 復牌 / 恢復買賣）
  attention  重点关注标签列表，可能包含:
             收购合并  （涉及收购 / 合并守则、全面要约）
             除牌风险  （长期停牌、上市规则除牌条款）
             核数师辞任（核数师辞任 / 更换）
             股权变动  （大股东 / 控股股东股权变动）
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

BASE = "https://www1.hkexnews.hk"
SEARCH_URL = BASE + "/search/titleSearchServlet.do"
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "announcements.json"

# 标题关键词（披露易为繁体）：停牌 + 复牌两组
KEYWORDS_SUSPENSION = ["停牌", "暫停買賣"]
KEYWORDS_RESUMPTION = ["復牌", "恢復買賣"]

# 只保留主板/创业板股票公告，排除结构性产品（牛熊证/权证）与债券的例行停牌
EXCLUDE_CATEGORY_PREFIXES = ("債券及結構性產品", "債券", "結構性產品")

# 重点关注标签规则：命中任一关键词即打标
ATTENTION_RULES = [
    ("收购合并", ["收購", "合併", "併購"]),
    ("除牌风险", ["除牌", "取消上市", "撤銷上市"]),
    ("核数师辞任", ["核數師辭任", "核數師辭職", "更換核數師"]),
    ("股权变动", ["股權", "控股股東"]),
]


def detect_attention(title: str, category: str) -> list[str]:
    text = title + " " + category
    return [label for label, kws in ATTENTION_RULES if any(k in text for k in kws)]


def fetch_day(day: date) -> list[dict]:
    items = {}
    groups = [(KEYWORDS_SUSPENSION, "停牌"), (KEYWORDS_RESUMPTION, "復牌")]
    for kws, _ in groups:
        for kw in kws:
            params = {
                "sortDir": "0", "sortByOptions": "DateTime", "category": "0",
                "market": "SEHK", "stockId": "-1", "documentType": "-1",
                "fromDate": day.strftime("%Y%m%d"), "toDate": day.strftime("%Y%m%d"),
                "title": kw, "searchType": "1",
                "t1code": "-2", "t2Gcode": "-2", "t2code": "-2",
                "rowRange": "100", "lang": "zh",
            }
            url = SEARCH_URL + "?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            rows = json.loads(payload["result"]) if payload.get("result") else []
            for r in rows:
                key = r.get("FILE_LINK") or r.get("NEWS_ID")
                if key:
                    items[key] = r
            time.sleep(0.5)

    out = []
    for r in items.values():
        cat = (r.get("LONG_TEXT") or r.get("SHORT_TEXT") or "").replace("<br/>", " ")
        if any(cat.startswith(p) for p in EXCLUDE_CATEGORY_PREFIXES):
            continue
        link = r.get("FILE_LINK") or ""
        dt = r.get("DATE_TIME", "")  # "04/11/2026 13:05"
        d, _, tm = dt.partition(" ")
        iso_date = ""
        if d:
            dd, mm, yyyy = d.split("/")
            iso_date = f"{yyyy}-{mm}-{dd}"
        title = (r.get("TITLE") or "").strip()
        text = title + " " + cat
        # 事件类型：标题/类别含复牌关键词则记为复牌，否则停牌
        if any(k in text for k in KEYWORDS_RESUMPTION):
            event_type = "復牌"
        else:
            event_type = "停牌"
        # 性质细分
        nature = "停牌"
        for key in ("短暫停牌", "暫停買賣", "停牌", "恢復買賣", "復牌"):
            if key in title or key in cat:
                nature = key
                break
        out.append({
            "id": link or r.get("NEWS_ID", ""),
            "date": iso_date,
            "time": tm,
            "stockName": (r.get("STOCK_NAME") or "").replace("<br/>", " / ").strip(),
            "stockCode": (r.get("STOCK_CODE") or "").replace("<br/>", " / ").strip(),
            "title": title,
            "eventType": event_type,
            "nature": nature,
            "attention": detect_attention(title, cat),
            "category": cat.strip(),
            "url": BASE + link if link.startswith("/") else link,
        })
    out.sort(key=lambda x: (x["date"], x["time"]))
    return out


def normalize(e: dict) -> dict:
    """为历史数据补齐 eventType / attention 字段。"""
    text = (e.get("title") or "") + " " + (e.get("category") or "")
    if not e.get("eventType"):
        e["eventType"] = "復牌" if any(k in text for k in KEYWORDS_RESUMPTION) else "停牌"
    if "attention" not in e:
        e["attention"] = detect_attention(e.get("title") or "", e.get("category") or "")
    return e


def merge(new_items: list[dict]) -> list[dict]:
    existing = []
    if DATA_FILE.exists():
        existing = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    by_id = {e["id"]: normalize(e) for e in existing}
    for e in new_items:
        by_id[e["id"]] = e
    merged = sorted(by_id.values(), key=lambda x: (x["date"], x["time"]), reverse=True)
    return merged


def main():
    if len(sys.argv) == 3:
        d0 = date(int(sys.argv[1][:4]), int(sys.argv[1][4:6]), int(sys.argv[1][6:]))
        d1 = date(int(sys.argv[2][:4]), int(sys.argv[2][4:6]), int(sys.argv[2][6:]))
    else:
        d0 = d1 = date.today()

    all_new = []
    d = d0
    while d <= d1:
        rows = fetch_day(d)
        suspended = sum(1 for r in rows if r["eventType"] == "停牌")
        resumed = len(rows) - suspended
        print(f"{d}: {len(rows)} 条（停牌 {suspended} / 复牌 {resumed}）")
        all_new.extend(rows)
        d += timedelta(days=1)

    merged = merge(all_new)
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"共 {len(all_new)} 条新抓取，合并后 data/announcements.json 共 {len(merged)} 条")


if __name__ == "__main__":
    main()
