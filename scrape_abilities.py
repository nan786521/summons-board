"""
サモンズボード角色能力資料爬蟲
從 GameWith 個別角色頁面抓取：HP、ATK、隊長技能、主動技能、TP技能、能力、潛在效果
支援斷點續爬（已爬過的會跳過）
"""

import json
import random
import re
import sys
import time
import urllib.request
import os

sys.stdout.reconfigure(encoding="utf-8")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

OUTPUT_FILE = "abilities.json"
BASE_DELAY = 2.0      # 基本延遲秒數
JITTER = 1.5          # 隨機抖動範圍
BACKOFF_403 = 30      # 遇到 403 時等待秒數
MAX_CONSECUTIVE_403 = 5  # 連續 403 幾次後暫停


def fetch_page(url):
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Referer": "https://gamewith.jp/summonsboard/",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
        # 處理 gzip
        if resp.headers.get("Content-Encoding") == "gzip":
            import gzip
            data = gzip.decompress(data)
        return data.decode("utf-8")


def clean_html(text):
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&nbsp;", " ").replace("&quot;", '"').replace("&times;", "×")
    return text.strip()


def extract_skill_table(html, heading):
    """
    GameWith 格式: <h3>heading</h3><table><tr><th>技能名</th></tr><tr><td>效果</td></tr></table>
    """
    pattern = re.compile(
        r"<h3>" + re.escape(heading) + r"</h3>\s*<table>(.*?)</table>",
        re.DOTALL
    )
    m = pattern.search(html)
    if not m:
        return None, None
    table = m.group(1)
    th = re.search(r"<th[^>]*>(.*?)</th>", table, re.DOTALL)
    td = re.search(r"<td[^>]*>(.*?)</td>", table, re.DOTALL)
    name = clean_html(th.group(1)) if th else ""
    effect = clean_html(td.group(1)) if td else ""
    return name, effect


def parse_detail_page(html):
    result = {}

    # === HP / ATK / ソウル枠 ===
    # HTML: <th>初期ソウル枠</th></tr><tr><td>48000</td><td>225×3(4)</td><td>4枠</td>
    stats_text = html.replace("&times;", "×")
    stats_match = re.search(
        r"初期ソウル枠</th>\s*</tr>\s*<tr>\s*<td>([\d,]+)</td>\s*<td>([^<]+)</td>\s*<td>(\d+)枠",
        stats_text
    )
    if stats_match:
        result["hp"] = int(stats_match.group(1).replace(",", ""))
        result["atk"] = stats_match.group(2).strip()
        result["soul_slots"] = int(stats_match.group(3))

    # === アクティブスキル ===
    as_name, as_effect = extract_skill_table(html, "アクティブスキル")
    if as_name or as_effect:
        skill = {"name": as_name, "effect": as_effect}
        # 技能回合
        turn_match = re.search(r"スキルターン\s*([\d]+ターン\s*→\s*[\d]+ターン)", as_effect)
        if turn_match:
            skill["turn"] = turn_match.group(1)
            skill["effect"] = as_effect[:as_effect.find("スキルターン")].strip()
        result["active_skill"] = skill

    # === TPスキル ===
    tp_name, tp_effect = extract_skill_table(html, "TPスキル")
    if tp_name or tp_effect:
        skill = {"name": tp_name, "effect": tp_effect}
        # TP cost from name, e.g. "最期の収穫(20TP)"
        tp_cost_match = re.search(r"\((\d+)TP\)", tp_name)
        if tp_cost_match:
            skill["tp_cost"] = int(tp_cost_match.group(1))
            skill["name"] = re.sub(r"\(\d+TP\)", "", tp_name).strip()
        result["tp_skill"] = skill

    # === リーダースキル ===
    ls_name, ls_effect = extract_skill_table(html, "リーダースキル")
    if ls_name or ls_effect:
        result["leader_skill"] = {"name": ls_name, "effect": ls_effect}

    # === 能力 (Abilities) ===
    # 格式: 基本情報...能力能力効果{name}{effect}...
    ability_section = re.search(
        r"<h3>能力</h3>\s*<table>(.*?)</table>",
        html, re.DOTALL
    )
    if not ability_section:
        # 有時能力在基本情報表格裡
        ability_section = re.search(
            r"能力能力効果(.*?)(?:</table>|▶)", html, re.DOTALL
        )
    if ability_section:
        ab_html = ability_section.group(1) if ability_section else ""
        abilities = []
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", ab_html, re.DOTALL)
        for row in rows:
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
            if len(cells) >= 2:
                name = clean_html(cells[0])
                effect = clean_html(cells[1])
                if name and "能力" not in name and "効果" not in name:
                    abilities.append({"name": name, "effect": effect})
        if abilities:
            result["abilities"] = abilities

    # === 潛在效果 ===
    pot_match = re.search(
        r"潜在効果(初期.*?)(?:▶|<h3>.*?入手|<h3>.*?評価)",
        html, re.DOTALL
    )
    if pot_match:
        pot_text = pot_match.group(1)
        potentials = []
        # 格式: 潜在Lv1【効果A】...【効果B】...
        for lv_match in re.finditer(
            r"(初期|潜在Lv\d+)(.*?)(?=初期|潜在Lv\d+|$)",
            pot_text, re.DOTALL
        ):
            level = clean_html(lv_match.group(1))
            content = clean_html(lv_match.group(2))
            if content:
                potentials.append({"level": level, "effect": content})
        if potentials:
            result["potentials"] = potentials

    return result


