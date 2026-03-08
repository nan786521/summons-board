"""Update index.html: add detail modal + star toggle"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

with open("index.html", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add CSS before /* Responsive */
detail_css = """
/* Detail Modal */
.detail-overlay {
  display: none; position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.75); z-index: 300;
  justify-content: center; align-items: center;
}
.detail-overlay.active { display: flex; }
.detail-panel {
  background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 16px; max-width: 400px; width: 90%; overflow: hidden;
}
.detail-header {
  position: relative; display: flex; align-items: center;
  gap: 16px; padding: 20px;
  background: linear-gradient(135deg, var(--bg) 0%, var(--card-bg) 100%);
}
.detail-icon {
  width: 96px; height: 96px; border-radius: 12px;
  border: 3px solid var(--border); object-fit: cover; flex-shrink: 0;
}
.detail-header.owned .detail-icon {
  border-color: var(--owned-border); box-shadow: 0 0 12px rgba(46,204,113,0.3);
}
.detail-title { flex: 1; min-width: 0; }
.detail-name { font-size: 20px; font-weight: 700; word-break: break-all; }
.detail-sub-info { font-size: 12px; color: var(--text-dim); margin-top: 4px; }
.detail-star {
  position: absolute; top: 12px; right: 12px;
  font-size: 32px; cursor: pointer; color: var(--border);
  transition: all 0.2s; line-height: 1; user-select: none;
}
.detail-star:hover { transform: scale(1.2); }
.detail-star.owned { color: var(--owned-border); text-shadow: 0 0 8px rgba(46,204,113,0.5); }
.detail-body { padding: 16px 20px 20px; }
.detail-scores { display: flex; gap: 12px; margin-bottom: 16px; }
.detail-score-box {
  flex: 1; text-align: center; padding: 12px;
  border-radius: 10px; background: var(--bg);
}
.detail-score-label { font-size: 11px; color: var(--text-dim); margin-bottom: 4px; }
.detail-score-num { font-size: 28px; font-weight: 700; }
.detail-info-grid {
  display: grid; grid-template-columns: auto 1fr;
  gap: 6px 12px; font-size: 13px;
}
.detail-info-grid dt { color: var(--text-dim); text-align: right; }
.detail-info-grid dd { font-weight: 500; }
.detail-actions { margin-top: 16px; display: flex; gap: 8px; }
.detail-actions .btn { flex: 1; text-align: center; }
.btn-gw { background: #e67e22; border-color: #e67e22; color: #fff; }
.btn-gw:hover { background: #d35400; }
.card-star {
  font-size: 22px; cursor: pointer; color: var(--border);
  flex-shrink: 0; transition: all 0.15s; user-select: none;
  line-height: 1; padding: 4px;
}
.card-star:hover { transform: scale(1.2); }
.monster-card.owned .card-star { color: var(--owned-border); }

"""
content = content.replace("/* Responsive */", detail_css + "/* Responsive */")

# 2. Add detail modal HTML before </body>
detail_html = """
<!-- Detail Modal -->
<div class="detail-overlay" id="detailOverlay">
  <div class="detail-panel">
    <div class="detail-header" id="detailHeader">
      <img class="detail-icon" id="detailIcon" src="" alt="">
      <div class="detail-title">
        <div class="detail-name" id="detailName"></div>
        <div class="detail-sub-info" id="detailSubInfo"></div>
      </div>
      <div class="detail-star" id="detailStar">☆</div>
    </div>
    <div class="detail-body">
      <div class="detail-scores">
        <div class="detail-score-box">
          <div class="detail-score-label">Leader 評分</div>
          <div class="detail-score-num" id="detailLeader"></div>
        </div>
        <div class="detail-score-box">
          <div class="detail-score-label">Sub 評分</div>
          <div class="detail-score-num" id="detailSubScore"></div>
        </div>
      </div>
      <dl class="detail-info-grid" id="detailInfo"></dl>
      <div class="detail-actions">
        <a class="btn btn-gw" id="detailGwLink" href="#" target="_blank">GameWith 詳情</a>
        <button class="btn" id="detailClose">關閉</button>
      </div>
    </div>
  </div>
</div>
"""
content = content.replace("</body>", detail_html + "</body>")

# 3. Update renderCard: add star button, remove <a> link from name
old_rc = 'function renderCard(m) {'
new_rc_start = content.find(old_rc)
new_rc_end = content.find('\n}', new_rc_start) + 2

old_render_card = content[new_rc_start:new_rc_end]

new_render_card = """function renderCard(m) {
  const isOwned = ownedSet.has(m.name);
  const iconHtml = m.icon
    ? `<img class="monster-icon" src="${m.icon}" alt="${escAttr(m.name)}" loading="lazy">`
    : `<div class="monster-icon"></div>`;
  const elBadge = m.element
    ? `<span class="el-badge ${elClass(m.element)}">${m.element}</span>`
    : "";
  const rarityHtml = m.rarity ? `<span class="rarity">★${m.rarity}</span>` : "";

  return `
    <div class="monster-card${isOwned ? " owned" : ""}" data-name="${escAttr(m.name)}">
      <div class="card-star" data-star="${escAttr(m.name)}">${isOwned ? "★" : "☆"}</div>
      ${iconHtml}
      ${elBadge}
      <div class="monster-info">
        <div class="monster-name">${escHtml(m.name)}</div>
        <div class="monster-types">
          ${rarityHtml}
          <span class="type-badge ${typeClass(m.type1)}">${m.type1}</span>
          / ${m.type2}
        </div>
      </div>
      <div class="monster-scores">
        <div class="score-badge">
          <div class="score-label">Leader</div>
          <div class="score-value ${scoreClass(m.leader_score)}">${m.leader_score}</div>
        </div>
        <div class="score-badge">
          <div class="score-label">Sub</div>
          <div class="score-value ${scoreClass(m.sub_score)}">${m.sub_score}</div>
        </div>
      </div>
    </div>`;
}"""

content = content.replace(old_render_card, new_render_card)

# 4. Replace grid click event handler
old_event = """document.getElementById("monsterGrid").addEventListener("click", e => {
  const card = e.target.closest(".monster-card");
  if (!card) return;
  const name = card.dataset.name;
  toggleOwned(name);

  // Update card in-place
  card.classList.toggle("owned");
  const indicator = card.querySelector(".own-indicator");
  indicator.textContent = ownedSet.has(name) ? "★" : "☆";
});"""

new_event = """document.getElementById("monsterGrid").addEventListener("click", e => {
  // Star click = toggle owned
  const star = e.target.closest(".card-star");
  if (star) {
    e.stopPropagation();
    const name = star.dataset.star;
    toggleOwned(name);
    const card = star.closest(".monster-card");
    card.classList.toggle("owned");
    star.textContent = ownedSet.has(name) ? "★" : "☆";
    return;
  }
  // Card click = show detail
  const card = e.target.closest(".monster-card");
  if (!card) return;
  showDetail(card.dataset.name);
});

function showDetail(name) {
  const m = allMonsters.find(x => x.name === name);
  if (!m) return;
  const isOwned = ownedSet.has(name);

  document.getElementById("detailHeader").classList.toggle("owned", isOwned);
  document.getElementById("detailIcon").src = m.icon || "";
  document.getElementById("detailName").textContent = m.name;

  const elText = m.element ? m.element + "屬性" : "";
  const rarText = m.rarity ? "★" + m.rarity : "";
  document.getElementById("detailSubInfo").textContent = [elText, rarText].filter(Boolean).join(" / ");

  const star = document.getElementById("detailStar");
  star.textContent = isOwned ? "★" : "☆";
  star.classList.toggle("owned", isOwned);
  star.dataset.name = name;

  const ls = document.getElementById("detailLeader");
  ls.textContent = m.leader_score;
  ls.className = "detail-score-num " + scoreClass(m.leader_score);

  const ss = document.getElementById("detailSubScore");
  ss.textContent = m.sub_score;
  ss.className = "detail-score-num " + scoreClass(m.sub_score);

  document.getElementById("detailInfo").innerHTML =
    '<dt>タイプ1</dt><dd><span class="type-badge ' + typeClass(m.type1) + '">' + m.type1 + '</span></dd>' +
    '<dt>タイプ2</dt><dd>' + (m.type2 || "なし") + '</dd>' +
    '<dt>屬性</dt><dd>' + (m.element ? '<span class="el-badge ' + elClass(m.element) + '">' + m.element + '</span>' : "—") + '</dd>' +
    '<dt>稀有度</dt><dd>' + (m.rarity ? "★".repeat(Math.min(m.rarity, 7)) : "—") + '</dd>' +
    '<dt>狀態</dt><dd style="color:' + (isOwned ? 'var(--owned-border)' : 'var(--text-dim)') + '">' + (isOwned ? "已持有" : "未持有") + '</dd>';

  const gwLink = document.getElementById("detailGwLink");
  gwLink.href = m.url || "#";
  gwLink.style.display = m.url ? "" : "none";

  document.getElementById("detailOverlay").classList.add("active");
}

document.getElementById("detailStar").addEventListener("click", function() {
  const name = this.dataset.name;
  toggleOwned(name);
  const isOwned = ownedSet.has(name);
  this.textContent = isOwned ? "★" : "☆";
  this.classList.toggle("owned", isOwned);
  document.getElementById("detailHeader").classList.toggle("owned", isOwned);
  // refresh detail info
  showDetail(name);
  // update card in grid
  const card = document.querySelector('.monster-card[data-name="' + CSS.escape(name) + '"]');
  if (card) {
    card.classList.toggle("owned", isOwned);
    const cs = card.querySelector(".card-star");
    if (cs) cs.textContent = isOwned ? "★" : "☆";
  }
});

document.getElementById("detailClose").addEventListener("click", () => {
  document.getElementById("detailOverlay").classList.remove("active");
});

document.getElementById("detailOverlay").addEventListener("click", e => {
  if (e.target === e.currentTarget)
    document.getElementById("detailOverlay").classList.remove("active");
});"""

# Fix: the old_event has a JS string with "★".repeat which uses non-ASCII
# Let me use a simpler find-replace approach
assert old_event in content, "Could not find old event handler"
content = content.replace(old_event, new_event)

# Save
with open("index.html", "w", encoding="utf-8") as f:
    f.write(content)

print(f"Done. File size: {len(content):,} bytes")
