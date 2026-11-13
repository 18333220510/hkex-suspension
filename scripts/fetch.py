#!/usr/bin/env python3
"""从披露易抓取停牌公告，并按固定规则分类；不使用 AI。

用法：
  python3 scripts/fetch.py                         # 抓取香港今天
  python3 scripts/fetch.py --days 5                # 回补香港最近 5 天（含今天）
  python3 scripts/fetch.py 20261020 20261031       # 指定日期范围（YYYYMMDD）
  python3 scripts/fetch.py --reclassify-only        # 仅清理并重分现有数据

只输出两类：
  新增停牌：首次/新发生的停牌、短暂停牌或暂停买卖。
  长期停牌公司进展：继续停牌、停牌进展/季度更新、复牌指引等仍处停牌状态的公告。
实际复牌/恢复买卖公告会被剔除。分类只依据下方公开关键词规则。
"""
import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = "https://www1.hkexnews.hk"
SEARCH_URL = BASE + "/search/titleSearchServlet.do"
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "announcements.json"
HK_TZ = ZoneInfo("Asia/Hong_Kong")

GROUP_NEW = "新增停牌"
GROUP_PROGRESS = "长期停牌公司进展"

# 仍需检索复牌词，才能收录「复牌指引」「复牌进展」等仍处停牌状态的公告；
# 真正恢复买卖的公告会在 classify() 中被剔除。
KEYWORDS = ("停牌", "暫停買賣", "復牌", "恢復買賣")
EXCLUDE_CATEGORY_PREFIXES = ("債券及結構性產品", "債券", "結構性產品")

# 明确表示仍然停牌，优先级最高，避免「复牌进展」被误作实际复牌。
CONTINUED_TERMS = (
    "繼續暫停買賣", "持續暫停買賣", "仍然暫停買賣", "繼續停止買賣",
    "繼續停牌", "持續停牌", "仍然停牌", "維持停牌",
)
# 表示停牌期间进展，而非交易已经恢复。
PROGRESS_TERMS = (
    "復牌指引", "額外復牌指引", "復牌進展", "復牌進度", "復牌之季度",
    "復牌季度", "復牌最新", "恢復買賣進展", "恢復買賣進度",
    "恢復買賣之季度", "停牌進展", "停牌進度", "停牌的最新消息",
    "停牌最新消息", "季度更新", "季度最新情況", "季度最新資料",
)
ACTUAL_RESUMPTION_TERMS = ("恢復買賣", "恢复买卖")

ATTENTION_RULES = (
    ("收购合并", ("收購", "合併", "併購")),
    ("除牌风险", ("除牌", "取消上市", "撤銷上市")),
    ("核数师辞任", ("核數師辭任", "核數師辭職", "更換核數師")),
    ("股权变动", ("股權", "控股股東")),
)


def has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def is_actual_resumption(title: str, category: str) -> bool:
    """识别交易已经恢复；继续停牌声明优先于复牌字样。"""
    text = title + " " + category
    if has_any(text, CONTINUED_TERMS):
        return False
    if has_any(title, ACTUAL_RESUMPTION_TERMS):
        return True
    normalized = re.sub(r"\s+", " ", title.strip())
    if normalized == "復牌" or re.fullmatch(r"交易所通告\s*[-–—]\s*復牌", normalized):
        return True
    # 披露易栏目标为「復牌」而标题没有仍停牌/进展说明时，视为实际复牌。
    return bool(re.search(r"(?:\[|/|&#x2f;)\s*復牌\s*(?:\]|$)", category))


def classify(title: str, category: str) -> tuple[str, str] | None:
    """返回（分组，性质）；实际复牌或无法确认仍停牌时返回 None。

    不按停牌天数推断「长期」，只看公告本身的性质。
    """
    text = title + " " + category
    continued = has_any(text, CONTINUED_TERMS)
    progress = has_any(text, PROGRESS_TERMS)

    if continued:
        nature = "復牌指引" if "復牌指引" in text or "恢復買賣指引" in text else "繼續停牌"
        return GROUP_PROGRESS, nature

    # 「已达成复牌指引及恢复买卖」是实际复牌；明确的继续停牌声明已在上面保留。
    if is_actual_resumption(title, category):
        return None

    if progress:
        nature = "復牌指引" if "復牌指引" in text or "恢復買賣指引" in text else "停牌進展"
        return GROUP_PROGRESS, nature

    # 没有继续/进展字样，且明确出现停牌事项，按新增停牌处理。
    if "暫停買賣" in title:
        return GROUP_NEW, "暫停買賣"
    if "短暫停牌" in text:
        return GROUP_NEW, "短暫停牌"
    if "暫停買賣" in text:
        return GROUP_NEW, "暫停買賣"
    if "停牌" in text:
        return GROUP_NEW, "停牌"

    # 例如只有「有关复牌之公告」而不能确认状态时，宁可不收录，也不猜测。
    return None


def detect_attention(title: str, category: str) -> list[str]:
    text = title + " " + category
    return [label for label, kws in ATTENTION_RULES if has_any(text, kws)]


