// The /dashboard page. Static HTML; data comes from /stats with the admin token,
// which the page asks for once and keeps in this browser's localStorage.
// Feedback is user-written, so it is only ever inserted with textContent.

export const DASHBOARD_HTML = String.raw`<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DesktopWidgets stats</title>
<style>
  :root {
    --bg: #12141b; --panel: #1b1f2a; --panel-2: #222735; --border: #2f3546;
    --txt: #f3f5fc; --txt2: #a5aec2; --muted: #7d869b;
    --accent: #a6b4ff; --track: #2a3044; --star: #f2c66d;
    --glow: rgba(166, 180, 255, 0.16);
    --map-empty: #262b3a; --map-low: #3a4370;
  }
  @media (prefers-color-scheme: light) {
    :root {
      --bg: #f2f0ec; --panel: #fbfaf8; --panel-2: #f1eee9; --border: #dcd7cf;
      --txt: #242833; --txt2: #5a5f6b; --muted: #7a7f8b;
      --accent: #4f63b0; --track: #e6e2db; --star: #a86a12;
      --glow: rgba(79, 99, 176, 0.12);
      --map-empty: #e7e3dc; --map-low: #c9d0ea;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--txt);
    font: 14px/1.45 "Segoe UI", system-ui, -apple-system, sans-serif;
    background-image: radial-gradient(900px 420px at 85% -120px, var(--glow), transparent 70%);
    min-height: 100vh;
  }
  main { max-width: 1080px; margin: 0 auto; padding: 32px 16px 56px; }
  .eyebrow { display: flex; align-items: center; gap: 8px; color: var(--txt2);
             font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
  .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--accent); flex: none; }
  h1 { margin: 6px 0 4px; font-size: 30px; }
  .sub { color: var(--txt2); margin: 0 0 24px; }
  .row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
  .grid { display: grid; gap: 14px; }
  .tiles { grid-template-columns: repeat(4, minmax(0, 1fr)); margin-bottom: 14px; }
  .two { grid-template-columns: 1.3fr 1fr; }
  @media (max-width: 760px) { .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); } .two { grid-template-columns: 1fr; } }
  .card { background: var(--panel); border: 1px solid var(--border); border-radius: 16px; padding: 16px 18px; min-width: 0; }
  .tile .value { font-size: 30px; font-weight: 700; margin-top: 6px; font-variant-numeric: tabular-nums; }
  .tile .note { color: var(--muted); font-size: 12px; }
  .card h2 { margin: 0 0 12px; }
  .bars { display: grid; gap: 8px; }
  .bar { display: grid; grid-template-columns: minmax(90px, 160px) 1fr 44px; gap: 10px; align-items: center;
         padding: 2px 0; border-radius: 8px; position: relative; }
  .bar .name { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .bar .track { height: 10px; background: var(--track); border-radius: 5px; overflow: hidden; }
  .bar .track, .bar .fill { display: block; }
  .bar .fill { height: 100%; background: var(--accent); border-radius: 0 5px 5px 0; min-width: 4px; }
  .bar .num { text-align: right; color: var(--txt2); font-variant-numeric: tabular-nums; }
  .bar:hover .fill { filter: brightness(1.15); }
  .bar:hover .name { color: var(--txt); }
  .empty { color: var(--muted); padding: 8px 0; }
  .feedback { display: grid; gap: 10px; }
  .item { background: var(--panel-2); border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px; }
  .item .meta { display: flex; gap: 10px; flex-wrap: wrap; color: var(--muted); font-size: 12px; margin-bottom: 4px; }
  .stars { color: var(--star); letter-spacing: 1px; }
  .item p { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; }
  .item p.none { color: var(--muted); font-style: italic; }
  button, input { font: inherit; }
  button { background: var(--accent); color: var(--bg); border: 0; border-radius: 999px; padding: 9px 18px;
           font-weight: 700; cursor: pointer; }
  button.ghost { background: var(--panel-2); color: var(--txt); border: 1px solid var(--border); }
  input { background: var(--panel-2); color: var(--txt); border: 1px solid var(--border); border-radius: 10px;
          padding: 9px 12px; min-width: 0; flex: 1; }
  #login { max-width: 460px; }
  #login .row { margin-top: 12px; }
  .error { color: #ff8a8a; margin-top: 10px; min-height: 1.4em; }
  .map-card { margin-bottom: 14px; }
  .map-wrap { position: relative; margin-top: 10px; }
  #map { width: 100%; height: auto; aspect-ratio: 960 / 470; display: block; }  /* same size zoomed or not */
  #map path { fill: var(--map-empty); stroke: var(--panel); stroke-width: .8; vector-effect: non-scaling-stroke; transition: fill .15s; }
  #map path.has { cursor: pointer; }
  #map path:hover, #map path:focus { stroke: var(--txt); stroke-width: 1.5; outline: none; }
  .zoom { margin-left: auto; display: flex; gap: 6px; }
  .zoom button { padding: 4px 12px; font-size: 12px; }
  .zoom button[aria-pressed="false"] { background: var(--panel-2); color: var(--txt2); border: 1px solid var(--border); }
  .legend { display: flex; align-items: center; gap: 10px; color: var(--muted); font-size: 12px; margin-top: 8px; }
  .legend .ramp { flex: 0 1 220px; height: 8px; border-radius: 4px;
                  background: linear-gradient(90deg, var(--map-low), var(--accent)); }
  .legend .none { width: 12px; height: 12px; border-radius: 3px; background: var(--map-empty); }
  #tip { position: fixed; pointer-events: none; background: var(--panel-2); border: 1px solid var(--border);
         border-radius: 8px; padding: 6px 10px; font-size: 12px; display: none; z-index: 9; }
  .filters { margin: 0 0 16px; }
  .filters button { padding: 6px 14px; }
  .filters button[aria-pressed="false"] { background: var(--panel-2); color: var(--txt2); border: 1px solid var(--border); }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { text-align: left; padding: 6px 4px; border-bottom: 1px solid var(--border); }
  th { color: var(--txt2); font-weight: 600; }
  td.n { text-align: right; font-variant-numeric: tabular-nums; }
  details { margin-top: 12px; color: var(--txt2); }
  summary { cursor: pointer; }
</style>
</head>
<body>
<main>
  <div class="eyebrow"><span class="dot"></span>DesktopWidgets</div>
  <h1>Your users</h1>
  <p class="sub" id="updated">Usage pings and feedback from the app.</p>

  <section id="login" class="card" hidden>
    <div class="eyebrow"><span class="dot"></span>Admin token</div>
    <p class="sub" style="margin:8px 0 0">Enter the ADMIN_TOKEN you set with <code>wrangler secret put</code>.
       It is kept in this browser only.</p>
    <form class="row" id="login-form">
      <input id="token" type="password" autocomplete="current-password" placeholder="Admin token" required>
      <button type="submit">Show stats</button>
    </form>
    <div class="error" id="error"></div>
  </section>

  <section id="stats" hidden>
    <div class="row filters" role="group" aria-label="Users shown">
      <button data-range="active_30d" aria-pressed="true">Active last 30 days</button>
      <button data-range="installs" aria-pressed="false">All installs</button>
      <span style="flex:1"></span>
      <button class="ghost" id="refresh">Refresh</button>
      <button class="ghost" id="logout">Forget token</button>
    </div>

    <div class="grid tiles">
      <div class="card tile"><div class="eyebrow"><span class="dot"></span>Total installs</div><div class="value" id="t-installs">-</div><div class="note">ever seen</div></div>
      <div class="card tile"><div class="eyebrow"><span class="dot"></span>Active 7 days</div><div class="value" id="t-7d">-</div><div class="note">opened the app this week</div></div>
      <div class="card tile"><div class="eyebrow"><span class="dot"></span>Active 30 days</div><div class="value" id="t-30d">-</div><div class="note">opened the app this month</div></div>
      <div class="card tile"><div class="eyebrow"><span class="dot"></span>Average rating</div><div class="value" id="t-rating">-</div><div class="note" id="t-rating-note">no feedback yet</div></div>
    </div>

    <div class="card map-card">
      <div class="row" style="gap:8px">
        <div class="eyebrow"><span class="dot"></span><span id="map-title">Where your users are</span></div>
        <div class="zoom" role="group" aria-label="Map area">
          <button data-zoom="world" aria-pressed="true">World</button>
          <button data-zoom="europe" aria-pressed="false">Europe</button>
        </div>
      </div>
      <div class="map-wrap"><svg id="map" role="img" aria-label="World map of users per country"></svg></div>
      <div class="legend"><span class="none"></span>No users<span style="width:12px"></span>
        <span id="legend-min">1</span><span class="ramp"></span><span id="legend-max">-</span></div>
    </div>

    <div class="grid two">
      <div class="card">
        <div class="eyebrow"><span class="dot"></span><span id="country-title">Users per country</span></div>
        <div class="bars" id="countries" style="margin-top:12px"></div>
        <details><summary>Show as table</summary><table id="country-table"></table></details>
      </div>
      <div class="grid" style="align-content:start">
        <div class="card">
          <div class="eyebrow"><span class="dot"></span>Versions (active last 30 days)</div>
          <div class="bars" id="versions" style="margin-top:12px"></div>
        </div>
        <div class="card">
          <div class="eyebrow"><span class="dot"></span>Ratings</div>
          <div class="bars" id="ratings" style="margin-top:12px"></div>
        </div>
      </div>
    </div>

    <div class="card" style="margin-top:14px">
      <div class="eyebrow"><span class="dot"></span>Latest feedback</div>
      <div class="feedback" id="feedback" style="margin-top:12px"></div>
    </div>
  </section>
</main>
<div id="tip" role="tooltip"></div>
<script>
(function () {
  var KEY = 'dw-admin-token';
  var data = null, range = 'active_30d';
  var regionNames = null;
  try { regionNames = new Intl.DisplayNames(undefined, { type: 'region' }); } catch (e) {}

  function el(id) { return document.getElementById(id); }
  function token() { try { return localStorage.getItem(KEY) || ''; } catch (e) { return ''; } }
  function setToken(v) { try { v ? localStorage.setItem(KEY, v) : localStorage.removeItem(KEY); } catch (e) {} }
  function fmt(n) { return (n || 0).toLocaleString(); }

  function countryName(code) {
    if (!code || code === 'XX' || code === 'T1') return 'Unknown';
    try { return (regionNames && regionNames.of(code)) || code; } catch (e) { return code; }
  }
  // Windows does not draw flag emoji (they show as "NL"), so names only.
  function flag() { return ''; }

  // Tooltip shared by every bar (hover and keyboard focus).
  var tip = el('tip');
  function showTip(e, text) {
    tip.textContent = text; tip.style.display = 'block';
    var x = (e.clientX || e.target.getBoundingClientRect().right) + 12;
    var y = (e.clientY || e.target.getBoundingClientRect().top) + 12;
    tip.style.left = Math.min(x, innerWidth - tip.offsetWidth - 8) + 'px';
    tip.style.top = y + 'px';
  }
  function hideTip() { tip.style.display = 'none'; }

  function bars(container, rows, total, unit) {
    container.textContent = '';
    if (!rows.length) {
      var p = document.createElement('div'); p.className = 'empty'; p.textContent = 'No data yet.';
      container.appendChild(p); return;
    }
    var max = Math.max.apply(null, rows.map(function (r) { return r.value; })) || 1;
    rows.forEach(function (r) {
      var row = document.createElement('div'); row.className = 'bar'; row.tabIndex = 0;
      var name = document.createElement('span'); name.className = 'name'; name.textContent = r.label;
      var track = document.createElement('span'); track.className = 'track';
      var fill = document.createElement('span'); fill.className = 'fill';
      fill.style.width = (100 * r.value / max) + '%'; track.appendChild(fill);
      var num = document.createElement('span'); num.className = 'num'; num.textContent = fmt(r.value);
      row.appendChild(name); row.appendChild(track); row.appendChild(num);
      var pct = total ? Math.round(100 * r.value / total) : 0;
      var text = r.label + ': ' + fmt(r.value) + ' ' + unit + (total ? ' (' + pct + '%)' : '');
      row.addEventListener('mousemove', function (e) { showTip(e, text); });
      row.addEventListener('focus', function (e) { showTip(e, text); });
      row.addEventListener('mouseleave', hideTip); row.addEventListener('blur', hideTip);
      container.appendChild(row);
    });
  }

  var map = null, zoom = 'world';
  // Europe in the map's own coordinates (the 960x470 Natural Earth layout).
  var EUROPE = '445 52 140 96';
  function loadMap() {
    return fetch('/map.json').then(function (r) { return r.json(); }).then(function (m) { map = m; })
      .catch(function () { map = { viewBox: '0 0 960 470', paths: {} }; });
  }

  // Sequential, one hue: share of the busiest country, on a square-root scale so
  // smaller countries are still visible next to a large one.
  function drawMap(counts, total) {
    var svg = el('map');
    svg.textContent = '';
    svg.setAttribute('viewBox', zoom === 'europe' ? EUROPE : map.viewBox);
    var max = 0;
    Object.keys(counts).forEach(function (k) { max = Math.max(max, counts[k]); });
    el('legend-max').textContent = fmt(max);
    Object.keys(map.paths).forEach(function (code) {
      var p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      p.setAttribute('d', map.paths[code]);
      var n = counts[code] || 0;
      if (n > 0) {
        var share = Math.round(15 + 85 * Math.sqrt(n / max));
        p.style.fill = 'color-mix(in oklab, var(--accent) ' + share + '%, var(--map-low))';
        p.setAttribute('class', 'has');
        p.setAttribute('tabindex', '0');
        var text = countryName(code) + ': ' + fmt(n) + ' users (' + Math.round(100 * n / total) + '%)';
        p.setAttribute('aria-label', text);
        p.addEventListener('mousemove', function (e) { showTip(e, text); });
        p.addEventListener('focus', function (e) { showTip(e, text); });
        p.addEventListener('mouseleave', hideTip); p.addEventListener('blur', hideTip);
      }
      svg.appendChild(p);
    });
  }

  function render() {
    var t = data.totals || {};
    el('t-installs').textContent = fmt(t.installs);
    el('t-7d').textContent = fmt(t.active_7d);
    el('t-30d').textContent = fmt(t.active_30d);

    var ratings = data.ratings || [], count = 0, sum = 0;
    ratings.forEach(function (r) { count += r.n; sum += r.n * r.rating; });
    el('t-rating').textContent = count ? (sum / count).toFixed(1) + ' / 5' : '-';
    el('t-rating-note').textContent = count ? fmt(count) + ' ratings' : 'no feedback yet';

    var countries = (data.countries || []).map(function (c) {
      return { label: flag(c.country) + countryName(c.country), code: c.country, value: c[range] || 0 };
    }).filter(function (c) { return c.value > 0; }).sort(function (a, b) { return b.value - a.value; });
    var total = countries.reduce(function (s, c) { return s + c.value; }, 0);
    el('country-title').textContent = range === 'installs' ? 'Installs per country' : 'Active users per country (30 days)';
    bars(el('countries'), countries.slice(0, 15), total, 'users');
    var counts = {};
    countries.forEach(function (c) { counts[c.code] = c.value; });
    el('map-title').textContent = range === 'installs' ? 'Where your users are (all installs)'
                                                       : 'Where your users are (active last 30 days)';
    if (map) drawMap(counts, total || 1);

    var table = el('country-table'); table.textContent = '';
    var head = table.insertRow(); ['Country', 'Installs', 'Active 30d'].forEach(function (h, i) {
      var th = document.createElement('th'); th.textContent = h; if (i) th.className = 'n'; head.appendChild(th); });
    (data.countries || []).forEach(function (c) {
      var tr = table.insertRow();
      [flag(c.country) + countryName(c.country), fmt(c.installs), fmt(c.active_30d)].forEach(function (v, i) {
        var td = tr.insertCell(); td.textContent = v; if (i) td.className = 'n'; });
    });

    var versions = (data.versions || []).map(function (v) { return { label: v.version || '?', value: v.installs }; });
    bars(el('versions'), versions, versions.reduce(function (s, v) { return s + v.value; }, 0), 'users');

    var byRating = {}; ratings.forEach(function (r) { byRating[r.rating] = r.n; });
    var ratingRows = [5, 4, 3, 2, 1].map(function (r) {
      return { label: '★'.repeat(r), value: byRating[r] || 0 }; });
    bars(el('ratings'), count ? ratingRows : [], count, 'ratings');

    var list = el('feedback'); list.textContent = '';
    var recent = data.recent_feedback || [];
    if (!recent.length) {
      var e = document.createElement('div'); e.className = 'empty'; e.textContent = 'No feedback yet.'; list.appendChild(e);
    }
    recent.forEach(function (f) {
      var item = document.createElement('div'); item.className = 'item';
      var meta = document.createElement('div'); meta.className = 'meta';
      var stars = document.createElement('span'); stars.className = 'stars';
      stars.textContent = '★'.repeat(f.rating) + '☆'.repeat(5 - f.rating);
      stars.setAttribute('aria-label', f.rating + ' out of 5');
      var when = document.createElement('span'); when.textContent = new Date(f.created_at).toLocaleString();
      var where = document.createElement('span'); where.textContent = flag(f.country) + countryName(f.country);
      var ver = document.createElement('span'); ver.textContent = 'v' + (f.version || '?');
      [stars, when, where, ver].forEach(function (n) { meta.appendChild(n); });
      var text = document.createElement('p');
      if (f.text) { text.textContent = f.text; } else { text.textContent = 'No comment'; text.className = 'none'; }
      item.appendChild(meta); item.appendChild(text); list.appendChild(item);
    });
    el('updated').textContent = 'Updated ' + new Date().toLocaleTimeString() + '. Countries come from Cloudflare; IP addresses are not stored.';
  }

  function load() {
    var tok = token();
    if (!tok) { el('login').hidden = false; el('stats').hidden = true; return; }
    fetch('/stats', { headers: { Authorization: 'Bearer ' + tok } }).then(function (r) {
      if (r.status === 401) { setToken(''); el('error').textContent = 'That token is not right.'; throw new Error('auth'); }
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    }).then(function (json) {
      return (map ? Promise.resolve() : loadMap()).then(function () { return json; });
    }).then(function (json) {
      data = json; el('login').hidden = true; el('stats').hidden = false; el('error').textContent = ''; render();
    }).catch(function (err) {
      el('login').hidden = false; el('stats').hidden = true;
      if (err.message !== 'auth') el('error').textContent = 'Could not load stats (' + err.message + ').';
    });
  }

  el('login-form').addEventListener('submit', function (e) {
    e.preventDefault(); setToken(el('token').value.trim()); el('token').value = ''; load();
  });
  el('logout').addEventListener('click', function () { setToken(''); data = null; load(); });
  el('refresh').addEventListener('click', load);
  Array.prototype.forEach.call(document.querySelectorAll('[data-range]'), function (b) {
    b.addEventListener('click', function () {
      range = b.getAttribute('data-range');
      Array.prototype.forEach.call(document.querySelectorAll('[data-range]'), function (o) {
        o.setAttribute('aria-pressed', String(o === b)); });
      if (data) render();
    });
  });
  Array.prototype.forEach.call(document.querySelectorAll('[data-zoom]'), function (b) {
    b.addEventListener('click', function () {
      zoom = b.getAttribute('data-zoom');
      Array.prototype.forEach.call(document.querySelectorAll('[data-zoom]'), function (o) {
        o.setAttribute('aria-pressed', String(o === b)); });
      if (data) render();
    });
  });
  load();
})();
</script>
</body>
</html>`;
