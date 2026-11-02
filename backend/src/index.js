// DesktopWidgets usage + feedback API (Cloudflare Worker, D1 database "DB").
//
//   POST /ping      {install_id, version, os}              -> 204
//   POST /feedback  {install_id, version, rating, text}    -> 204
//   GET  /stats     Authorization: Bearer <ADMIN_TOKEN>    -> JSON summary
//
// The visitor's country comes from request.cf.country. The IP address is
// never read or stored.

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MAX_FEEDBACK_PER_DAY = 3;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    try {
      if (request.method === "POST" && url.pathname === "/ping") return await ping(request, env);
      if (request.method === "POST" && url.pathname === "/feedback") return await feedback(request, env);
      if (request.method === "GET" && url.pathname === "/stats") return await stats(request, env);
      return new Response("Not found", { status: 404 });
    } catch (err) {
      return new Response("Bad request", { status: 400 });
    }
  },
};

function clean(value, max) {
  return String(value ?? "").replace(/[\u0000-\u001f]/g, " ").trim().slice(0, max);
}

async function readBody(request) {
  const body = await request.json();
  if (!UUID.test(body.install_id || "")) throw new Error("install_id");
  return body;
}

async function ping(request, env) {
  const body = await readBody(request);
  const today = new Date().toISOString().slice(0, 10);
  const country = request.cf?.country || "XX";
  await env.DB.prepare(
    `INSERT INTO installs (install_id, country, version, os, first_seen, last_seen)
     VALUES (?1, ?2, ?3, ?4, ?5, ?5)
     ON CONFLICT(install_id) DO UPDATE SET
       country = excluded.country, version = excluded.version,
       os = excluded.os, last_seen = excluded.last_seen`
  ).bind(body.install_id, country, clean(body.version, 20), clean(body.os, 40), today).run();
  return new Response(null, { status: 204 });
}

async function feedback(request, env) {
  const body = await readBody(request);
  const rating = Number(body.rating);
  if (!Number.isInteger(rating) || rating < 1 || rating > 5) throw new Error("rating");
  const today = new Date().toISOString().slice(0, 10);
  const { n } = await env.DB.prepare(
    "SELECT COUNT(*) AS n FROM feedback WHERE install_id = ?1 AND created_at >= ?2"
  ).bind(body.install_id, today).first();
  if (n >= MAX_FEEDBACK_PER_DAY) return new Response(null, { status: 429 });
  await env.DB.prepare(
    `INSERT INTO feedback (install_id, version, country, rating, text, created_at)
     VALUES (?1, ?2, ?3, ?4, ?5, ?6)`
  ).bind(body.install_id, clean(body.version, 20), request.cf?.country || "XX",
         rating, clean(body.text, 2000), new Date().toISOString()).run();
  return new Response(null, { status: 204 });
}

async function stats(request, env) {
  const auth = request.headers.get("Authorization") || "";
  if (!env.ADMIN_TOKEN || auth !== `Bearer ${env.ADMIN_TOKEN}`) {
    return new Response("Unauthorized", { status: 401 });
  }
  const since = (days) => new Date(Date.now() - days * 864e5).toISOString().slice(0, 10);
  const all = (sql, ...args) => env.DB.prepare(sql).bind(...args).all().then((r) => r.results);
  const [countries, versions, totals, ratings, recent] = await Promise.all([
    all(`SELECT country, COUNT(*) AS installs,
                SUM(last_seen >= ?1) AS active_30d
         FROM installs GROUP BY country ORDER BY installs DESC`, since(30)),
    all(`SELECT version, COUNT(*) AS installs FROM installs
         WHERE last_seen >= ?1 GROUP BY version ORDER BY installs DESC`, since(30)),
    all(`SELECT COUNT(*) AS installs, SUM(last_seen >= ?1) AS active_7d,
                SUM(last_seen >= ?2) AS active_30d FROM installs`, since(7), since(30)),
    all(`SELECT rating, COUNT(*) AS n FROM feedback GROUP BY rating ORDER BY rating`),
    all(`SELECT created_at, version, country, rating, text FROM feedback
         ORDER BY created_at DESC LIMIT 50`),
  ]);
  return Response.json({ totals: totals[0], countries, versions, ratings, recent_feedback: recent });
}
