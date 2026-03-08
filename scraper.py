"""
サモンズボード全角色資料爬蟲
從 GameWith 抓取角色評價一覽（含圖示、屬性、稀有度、技能標籤），輸出 JSON 並嵌入 HTML
"""

import json
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

ELEMENT_MAP = {
    "fir": "火",
    "wat": "水",
    "mok": "木",
    "light": "光",
    "dark": "闇",
}

# 需要排除的非技能 class（屬性、稀有度、類型等已另外處理）
SKIP_CLASSES = {
    "fir", "wat", "mok", "light", "dark",
    "rare4", "rare5", "rare6", "rare7",
    "atk", "hp", "bal",
    "firels", "waterls", "leafls", "lightls", "darkls",
    "kouls", "hpls", "barals", "atkls", "skillls", "assils", "couls", "defls",
    "allls",
}


def fetch_page(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def extract_tag_mappings(html):
    """從篩選區域提取 class -> 標籤名稱的映射"""
    mappings = {}
    pattern = r'<input\s+type="checkbox"[^>]*id="([^"]+)"[^>]*><label\s+for="\1">([^<]+)</label>'
    for m in re.finditer(pattern, html):
        tag_id = m.group(1)
        label = m.group(2)
        if tag_id not in SKIP_CLASSES:
            mappings[tag_id] = label
    return mappings


def scrape_gamewith():
    url = "https://gamewith.jp/summonsboard/article/show/89035"
    print(f"正在抓取: {url}")
    html = fetch_page(url)
    print(f"頁面大小: {len(html):,} bytes")

    # 提取標籤映射
    tag_map = extract_tag_mappings(html)
    print(f"標籤映射: {len(tag_map)} 個")

    # 解析每個角色
    row_pattern = re.compile(
        r'<tr\s+class="w-idb-element\s+([^"]*)"[^>]*'
        r'data-col3="([^"]*)"[^>]*'
        r'data-col4="([^"]*)"[^>]*>'
        r'(.*?)</tr>',
        re.DOTALL
    )

    link_pattern = re.compile(r"href='([^']+)'")
    icon_pattern = re.compile(r"data-original='([^']+)'")
    name_pattern = re.compile(r"(?:</noscript>|</img>)([^<]+)</a>")
    number_pattern = re.compile(r"i_(\d+)\.")
    type_pattern = re.compile(r"<td>(.*?)</td>", re.DOTALL)

    monsters = []
    seen = set()

    def parse_score(s):
        if not s or s == "-":
            return 0
        return float(s.replace(",", "."))

    for match in row_pattern.finditer(html):
        classes = match.group(1).split()

        leader_score = parse_score(match.group(2))
        sub_score = parse_score(match.group(3))
        content = match.group(4)

        # 屬性
        element = ""
        for cls in classes:
            if cls in ELEMENT_MAP:
                element = ELEMENT_MAP[cls]
                break

        # 稀有度
        rarity = 0
        for cls in classes:
            if cls.startswith("rare"):
                try:
                    rarity = int(cls[4:])
                except ValueError:
                    pass

        # 技能/能力標籤
        tags = []
        for cls in classes:
            if cls in tag_map:
                tags.append(tag_map[cls])

        # URL
        url_match = link_pattern.search(content)
        monster_url = url_match.group(1) if url_match else ""

        # 圖示
        icon_match = icon_pattern.search(content)
        icon_url = icon_match.group(1) if icon_match else ""

        # 名稱
        name_match = name_pattern.search(content)
        if not name_match:
            alt_match = re.search(r">([^<]{1,50})</a>", content)
            name = alt_match.group(1).strip() if alt_match else ""
        else:
            name = name_match.group(1).strip()

        if not name:
            continue

        # タイプ
        tds = type_pattern.findall(content)
        type1 = ""
        type2 = ""
        if len(tds) >= 2:
            type_parts = re.sub(r"<[^>]+>", "|", tds[1])
            type_parts = [t.strip().replace("タイプ", "") for t in type_parts.split("|") if t.strip()]
            if len(type_parts) >= 2:
                type1, type2 = type_parts[0], type_parts[1]
            elif len(type_parts) == 1:
                type1 = type_parts[0]

        # 去重
        key = f"{name}_{leader_score}_{sub_score}"
        if key in seen:
            continue
        seen.add(key)

        # 角色編號（從圖示 URL 提取）
        num = 0
        if icon_url:
            num_match = number_pattern.search(icon_url)
            if num_match:
                num = int(num_match.group(1))

        monster = {
            "name": name,
            "no": num,
            "element": element,
            "rarity": rarity,
            "type1": type1,
            "type2": type2,
            "leader_score": leader_score,
            "sub_score": sub_score,
        }
        if icon_url:
            monster["icon"] = icon_url
        if monster_url:
            monster["url"] = monster_url
        if tags:
            monster["tags"] = tags

        monsters.append(monster)

    print(f"解析到 {len(monsters)} 個角色")
    monsters.sort(key=lambda m: m.get("sub_score", 0), reverse=True)
    return monsters


def embed_in_html(monsters):
    """將角色資料嵌入 index.html"""
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        print("index.html 不存在，跳過嵌入")
        return

    compact = json.dumps(monsters, ensure_ascii=False, separators=(",", ":"))

    pattern = r"const MONSTER_DATA = \[.*?\];"
    replacement = f"const MONSTER_DATA = {compact};"

    new_html, count = re.subn(pattern, replacement, html, count=1, flags=re.DOTALL)
    if count:
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(new_html)
        print(f"已更新 index.html（{len(new_html):,} bytes）")
    else:
        print("index.html 中找不到 MONSTER_DATA，跳過嵌入")


def main():
    monsters = scrape_gamewith()

    if not monsters:
        print("未抓取到任何角色資料")
        return

    with open("monsters.json", "w", encoding="utf-8") as f:
        json.dump(monsters, f, ensure_ascii=False, indent=2)
    print(f"已儲存至 monsters.json")

    embed_in_html(monsters)

    # 統計
    with_tags = sum(1 for m in monsters if m.get("tags"))
    avg_tags = sum(len(m.get("tags", [])) for m in monsters) / max(len(monsters), 1)
    print(f"\n=== 統計 ===")
    print(f"總角色數: {len(monsters)}")
    print(f"有標籤: {with_tags} 個 (平均 {avg_tags:.1f} 個標籤/角色)")

    print(f"\n=== Top 5 範例 ===")
    for m in monsters[:5]:
        tags = ", ".join(m.get("tags", [])[:8])
        print(f"  {m['name']} | L:{m['leader_score']} S:{m['sub_score']} | {tags}")


if __name__ == "__main__":
    main()
