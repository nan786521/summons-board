"""
從 GameWith ソウル一覽頁面抓取ソウル圖示 URL
輸出 soul_icons.json: { "ソウル名": "圖示URL", ... }
"""

import json
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

URL = "https://gamewith.jp/summonsboard/article/show/91320"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ja,en;q=0.5",
        "Referer": "https://gamewith.jp/summonsboard/",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            import gzip
            data = gzip.decompress(data)
        return data.decode("utf-8")


def main():
    print("Fetching soul list page...")
    html = fetch(URL)

    # Pattern: soul icon img followed by soul name in table rows or list
    # GameWith typically uses: <img src="https://img.gamewith.jp/img/HASH.png"> ... soul name in nearby td/text
    # Try multiple patterns

    icons = {}

    # Pattern 1: table rows with img and text
    # <tr><td><img src="..."></td><td>ソウル名</td>...</tr>
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)
    for row in rows:
        imgs = re.findall(r'<img[^>]+src="(https://img\.gamewith\.jp/img/[^"]+)"', row)
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if imgs and len(cells) >= 2:
            # Clean text from cells to find name
            for i, cell in enumerate(cells):
                name = re.sub(r"<[^>]+>", "", cell).strip()
                if name and not name.startswith("http") and len(name) > 1 and len(name) < 30:
                    # Check if this cell doesn't contain the img
                    if "<img" not in cell:
                        icons[name] = imgs[0]
                        break

    # Pattern 2: divs with data-col structure
    # <div class="..."><img src="..."><span>soul name</span></div>
    div_matches = re.findall(
        r'<img[^>]+src="(https://img\.gamewith\.jp/img/[^"]+)"[^>]*>\s*(?:</[^>]+>\s*)*(?:<[^>]*>)*([^<]{2,30})',
        html
    )
    for img_url, name in div_matches:
        name = name.strip()
        if name and name not in icons and not name.startswith("http"):
            icons[name] = img_url

    # Pattern 3: Look for h4/h3 headings with soul names, followed by img
    heading_matches = re.findall(
        r'<img[^>]+src="(https://img\.gamewith\.jp/img/[^"]+)"[^>]*alt="([^"]+)"',
        html
    )
    for img_url, alt_name in heading_matches:
        alt_name = alt_name.strip()
        if alt_name and len(alt_name) < 30:
            if alt_name not in icons:
                icons[alt_name] = img_url

    print(f"Found {len(icons)} soul icons")

    # Show top matches
    # Load abilities to check coverage
    with open("abilities.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    from collections import Counter
    soul_counts = Counter()
    for v in data.values():
        for s in (v.get("recommended_souls") or []):
            soul_counts[s.get("name", "")] += 1

    matched = 0
    for name, cnt in soul_counts.most_common(40):
        if name in icons:
            matched += 1
            print(f"  ✓ {name} ({cnt}x) -> {icons[name][:60]}...")
        else:
            print(f"  ✗ {name} ({cnt}x)")

    print(f"\nTop 40 coverage: {matched}/40")

    with open("soul_icons.json", "w", encoding="utf-8") as f:
        json.dump(icons, f, ensure_ascii=False, indent=2)

    print(f"Saved soul_icons.json ({len(icons)} entries)")


if __name__ == "__main__":
    main()
