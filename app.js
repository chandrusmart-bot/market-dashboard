// Renders data/latest.json + data/history.json. Never fetches live market data.
const SECTIONS = {
  flows: "Institutional flows (India)",
  indices: "Indices",
  commodities: "Commodities & currency",
  us_stocks: "US-listed stocks",
};
// Set this to your repo's workflow page; filled in automatically on github.io.
const ACTIONS_URL = (() => {
  const m = location.hostname.match(/^(.+)\.github\.io$/);
  const repo = location.pathname.split("/")[1];
  return m && repo ? `https://github.com/${m[1]}/${repo}/actions/workflows/daily-update.yml` : "#";
})();

const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
};
const isNum = (x) => typeof x === "number" && Number.isFinite(x);

function fmt(x, digits = 2) {
  return isNum(x) ? x.toLocaleString("en-IN", { minimumFractionDigits: digits, maximumFractionDigits: digits }) : "—";
}
function signed(x, digits = 2) {
  return isNum(x) ? (x > 0 ? "+" : x < 0 ? "−" : "") + fmt(Math.abs(x), digits) : "—";
}
function istTime(iso) {
  const d = new Date(iso);
  if (!iso || isNaN(d)) return "—";
  return d.toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false,
  }) + " IST";
}

function sparkline(points) {
  const vals = (points || []).map((p) => p[1]).filter(isNum);
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("class", "spark");
  svg.setAttribute("viewBox", "0 0 100 36");
  svg.setAttribute("preserveAspectRatio", "none");
  if (vals.length < 2) {
    const t = document.createElementNS(ns, "text");
    t.setAttribute("x", "0"); t.setAttribute("y", "22");
    t.textContent = "collecting history…";
    svg.appendChild(t);
    return svg;
  }
  const min = Math.min(...vals), max = Math.max(...vals), span = max - min || 1;
  const pts = vals.map((v, i) => `${(i / (vals.length - 1)) * 100},${33 - ((v - min) / span) * 30}`);
  const line = document.createElementNS(ns, "polyline");
  line.setAttribute("points", pts.join(" "));
  line.setAttribute("vector-effect", "non-scaling-stroke");
  svg.appendChild(line);
  return svg;
}

function renderTile(t, series) {
  const dir = !isNum(t.change) || t.change === 0 ? "flat" : t.change > 0 ? "up" : "down";
  const card = el("article", `tile ${t.status || "error"}`);

  const head = el("div", "tile-head");
  head.append(el("span", "label", t.label || t.id));
  if (t.status !== "ok") {
    const b = el("span", "badge", t.status === "error" ? "⚠ no data" : "⚠ stale");
    b.title = t.error || "Value may be out of date";
    head.append(b);
  }
  card.append(head);

  const value = el("div", `value ${dir}`);
  value.append(isNum(t.value) ? fmt(t.value) : "—");
  if (t.unit) value.append(" ", el("span", "unit", t.unit));
  card.append(value);

  const arrow = dir === "up" ? "▲" : dir === "down" ? "▼" : "•";
  const pct = isNum(t.change_pct) ? ` (${signed(t.change_pct)}%)` : "";
  card.append(el("div", `delta ${dir}`, `${arrow} ${signed(t.change)}${pct}`));

  const spark = sparkline(series);
  spark.classList.add(dir);
  card.append(spark);

  const meta = el("div", "meta");
  meta.append(`As of ${t.as_of || "—"} · fetched ${istTime(t.fetched_at)}`, el("br"));
  if (t.source_url) {
    const a = el("a", null, t.source_name || "source");
    a.href = t.source_url; a.target = "_blank"; a.rel = "noopener";
    meta.append(a);
  } else {
    meta.append(t.source_name || "—");
  }
  card.append(meta);
  return card;
}

function render(latest, history) {
  const root = $("dashboard");
  root.replaceChildren();
  const tiles = Object.values(latest.tiles || {});
  for (const [key, title] of Object.entries(SECTIONS)) {
    const inSection = tiles.filter((t) => t.section === key);
    if (!inSection.length) continue;
    root.append(el("h2", null, title));
    const grid = el("div", "grid");
    for (const t of inSection) grid.append(renderTile(t, (history.series || {})[t.id]));
    root.append(grid);
  }
  $("updated").textContent = `Snapshot generated ${istTime(latest.generated_at)}`;
  const banner = $("banner");
  banner.hidden = !latest.sample;
  banner.textContent = "Showing sample data. The first scheduled update will replace it with real values.";
}

async function load() {
  const btn = $("refresh");
  btn.disabled = true;
  try {
    const bust = `?t=${Date.now()}`;
    const [latest, history] = await Promise.all([
      fetch(`data/latest.json${bust}`, { cache: "no-store" }).then((r) => r.json()),
      fetch(`data/history.json${bust}`, { cache: "no-store" }).then((r) => r.json()).catch(() => ({})),
    ]);
    render(latest, history);
  } catch (e) {
    $("updated").textContent = "Could not load data/latest.json";
  } finally {
    btn.disabled = false;
  }
}

$("run-update").href = ACTIONS_URL;
$("refresh").addEventListener("click", load);
load();
