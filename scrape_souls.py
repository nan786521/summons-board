"""
補爬推薦ソウル裝備資料
只爬取 abilities.json 中沒有 recommended_souls 的角色
"""

import json
import random
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from scrape_abilities import fetch_page, clean_html

OUTPUT_FILE = "abilities.json"
BASE_DELAY = 2.5
JITTER = 2.0
BACKOFF_403 = 30
MAX_CONSECUTIVE_403 = 5


def parse_souls(html):
    """Extract recommended souls from page HTML."""
    match = re.search(
        r"<h3>おすすめソウル</h3>(.*?)(?:▶|サモンズボード攻略)",
        html, re.DOTALL
    )
    if not match:
        return None
    section = match.group(1)
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", section, re.DOTALL)
    souls = []
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(cells) >= 2:
            name = clean_html(cells[0]).strip()
            effect = clean_html(cells[1]).strip()
            if name and "ソウル名" not in name:
                souls.append({"name": name, "effect": effect})
    return souls if souls else None


def main():
    with open("monsters.json", "r", encoding="utf-8") as f:
        monsters = json.load(f)

    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        abilities = json.load(f)

    targets = []
    for m in monsters:
        if not m.get("url"):
            continue
        key = str(m["no"]) if m.get("no") else m["name"]
        ab = abilities.get(key)
        if ab and not ab.get("recommended_souls"):
            targets.append((key, m))

    print(f"需補爬推薦ソウル: {len(targets)} 個角色")

    success = 0
    fail = 0
    found = 0
    consecutive_403 = 0

    for i, (key, m) in enumerate(targets):
        url = m["url"]
        if not url.startswith("http"):
            url = "https://gamewith.jp" + url

        try:
            print(f"[{i+1}/{len(targets)}] {m['name']}...", end=" ", flush=True)
            html = fetch_page(url)
            consecutive_403 = 0

            souls = parse_souls(html)
            if souls:
                abilities[key]["recommended_souls"] = souls
                found += 1
                names = [s["name"] for s in souls[:3]]
                print(f"OK ({len(souls)}個: {', '.join(names)})")
            else:
                print("(無)")

            success += 1

        except Exception as e:
            err_str = str(e)
            if "403" in err_str:
                consecutive_403 += 1
                print(f"403 (連續 {consecutive_403} 次)")
                if consecutive_403 >= MAX_CONSECUTIVE_403:
                    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                        json.dump(abilities, f, ensure_ascii=False, indent=2)
                    wait = BACKOFF_403 * consecutive_403
                    print(f"  === 暫停 {wait} 秒 ===")
                    time.sleep(wait)
                    consecutive_403 = 0
                else:
                    time.sleep(BACKOFF_403)
            else:
                print(f"FAIL: {e}")
            fail += 1

        if (success + fail) % 50 == 0 and (success + fail) > 0:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(abilities, f, ensure_ascii=False, indent=2)
            print(f"  --- 已儲存 (找到 {found} 筆推薦ソウル) ---")

        delay = BASE_DELAY + random.uniform(0, JITTER)
        time.sleep(delay)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(abilities, f, ensure_ascii=False, indent=2)

    print(f"\n=== 完成 ===")
    print(f"成功: {success}，失敗: {fail}，找到推薦ソウル: {found} 筆")


if __name__ == "__main__":
    main()