def load_existing():
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_data(data):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    with open("monsters.json", "r", encoding="utf-8") as f:
        monsters = json.load(f)

    targets = [m for m in monsters if m.get("url")]
    print(f"共 {len(targets)} 個角色有詳細頁面 URL")

    abilities = load_existing()
    already = len(abilities)
    print(f"已爬取: {already} 個，剩餘: {len(targets) - already} 個")

    success = 0
    fail = 0
    consecutive_403 = 0

    for i, m in enumerate(targets):
        key = str(m["no"]) if m.get("no") else m["name"]

        if key in abilities:
            continue

        url = m["url"]
        if not url.startswith("http"):
            url = "https://gamewith.jp" + url

        try:
            total_done = already + success + fail + 1
            print(f"[{total_done}/{len(targets)}] {m['name']} (No.{m.get('no', '?')})...", end=" ", flush=True)
            html = fetch_page(url)
            info = parse_detail_page(html)
            consecutive_403 = 0  # 成功就重置

            if info:
                info["name"] = m["name"]
                abilities[key] = info
                success += 1
                fields = [k for k in info if k != "name"]
                print(f"OK ({', '.join(fields)})")
            else:
                print("(空)")
                abilities[key] = {"name": m["name"]}
                success += 1

        except urllib.error.HTTPError as e:
            if e.code == 403:
                consecutive_403 += 1
                print(f"403 (連續 {consecutive_403} 次)")
                if consecutive_403 >= MAX_CONSECUTIVE_403:
                    save_data(abilities)
                    wait = BACKOFF_403 * consecutive_403
                    print(f"  === 連續 {consecutive_403} 次 403，暫停 {wait} 秒 ===")
                    time.sleep(wait)
                    consecutive_403 = 0
                else:
                    time.sleep(BACKOFF_403)
                fail += 1
                continue
            else:
                fail += 1
                print(f"HTTP {e.code}")
        except Exception as e:
            fail += 1
            print(f"FAIL: {e}")

        # 每 50 筆存檔
        if (success + fail) % 50 == 0 and (success + fail) > 0:
            save_data(abilities)
            print(f"  --- 已儲存 ({len(abilities)} 筆) ---")

        # 隨機延遲
        delay = BASE_DELAY + random.uniform(0, JITTER)
        time.sleep(delay)

    save_data(abilities)
    print(f"\n=== 完成 ===")
    print(f"成功: {success}，失敗: {fail}，總計: {len(abilities)} 筆")
    print(f"已儲存至 {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
