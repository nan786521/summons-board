"""Update detail modal to show skill tags"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

with open("index.html", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add CSS for tags in detail panel
tag_css = """
.detail-tags {
  margin-top: 12px;
}
.detail-tags-title {
  font-size: 11px;
  color: var(--text-dim);
  margin-bottom: 6px;
}
.detail-tag {
  display: inline-block;
  padding: 3px 8px;
  margin: 2px;
  border-radius: 4px;
  font-size: 11px;
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
}
.detail-tag.chain { border-color: #e67e22; color: #e67e22; }
.detail-tag.speed { border-color: #2ecc71; color: #2ecc71; }
.detail-tag.buff { border-color: #3498db; color: #3498db; }
.detail-tag.dmg { border-color: #e74c3c; color: #e74c3c; }
.detail-tag.def { border-color: #9b59b6; color: #9b59b6; }
"""
content = content.replace("/* Responsive */", tag_css + "\n/* Responsive */")

# 2. Add tags container to detail modal HTML
old_actions = '<div class="detail-actions">'
new_actions = '<div class="detail-tags" id="detailTags"></div>\n      <div class="detail-actions">'
content = content.replace(old_actions, new_actions, 1)

# 3. Update showDetail function to display tags
old_show_end = """  const gwLink = document.getElementById("detailGwLink");
  gwLink.href = m.url || "#";
  gwLink.style.display = m.url ? "" : "none";

  document.getElementById("detailOverlay").classList.add("active");
}"""

new_show_end = """  // Tags
  const tagsEl = document.getElementById("detailTags");
  if (m.tags && m.tags.length > 0) {
    const tagHtml = m.tags.map(t => {
      let cls = "detail-tag";
      if (t.includes("チェーン") || t.includes("速攻")) cls += " chain";
      else if (t.includes("アップ") || t.includes("強化") || t.includes("バフ")) cls += " buff";
      else if (t.includes("ダメ") || t.includes("攻撃") || t.includes("貫通") || t.includes("破壊")) cls += " dmg";
      else if (t.includes("軽減") || t.includes("防") || t.includes("バリア") || t.includes("ブロック") || t.includes("回復")) cls += " def";
      return '<span class="' + cls + '">' + t + '</span>';
    }).join("");
    tagsEl.innerHTML = '<div class="detail-tags-title">スキル・能力</div>' + tagHtml;
    tagsEl.style.display = "";
  } else {
    tagsEl.style.display = "none";
  }

  const gwLink = document.getElementById("detailGwLink");
  gwLink.href = m.url || "#";
  gwLink.style.display = m.url ? "" : "none";

  document.getElementById("detailOverlay").classList.add("active");
}"""

content = content.replace(old_show_end, new_show_end)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(content)

print(f"Done. File size: {len(content):,} bytes")