def request_rows(day: date, keyword: str) -> list[dict]:
    params = {
        "sortDir": "0", "sortByOptions": "DateTime", "category": "0",
        "market": "SEHK", "stockId": "-1", "documentType": "-1",
        "fromDate": day.strftime("%Y%m%d"), "toDate": day.strftime("%Y%m%d"),
        "title": keyword, "searchType": "1",
        "t1code": "-2", "t2Gcode": "-2", "t2code": "-2",
        "rowRange": "100", "lang": "zh",
    }
    url = SEARCH_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            return json.loads(payload["result"]) if payload.get("result") else []
        except (OSError, ValueError, KeyError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"披露易请求失败：{day} / {keyword}") from last_error


def fetch_day(day: date) -> list[dict]:
    items = {}
    for keyword in KEYWORDS:
        for row in request_rows(day, keyword):
            # NEWS_ID 可能重复，必须以披露易文件链接去重。
            link = row.get("FILE_LINK") or ""
            if link:
                items[link] = row
        time.sleep(0.3)

    out = []
    for link, row in items.items():
        category = (row.get("LONG_TEXT") or row.get("SHORT_TEXT") or "").replace("<br/>", " ").strip()
        if any(category.startswith(p) for p in EXCLUDE_CATEGORY_PREFIXES):
            continue
        title = (row.get("TITLE") or "").strip()
        result = classify(title, category)
        if not result:
            if not is_actual_resumption(title, category):
                print(f"警告：无法确认仍处停牌状态，未收录：{day} {title}")
            continue
        group, nature = result
        dt = row.get("DATE_TIME", "")  # 04/11/2026 13:05
        day_text, _, time_text = dt.partition(" ")
        try:
            iso_date = datetime.strptime(day_text, "%d/%m/%Y").date().isoformat()
        except ValueError:
            print(f"警告：公告日期格式异常，未收录：{dt} {title}")
            continue
        out.append({
            "id": link,
            "date": iso_date,
            "time": time_text,
            "stockName": (row.get("STOCK_NAME") or "").replace("<br/>", " / ").strip(),
            "stockCode": (row.get("STOCK_CODE") or "").replace("<br/>", " / ").strip(),
            "title": title,
            "group": group,
            "nature": nature,
            "attention": detect_attention(title, category),
            "category": category,
            "url": BASE + link if link.startswith("/") else link,
        })
    out.sort(key=lambda x: (x["date"], x["time"]))
    return out


def normalize(item: dict) -> dict | None:
    """清理旧复牌字段，并用同一套规则重分全部历史数据。"""
    item = dict(item)
    title = item.get("title") or ""
    category = item.get("category") or ""
    result = classify(title, category)
    if not result:
        return None
    item["group"], item["nature"] = result
    item.pop("eventType", None)
    item["attention"] = detect_attention(title, category)
    keys = ("id", "date", "time", "stockName", "stockCode", "title", "group", "nature", "attention", "category", "url")
    return {key: item.get(key, [] if key == "attention" else "") for key in keys}


def merge(new_items: list[dict]) -> list[dict]:
    existing = []
    if DATA_FILE.exists():
        existing = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    by_id = {}
    for item in existing + new_items:
        normalized = normalize(item)
        if normalized and normalized.get("id"):
            by_id[normalized["id"]] = normalized
    return sorted(by_id.values(), key=lambda x: (x["date"], x["time"]), reverse=True)


def parse_day(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期必须为 YYYYMMDD") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dates", nargs="*", type=parse_day, help="起止日期 YYYYMMDD")
    parser.add_argument("--days", type=int, help="回补最近 N 天（含香港今天）")
    parser.add_argument("--reclassify-only", action="store_true", help="不联网，仅重分现有数据")
    args = parser.parse_args()
    if args.days is not None and args.days < 1:
        parser.error("--days 必须大于 0")
    if args.dates and len(args.dates) != 2:
        parser.error("请提供起始和结束两个日期")
    if args.reclassify_only and (args.dates or args.days):
        parser.error("--reclassify-only 不能与日期参数同时使用")

    all_new = []
    if not args.reclassify_only:
        today = datetime.now(HK_TZ).date()
        if args.dates:
            start, end = args.dates
        else:
            end = today
            start = today - timedelta(days=(args.days or 1) - 1)
        if start > end:
            parser.error("起始日期不能晚于结束日期")
        current = start
        while current <= end:
            rows = fetch_day(current)
            new_count = sum(row["group"] == GROUP_NEW for row in rows)
            print(f"{current}: 保留 {len(rows)} 条（{GROUP_NEW} {new_count} / {GROUP_PROGRESS} {len(rows) - new_count}）")
            all_new.extend(rows)
            current += timedelta(days=1)

    merged = merge(all_new)
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    new_total = sum(item["group"] == GROUP_NEW for item in merged)
    print(f"本次抓取 {len(all_new)} 条；数据共 {len(merged)} 条（{GROUP_NEW} {new_total} / {GROUP_PROGRESS} {len(merged) - new_total}）")


if __name__ == "__main__":
    main()
