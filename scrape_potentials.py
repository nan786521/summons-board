"""
補爬潛在效果（開眼）資料
只爬取 abilities.json 中沒有 potentials 的角色
"""

import json
import random
import re
import sys
import time
import os

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from scrape_abilities import fetch_page, parse_detail_page, USER_AGENTS

OUTPUT_FILE = "abilities.json"
BASE_DELAY = 2.5
JITTER = 2.0
BACKOFF_403 = 30
MAX_CONSECUTIVE_403 = 5


def main():
    with open("monsters.json", "r", encoding="utf-8") as f:
        monsters = json.load(f)

    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        abilities = json.load(f)

    # Find characters that have ability data but no potentials
    targets = []
    for m in monsters:
        if not m.get("url"):
            continue
        key = str(m["no"]) if m.get("no") else m["name"]
        ab = abilities.get(key)
        if ab and not ab.get("potentials"):
            targets.append((key, m))

    print(f"需補爬潛在效果: {len(targets)} 個角色")

    success = 0
    fail = 0
    found = 0
    consecutive_403 = 0

    for i, (key, m) in enumerate(targets):
        url = m["url"]
        if not url.startswith("http"):
            url = "https://gamewith.jp" + url

        try:
            print(f"[{i+1}/{len(targets)}] {m['name']} (No.{m.get('no', '?')})...", end=" ", flush=True)
            html = fetch_page(url)
            result = parse_detail_page(html)
            consecutive_403 = 0

            if result.get("potentials"):
                abilities[key]["potentials"] = result["potentials"]
                found += 1
                lvs = [p["level"] for p in result["potentials"]]
                print(f"OK ({len(result['potentials'])} levels: {', '.join(lvs)})")
            else:
                print("(無開眼)")

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

        # Save every 50
        if (success + fail) % 50 == 0 and (success + fail) > 0:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(abilities, f, ensure_ascii=False, indent=2)
            print(f"  --- 已儲存 (找到 {found} 筆開眼) ---")

        delay = BASE_DELAY + random.uniform(0, JITTER)
        time.sleep(delay)

    # Final save
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(abilities, f, ensure_ascii=False, indent=2)

    print(f"\n=== 完成 ===")
    print(f"成功: {success}，失敗: {fail}，找到開眼: {found} 筆")


if __name__ == "__main__":
    main()
