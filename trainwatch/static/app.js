'use strict';
/* trainwatch web UI — без сборки и внешних зависимостей. */

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const store = {
  get(k, d) { try { const v = localStorage.getItem('tw:' + k); return v === null ? d : JSON.parse(v); } catch (_) { return d; } },
  set(k, v) { try { localStorage.setItem('tw:' + k, JSON.stringify(v)); } catch (_) { /* приватный режим */ } },
};

const S = {
  state: null,
  feedKind: '',
  feedOldest: null,
  histories: {},          // watchId -> {key, rows}
  ranges: store.get('ranges', {}),
  reg: null,
  pushSub: null,
  shownAlerts: new Set(),
  online: null,          // null — ещё подключаемся
  checking: new Set(),
};

async function api(path, opts = {}) {
  const init = { method: opts.method || 'GET', headers: {}, credentials: 'include' };
  if (opts.body !== undefined) { init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(opts.body); }
  const r = await fetch(path, init);
  let data = null;
  try { data = await r.json(); } catch (_) { /* пусто */ }
  if (!r.ok) throw new Error((data && data.detail) || `HTTP ${r.status}`);
  return data;
}

function toast(msg, ms = 3500) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove('show'), ms);
}

/* ---------------- время и числа ---------------- */
function plural(n, one, few, many) {
  const n10 = n % 10, n100 = n % 100;
  if (n10 === 1 && n100 !== 11) return one;
  if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) return few;
  return many;
}
const seats = (n) => `${n} ${plural(n, 'место', 'места', 'мест')}`;
const pad = (n) => String(n).padStart(2, '0');
const fmtTime = (iso) => { const d = new Date(iso); return `${pad(d.getHours())}:${pad(d.getMinutes())}`; };
const fmtDT = (iso) => { const d = new Date(iso); return `${pad(d.getDate())}.${pad(d.getMonth() + 1)} ${fmtTime(iso)}`; };
function fmtKZ(iso) { // время отправления — как на сайте, UTC+5
  const d = new Date(new Date(iso).getTime() + 5 * 3600e3);
  const months = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
  return `${d.getUTCDate()} ${months[d.getUTCMonth()]} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
}
function ago(iso) {
  if (!iso) return 'никогда';
  const s = Math.max(0, Math.round((Date.now() - new Date(iso)) / 1000));
  if (s < 60) return 'только что';
  if (s < 3600) return `${Math.floor(s / 60)} мин назад`;
  if (s < 86400) return `${Math.floor(s / 3600)} ч ${Math.floor(s % 3600 / 60)} мин назад`;
  return fmtDT(iso);
}
function dur(sec) {
  sec = Math.max(0, Math.round(sec));
  const d = Math.floor(sec / 86400), h = Math.floor(sec % 86400 / 3600), m = Math.floor(sec % 3600 / 60), s = sec % 60;
  if (d) return `${d} д ${h} ч`;
  if (h) return `${h} ч ${pad(m)} мин`;
  return `${m}:${pad(s)}`;
}

/* ---------------- данные ---------------- */
let refreshTimer = null;
function scheduleRefresh(ms = 250) {
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(refresh, ms);
}
async function refresh() {
  try {
    S.state = await api('/api/state');
    renderAll();
  } catch (e) {
    console.warn('state', e);
  }
}

/* ---------------- отрисовка ---------------- */
function renderAll() {
  renderChannels();
  renderHero();
  renderSetup();
  renderWatches();
  tick();
}

function pushState() {
  if (!window.isSecureContext) return 'insecure';
  if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) return 'unsupported';
  if (Notification.permission === 'denied') return 'denied';
  return S.pushSub ? 'on' : 'off';
}

function renderChannels() {
  const st = S.state;
  const tg = st.telegram;
  const ps = pushState();
  const chips = [];
  chips.push(S.online === null ? '<span class="chip"><span class="dot"></span>подключение…</span>'
    : `<span class="chip ${S.online ? 'ok' : 'bad'}"><span class="dot"></span>${S.online ? 'онлайн' : 'нет связи'}</span>`);
  chips.push(`<span class="chip"><span class="dot" style="background:var(--accent)"></span>раз в ${st.server.interval_minutes} мин</span>`);
  const pushTxt = { on: 'Push: вкл', off: 'Push: выкл', denied: 'Push: запрещён', insecure: 'Push: нужен localhost', unsupported: 'Push: не поддерживается' }[ps];
  chips.push(`<button class="chip ${ps === 'on' ? 'ok' : 'warn'}" data-open-settings><span class="dot"></span>${pushTxt}</button>`);
  let tgCls = 'warn', tgTxt = 'Telegram: не настроен';
  if (!tg.enabled) { tgCls = ''; tgTxt = 'Telegram: выкл'; }
  else if (tg.configured && tg.last_error) { tgCls = 'bad'; tgTxt = 'Telegram: ошибка'; }
  else if (tg.configured) { tgCls = 'ok'; tgTxt = `Telegram${tg.bot_username ? ': @' + esc(tg.bot_username) : ''}`; }
  if (tg.queue > 0 && tg.configured) tgTxt += ` · в очереди ${tg.queue}`;
  chips.push(`<button class="chip ${tgCls}" data-open-settings title="${esc(tg.last_error || '')}"><span class="dot"></span>${tgTxt}</button>`);
  $('#channels').innerHTML = chips.join('');
}

function activeFinds() {
  const items = [];
  for (const w of S.state.watches) {
    if (w.status === 'finished') continue;
    for (const c of w.cars) {
      for (const cab of c.free_cabins) items.push({ w, kind: 'cabin', text: `Вагон <b>${esc(c.number)}</b> (${esc(c.car_type)}): места <b>${esc(cab.seats[0])}–${esc(cab.seats[cab.seats.length - 1])}</b>${cab.for_disabled ? ' ♿' : ''}`, key: `${w.id}:${c.number}:${cab.seats.join(',')}` });
      if (c.is_new) items.push({ w, kind: 'car', text: `Новый вагон <b>${esc(c.number)}</b> (${esc(c.car_type)}): ${seats(c.free_seats)}`, key: `${w.id}:new:${c.number}` });
    }
  }
  return items;
}

function renderHero() {
  const items = activeFinds();
  const key = items.map((i) => i.key).sort().join('|');
  const hidden = store.get('heroDismissed', '') === key;
  if (!items.length || hidden) { $('#hero').innerHTML = ''; return; }
  const hasCabin = items.some((i) => i.kind === 'cabin');
  const hasCar = items.some((i) => i.kind === 'car');
  const title = hasCabin && hasCar ? 'Есть свободная кабинка и новый вагон!' : hasCabin ? 'Есть свободная кабинка — 4 места!' : 'Появился новый вагон!';
  const byWatch = new Map();
  items.forEach((i) => { if (!byWatch.has(i.w.id)) byWatch.set(i.w.id, { w: i.w, list: [] }); byWatch.get(i.w.id).list.push(i); });
  const blocks = [...byWatch.values()].map(({ w, list }) => `
      <div><small>${esc(w.title)}${w.route ? ' · ' + esc(w.route) : ''}</small>
      <ul class="hero-list">${list.map((i) => `<li>${i.kind === 'cabin' ? '🟢' : '🆕'} ${i.text}</li>`).join('')}</ul>
      <a class="btn buy" href="${esc(w.url)}" target="_blank" rel="noopener">🎫 Купить на сайте</a></div>`).join('<hr style="border-color:rgba(255,255,255,.3)">');
  $('#hero').innerHTML = `
    <div class="hero" role="alert">
      <h2>🚨 ${title}</h2>
      ${blocks}
      <div style="margin-top:10px"><button class="btn ghost small" id="hero-hide" data-key="${esc(key)}">Скрыть до следующей находки</button></div>
    </div>`;
}

function renderSetup() {
  const st = S.state;
  const ps = pushState();
  const steps = [
    { done: st.watches.length > 0, title: 'Добавьте поезд для отслеживания', action: '<button class="btn small primary" data-add>＋ Добавить поезд</button>' },
    {
      done: ps === 'on',
      title: 'Push-уведомления в этом браузере',
      action: ps === 'off' ? '<button class="btn small primary" data-push-on>Включить</button>'
        : ps === 'denied' ? '<span class="hint">Разрешите уведомления для этого сайта в настройках браузера (значок замка в адресной строке)</span>'
          : ps === 'insecure' ? `<span class="hint">Откройте <a href="http://localhost:${location.port}/">http://localhost:${location.port}</a> — push работает только на localhost или HTTPS</span>`
            : ps === 'unsupported' ? '<span class="hint">Браузер не поддерживает Web Push</span>' : '<span class="st">✓ включено</span>',
    },
    { done: st.telegram.configured && st.telegram.enabled && !st.telegram.last_error, optional: true, title: 'Telegram (необязательно)', action: '<button class="btn small" data-open-settings>Настроить</button>' },
  ];
  const need = steps.filter((s) => !s.done && !(s.optional && store.get('skipTelegram', false)));
  if (!need.length) { $('#setup').innerHTML = ''; return; }
  $('#setup').innerHTML = `
    <div class="panel setup">
      <h2>Настройка уведомлений</h2>
      <ul class="setup-list">
        ${steps.map((s) => `<li class="${s.done ? 'done' : ''}"><span>${s.done ? '✅' : '⬜'} ${s.title}</span><span>${s.done ? '' : s.action}${!s.done && s.optional ? ' <button class="btn small ghost" data-skip-tg>Не нужно</button>' : ''}</span></li>`).join('')}
      </ul>
    </div>`;
}

const STATUS = {
  ok: ['ok', '● Работает'], error: ['error', '⚠ Ошибки проверки'], paused: ['paused', '⏸ На паузе'],
  finished: ['finished', '🏁 Поезд ушёл'], checking: ['checking', '⟳ Проверяю…'], starting: ['starting', '… Первая проверка'],
};

function renderWatches() {
  const ws = S.state.watches;
  const root = $('#watches');
  if (!ws.length) {
    root.innerHTML = `
      <div class="panel empty">
        <div class="big">🚆</div>
        <h2>Пока ничего не отслеживается</h2>
        <p>Добавьте ссылку на страницу выбора вагона с bilet.railways.kz — сервис будет проверять её и сообщит, когда появится новый вагон или освободится целая кабинка.</p>
        <button class="btn primary" data-add>＋ Добавить поезд</button>
      </div>`;
    return;
  }
  // сохраняем раскрытые <details>, чтобы обновление не сворачивало их
  const open = new Set($$('details[data-keep]').filter((d) => d.open).map((d) => d.dataset.keep));
  root.innerHTML = ws.map(watchCard).join('');
  $$('details[data-keep]').forEach((d) => { if (open.has(d.dataset.keep)) d.open = true; });
  ws.forEach((w) => loadHistory(w));
}

function watchCard(w) {
  const [cls, label] = STATUS[w.status] || ['paused', w.status];
  const t = w.totals;
  const dep = w.departure ? `🕒 ${w.departure_text ? esc(w.departure_text) : fmtKZ(w.departure)} <span class="muted" data-depart="${esc(w.departure)}"></span>` : '';
  const cars = w.cars.map((c) => carTile(c)).join('') + w.absent_known.map((a) => `
      <div class="car absent"><div class="car-top"><span class="car-no">Вагон ${esc(a.number)}${a.is_new ? '<span class="tag new">НОВЫЙ</span>' : ''}</span>
      <span class="car-type">мест нет</span></div><div class="car-meta"><span>был в продаже, сейчас распродан</span></div></div>`).join('');
  const range = S.ranges[w.id] ?? 48;
  const busy = S.checking.has(w.id) || w.status === 'checking';
  return `
  <article class="panel watch" id="w-${esc(w.id)}">
    <div class="watch-head">
      <div>
        <span class="train-badge">${esc(w.train)}</span><span class="watch-title">${esc(w.route || w.title)}</span>
        <div class="watch-sub">
          ${w.name ? `<span>${esc(w.name)}</span>` : ''}
          ${dep ? `<span>${dep}</span>` : ''}
          ${w.carrier ? `<span>${esc(w.carrier)}</span>` : ''}
          <span class="status ${cls}">${label}</span>
        </div>
      </div>
      <div class="watch-actions">
        <button class="btn small" data-check="${esc(w.id)}" ${busy || !w.enabled || w.status === 'finished' ? 'disabled' : ''}>${busy ? '<span class="spin">⟳</span>' : '⟳'} Проверить</button>
        ${w.status !== 'finished' ? `<button class="btn small" data-toggle="${esc(w.id)}" data-enabled="${w.enabled}">${w.enabled ? '⏸ Пауза' : '▶ Возобновить'}</button>` : ''}
        <a class="btn small" href="${esc(w.url)}" target="_blank" rel="noopener">↗ Сайт</a>
        <button class="btn small ghost" data-rename="${esc(w.id)}" title="Переименовать" aria-label="Переименовать">✎</button>
        <button class="btn small ghost danger" data-delete="${esc(w.id)}" title="Удалить" aria-label="Удалить">🗑</button>
      </div>
    </div>

    <div class="timing">
      <span>Проверено: <b data-ago="${esc(w.last_check_at || '')}">${ago(w.last_check_at)}</b></span>
      ${w.next_check_at ? `<span>Следующая через <b class="num" data-next="${esc(w.next_check_at)}" data-from="${esc(w.last_check_at || '')}"></b></span>
      <div class="progress"><i data-progress="${esc(w.id)}" style="width:0"></i></div>` : ''}
      ${w.started_at ? `<span class="hint">отслеживается с ${fmtDT(w.started_at)}</span>` : ''}
    </div>
    ${w.consecutive_failures ? `<div class="err-line">⚠ Ошибок подряд: ${w.consecutive_failures}. ${esc(w.last_error)} — повторю автоматически.</div>` : ''}
    ${w.pending_empty ? `<div class="err-line">Сайт ответил «ничего не найдено» — перепроверяю, прежде чем поверить.</div>` : ''}

    <div class="kpis">
      <div class="kpi"><div class="v">${t.free}</div><div class="l">${plural(t.free, 'свободное место', 'свободных места', 'свободных мест')}</div></div>
      <div class="kpi"><div class="v">${t.cars}</div><div class="l">${plural(t.cars, 'вагон', 'вагона', 'вагонов')} с местами</div></div>
      <div class="kpi ${t.cabins ? 'hot' : ''}"><div class="v">${t.cabins}</div><div class="l">${plural(t.cabins, 'свободная кабинка', 'свободные кабинки', 'свободных кабинок')} (4 места)</div></div>
      <div class="kpi ${t.new_cars ? 'hot' : ''}"><div class="v">${t.new_cars}</div><div class="l">новых вагонов · всего известно ${t.known}</div></div>
    </div>

    ${w.cars.length || w.absent_known.length ? `
      <h3 class="sec">Вагоны</h3>
      <div class="cars">${cars}</div>
      <div class="legend"><span><i style="background:var(--seat-free)"></i>свободно</span><span><i style="background:var(--seat-taken)"></i>занято</span>
      <span><i style="background:var(--good)"></i>кабинка свободна целиком</span><span>верхний ряд — верхние полки, снизу — боковые</span></div>`
      : `<p class="hint">${w.status === 'starting' ? 'Жду первую проверку…' : 'Свободных мест в поезде нет (или продажа ещё не открыта).'}</p>`}

    <div class="chart-head">
      <h3 class="sec">Свободные места во времени</h3>
      <div class="seg" data-range-for="${esc(w.id)}">
        ${[[24, '24 ч'], [72, '3 дня'], [168, 'неделя'], [0, 'всё']].map(([h, l]) => `<button data-h="${h}" class="${range === h ? 'on' : ''}">${l}</button>`).join('')}
      </div>
    </div>
    <div class="chart-wrap" data-chart="${esc(w.id)}"><div class="empty-chart">Загрузка…</div></div>
    <details data-keep="tbl-${esc(w.id)}"><summary class="hint">Последние проверки (таблица)</summary><div data-table="${esc(w.id)}"></div></details>
  </article>`;
}

function seatMap(c) {
  if (!c.layout_cabins.length) return '';
  const free = new Set(c.free_numbers);
  const full = new Set(c.free_cabins.map((x) => x.seats.join(',')));
  const sq = (n, kind) => `<i class="s ${free.has(n) ? 'f' : ''}" title="Место ${esc(n)} — ${kind}, ${free.has(n) ? 'свободно' : 'занято'}"></i>`;
  const lower = (n) => Number(n) % 2 === 1;
  return `<div class="seatmap" aria-label="Схема вагона ${esc(c.number)}">${c.layout_cabins.map((cab, i) => {
    // в кабинке: верхние (чётные) сверху, нижние (нечётные) снизу
    const ordered = cab.length === 4 ? [cab[1], cab[3], cab[0], cab[2]] : cab;
    const side = c.layout_sides[i] || [];
    return `<div class="cabcol"><div class="cab ${full.has(cab.join(',')) ? 'full' : ''}">${ordered.map((n) => sq(n, lower(n) ? 'нижнее' : 'верхнее')).join('')}</div>
      ${side.length ? `<div class="side">${side.map((n) => sq(n, lower(n) ? 'боковое нижнее' : 'боковое верхнее')).join('')}</div>` : ''}</div>`;
  }).join('')}</div>`;
}

function carTile(c) {
  const cab = c.free_cabins.length;
  return `
    <div class="car ${cab ? 'has-cabin' : ''} ${c.is_new ? 'is-new' : ''}">
      <div class="car-top">
        <div><div class="car-no">Вагон ${esc(c.number)}${c.is_new ? '<span class="tag new">НОВЫЙ</span>' : ''}${cab ? `<span class="tag cab">${cab} ${plural(cab, 'кабинка', 'кабинки', 'кабинок')}</span>` : ''}</div>
        <div class="car-type">${esc(c.car_type)} ${esc(c.service_class)}</div></div>
        <div class="car-free">${c.free_seats}<small>${plural(c.free_seats, 'место', 'места', 'мест')}</small></div>
      </div>
      ${seatMap(c)}
      ${cab ? `<div class="cabins-free">Кабинки целиком: ${c.free_cabins.map((x) => `${esc(x.seats[0])}–${esc(x.seats[x.seats.length - 1])}${x.for_disabled ? ' ♿' : ''}`).join(', ')}</div>` : ''}
      <div class="car-meta"><span>${esc(c.price || '')}</span>${c.is_new && c.first_seen ? `<span>появился ${fmtDT(c.first_seen)}</span>` : ''}</div>
    </div>`;
}

/* ---------------- обновление таймеров ---------------- */
function tick() {
  const now = Date.now();
  $$('[data-next]').forEach((el) => {
    const next = new Date(el.dataset.next).getTime();
    const left = (next - now) / 1000;
    el.textContent = left > 0 ? dur(left) : 'сейчас…';
    const from = el.dataset.from ? new Date(el.dataset.from).getTime() : null;
    const bar = el.closest('.timing').querySelector('[data-progress]');
    if (bar && from) bar.style.width = `${Math.min(100, Math.max(0, (now - from) / (next - from) * 100))}%`;
  });
  $$('[data-ago]').forEach((el) => { if (el.dataset.ago) el.textContent = ago(el.dataset.ago); });
  $$('[data-depart]').forEach((el) => {
    const left = (new Date(el.dataset.depart) - now) / 1000;
    el.textContent = left > 0 ? `· через ${dur(left)}` : '· отправился';
  });
}
setInterval(tick, 1000);

/* ---------------- график ---------------- */
async function loadHistory(w, force = false) {
  const hours = S.ranges[w.id] ?? 48;
  const key = `${hours}|${w.last_check_at}`;
  const cached = S.histories[w.id];
  if (!force && cached && cached.key === key) { drawChart(w.id, cached.rows, hours); return; }
  try {
    const rows = await api(`/api/history/${encodeURIComponent(w.id)}?hours=${hours}`);
    S.histories[w.id] = { key, rows };
    drawChart(w.id, rows, hours);
  } catch (e) {
    const el = $(`[data-chart="${CSS.escape(w.id)}"]`);
    if (el) el.innerHTML = `<div class="empty-chart">Не удалось загрузить историю: ${esc(e.message)}</div>`;
  }
}

function niceMax(v) {
  if (v <= 4) return 4;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= v) return m * p;
  return v;
}

function drawChart(id, rows, hours) {
  const wrap = $(`[data-chart="${CSS.escape(id)}"]`);
  const tbl = $(`[data-table="${CSS.escape(id)}"]`);
  if (!wrap) return;
  if (tbl) {
    const last = rows.slice(-30).reverse();
    tbl.innerHTML = last.length ? `<table style="width:100%;font-size:12px;border-collapse:collapse"><thead><tr style="text-align:left;color:var(--muted)"><th>Время</th><th>Свободно</th><th>Вагонов</th><th>Кабинок</th><th>Итог</th></tr></thead><tbody>${last.map((r) => `<tr><td>${fmtDT(r.at)}</td><td>${r.total_free ?? '—'}</td><td>${r.cars ?? '—'}</td><td>${r.cabins ?? '—'}</td><td>${r.ok ? 'ок' : esc(r.error || 'ошибка')}</td></tr>`).join('')}</tbody></table>` : '<p class="hint">Проверок ещё не было.</p>';
  }
  const pts = rows.filter((r) => r.ok && r.total_free !== null).map((r) => ({ t: new Date(r.at).getTime(), v: r.total_free, cab: r.cabins || 0, cars: r.cars }));
  const fails = rows.filter((r) => !r.ok).map((r) => ({ t: new Date(r.at).getTime(), err: r.error }));
  if (pts.length < 2) {
    wrap.innerHTML = `<div class="empty-chart">${pts.length ? 'Нужно хотя бы две проверки, чтобы построить график.' : 'Данных за этот период нет.'}</div>`;
    return;
  }
  const W = Math.max(280, wrap.clientWidth || 600), H = 180, m = { l: 34, r: 12, t: 10, b: 22 };
  const now = Date.now();
  const t0 = hours ? Math.min(pts[0].t, now - hours * 3600e3) : pts[0].t;
  const t1 = Math.max(pts[pts.length - 1].t, hours ? now : pts[pts.length - 1].t);
  const tmin = hours ? Math.max(t0, pts[0].t) : t0;
  const vmax = niceMax(Math.max(...pts.map((p) => p.v)) * 1.1 || 1);
  const x = (t) => m.l + (t - tmin) / Math.max(1, t1 - tmin) * (W - m.l - m.r);
  const y = (v) => m.t + (1 - v / vmax) * (H - m.t - m.b);

  // ступенчатая линия: число мест меняется скачками между проверками
  let d = `M${x(pts[0].t)},${y(pts[0].v)}`;
  for (let i = 1; i < pts.length; i++) d += `H${x(pts[i].t)}V${y(pts[i].v)}`;
  const lastX = x(Math.min(now, t1));
  d += `H${lastX}`;
  const area = `${d}V${y(0)}H${x(pts[0].t)}Z`;

  const yt = [0, vmax / 4, vmax / 2, vmax * 3 / 4, vmax];
  const span = t1 - tmin;
  const nx = Math.max(2, Math.min(6, Math.floor((W - m.l) / 90)));
  const xt = Array.from({ length: nx }, (_, i) => tmin + span * i / (nx - 1));
  let prevLabel = '';
  const xl = (t) => span > 36 * 3600e3 ? fmtDT(new Date(t).toISOString()).slice(0, 5) + ' ' + fmtTime(new Date(t).toISOString()) : fmtTime(new Date(t).toISOString());

  wrap.innerHTML = `
    <svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="График свободных мест: сейчас ${pts[pts.length - 1].v}">
      <g class="grid">${yt.map((v) => `<line x1="${m.l}" x2="${W - m.r}" y1="${y(v)}" y2="${y(v)}"/>`).join('')}</g>
      <g class="axis">
        ${yt.map((v) => `<text x="${m.l - 6}" y="${y(v) + 4}" text-anchor="end">${Math.round(v)}</text>`).join('')}
        ${xt.map((t, i) => { const l = xl(t); if (l === prevLabel) return ''; prevLabel = l; return `<text x="${x(t)}" y="${H - 4}" text-anchor="${i === 0 ? 'start' : i === nx - 1 ? 'end' : 'middle'}">${l}</text>`; }).join('')}
      </g>
      <path class="area" d="${area}"/>
      <path class="line" d="${d}"/>
      ${fails.filter((f) => f.t >= tmin).map((f) => `<line class="fail" x1="${x(f.t)}" x2="${x(f.t)}" y1="${y(0) - 6}" y2="${y(0)}"/>`).join('')}
      ${pts.filter((p) => p.cab > 0).map((p) => `<circle class="cabin-dot" cx="${x(p.t)}" cy="${y(p.v)}" r="4.5"/>`).join('')}
      <line class="cross" y1="${m.t}" y2="${y(0)}" visibility="hidden"/>
      <circle class="hover-dot" r="4.5" visibility="hidden"/>
      <rect x="${m.l}" y="0" width="${W - m.l - m.r}" height="${H}" fill="transparent" class="hit"/>
    </svg>
    <div class="legend">${pts.some((p) => p.cab) ? '<span><i style="background:var(--good);border-radius:50%"></i>в этот момент была свободная кабинка</span>' : ''}
    ${fails.length ? '<span><i style="background:var(--crit);width:2px"></i>проверка не удалась</span>' : ''}</div>`;

  const svg = wrap.querySelector('svg');
  const cross = svg.querySelector('.cross'), dot = svg.querySelector('.hover-dot');
  let tip = null;
  const hide = () => { cross.setAttribute('visibility', 'hidden'); dot.setAttribute('visibility', 'hidden'); if (tip) { tip.remove(); tip = null; } };
  svg.querySelector('.hit').addEventListener('pointermove', (e) => {
    const r = svg.getBoundingClientRect();
    const px = (e.clientX - r.left) * (W / r.width);
    let best = pts[0];
    for (const p of pts) if (Math.abs(x(p.t) - px) < Math.abs(x(best.t) - px)) best = p;
    const cx = x(best.t), cy = y(best.v);
    cross.setAttribute('x1', cx); cross.setAttribute('x2', cx); cross.setAttribute('visibility', 'visible');
    dot.setAttribute('cx', cx); dot.setAttribute('cy', cy); dot.setAttribute('visibility', 'visible');
    if (!tip) { tip = document.createElement('div'); tip.className = 'tooltip'; wrap.appendChild(tip); }
    tip.innerHTML = `${fmtDT(new Date(best.t).toISOString())}<br><b>${seats(best.v)}</b> в ${best.cars} ${plural(best.cars, 'вагоне', 'вагонах', 'вагонах')}${best.cab ? `<br>🛏 свободных кабинок: ${best.cab}` : ''}`;
    tip.style.left = `${cx * r.width / W}px`;
    tip.style.top = `${cy * r.height / H}px`;
  });
  svg.querySelector('.hit').addEventListener('pointerleave', hide);
}

let resizeT;
window.addEventListener('resize', () => {
  clearTimeout(resizeT);
  resizeT = setTimeout(() => S.state && S.state.watches.forEach((w) => S.histories[w.id] && drawChart(w.id, S.histories[w.id].rows, S.ranges[w.id] ?? 48)), 200);
});

/* ---------------- лента событий ---------------- */
const ICON = { alert: '🚨', report: '📋', error: '⚠️', recovered: '✅', finished: '🏁', info: 'ℹ️' };

function feedItem(e, flash = false) {
  const full = e.data && e.data.text;
  return `<li class="${esc(e.kind)} ${flash ? 'flash' : ''}" data-ev="${e.id}">
    <span class="ico">${ICON[e.kind] || '•'}</span>
    <div><div class="t">${esc(String(e.title || '').replace(/^\p{Extended_Pictographic}️?\s*/u, ''))}</div>
    <div class="b">${esc(e.body)}</div>
    <div class="w">${fmtDT(e.at)}${e.url ? ` · <a href="${esc(e.url)}" target="_blank" rel="noopener">сайт</a>` : ''}</div>
    ${full && full !== e.body ? `<details><summary>Полный текст</summary><pre>${esc(full)}</pre></details>` : ''}</div></li>`;
}

async function loadFeed(reset = true) {
  const params = new URLSearchParams({ limit: 40 });
  if (S.feedKind) params.set('kinds', S.feedKind);
  if (!reset && S.feedOldest) params.set('before', S.feedOldest);
  try {
    const list = await api(`/api/events?${params}`);
    const ol = $('#feed');
    if (reset) ol.innerHTML = '';
    ol.insertAdjacentHTML('beforeend', list.map((e) => feedItem(e)).join(''));
    if (list.length) S.feedOldest = list[list.length - 1].id;
    if (reset && !list.length) ol.innerHTML = '<li class="feed-empty">Событий пока нет</li>';
    $('#feed-more').hidden = list.length < 40;
  } catch (e) {
    console.warn('feed', e);
  }
}

function pushToFeed(e) {
  if (S.feedKind && !S.feedKind.split(',').includes(e.kind)) return;
  const ol = $('#feed');
  const empty = ol.querySelector('.feed-empty');
  if (empty) empty.remove();
  if (ol.querySelector(`[data-ev="${e.id}"]`)) return;
  ol.insertAdjacentHTML('afterbegin', feedItem(e, true));
}

/* ---------------- тревога: оверлей + звук ---------------- */
let audioCtx = null;
function unlockAudio() {
  try {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === 'suspended') audioCtx.resume();
  } catch (_) { /* нет WebAudio */ }
}
document.addEventListener('pointerdown', unlockAudio, { once: false, passive: true });
document.addEventListener('keydown', unlockAudio, { passive: true });

function siren() {
  if (!audioCtx || audioCtx.state !== 'running' || !store.get('sound', true)) return false;
  const t = audioCtx.currentTime;
  for (let i = 0; i < 6; i++) {
    const o = audioCtx.createOscillator(), g = audioCtx.createGain();
    o.type = 'square';
    o.frequency.value = i % 2 ? 660 : 990;
    g.gain.setValueAtTime(0.0001, t + i * 0.35);
    g.gain.exponentialRampToValueAtTime(0.25, t + i * 0.35 + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, t + i * 0.35 + 0.3);
    o.connect(g).connect(audioCtx.destination);
    o.start(t + i * 0.35);
    o.stop(t + i * 0.35 + 0.32);
  }
  return true;
}

let alarmTimer = null, titleTimer = null;
function showAlarm(e) {
  if (e.id && S.shownAlerts.has(e.id)) return;
  if (e.id) S.shownAlerts.add(e.id);
  $('#alarm-title').textContent = (e.title || '').replace(/^🚨\s*/, '').split(' · ')[0];
  $('#alarm-train').textContent = (e.data && e.data.watch_title) || '';
  $('#alarm-body').textContent = e.body || '';
  const buy = $('#alarm-buy');
  buy.hidden = !e.url;
  if (e.url) buy.href = e.url;
  $('#alarm').hidden = false;
  const played = siren();
  $('#alarm-note').textContent = played ? '' : (store.get('sound', true) ? 'Звук не сыграл: браузер разрешает звук только после клика по странице.' : 'Звук выключен в настройках.');
  let n = 0;
  clearInterval(alarmTimer);
  alarmTimer = setInterval(() => { if (++n > 15 || $('#alarm').hidden) clearInterval(alarmTimer); else siren(); }, 4000);
  const orig = 'trainwatch';
  let on = false;
  clearInterval(titleTimer);
  titleTimer = setInterval(() => { document.title = (on = !on) ? '🚨 СВОБОДНО! 🚨' : orig; }, 900);
  // вкладка открыта, но push не включён — покажем системное уведомление средствами страницы
  if (!S.pushSub && 'Notification' in window && Notification.permission === 'granted' && document.hidden) {
    try { new Notification(e.title, { body: e.body, icon: '/static/icon-192.png', requireInteraction: true, tag: 'alert-' + e.id }); } catch (_) { /* мобильные браузеры */ }
  }
}
function hideAlarm() {
  $('#alarm').hidden = true;
  clearInterval(alarmTimer);
  clearInterval(titleTimer);
  document.title = 'trainwatch';
}

const TEST_ALARM = {
  id: null, kind: 'alert', title: '🚨 ОСВОБОДИЛАСЬ КАБИНКА — 4 МЕСТА! (тест)',
  body: 'Вагон 10 (Плацкартный): места 13–16\nВагон 06 (Плацкартный): места 21–24',
  url: 'https://bilet.railways.kz', data: { watch_title: 'Так будет выглядеть настоящая тревога' },
};

/* ---------------- SSE ---------------- */
let es = null;
function connect() {
  es = new EventSource('/api/stream');
  es.onopen = () => {
    S.online = true;
    $('#conn-lost').hidden = true;
    refresh();
    loadFeed(true);
  };
  es.onerror = () => {
    S.online = false;
    $('#conn-lost').hidden = false;
    if (S.state) renderChannels();
  };
  es.onmessage = (m) => {
    let msg;
    try { msg = JSON.parse(m.data); } catch (_) { return; }
    if (msg.type === 'state') scheduleRefresh();
    if (msg.type === 'event') {
      pushToFeed(msg.event);
      if (msg.event.kind === 'alert') showAlarm(msg.event);
      scheduleRefresh(100);
    }
  };
}

/* ---------------- Web Push ---------------- */
function b64urlToBytes(s) {
  const p = '='.repeat((4 - s.length % 4) % 4);
  const raw = atob((s + p).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}
function bytesToB64url(buf) {
  return btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function initServiceWorker() {
  if (!('serviceWorker' in navigator) || !window.isSecureContext) return;
  try {
    S.reg = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
    await navigator.serviceWorker.ready;
    S.pushSub = await S.reg.pushManager.getSubscription();
    navigator.serviceWorker.addEventListener('message', (m) => {
      const d = m.data || {};
      if (d.type === 'push' && d.payload && d.payload.kind === 'alert' && !S.online) {
        showAlarm({ id: d.payload.event_id, title: d.payload.title, body: d.payload.body, url: d.payload.url, data: {} });
      }
      if (d.type === 'focus-event' && d.eventId) {
        const li = $(`[data-ev="${d.eventId}"]`);
        if (li) { li.scrollIntoView({ behavior: 'smooth', block: 'center' }); li.classList.add('flash'); }
      }
    });
  } catch (e) {
    console.warn('SW', e);
  }
}

async function syncPushSubscription() {
  // сервер мог потерять подписку (новая база) или сменить ключ — синхронизируем
  if (!S.pushSub || !S.state || !S.state.push.public_key) return;
  const key = S.pushSub.options && S.pushSub.options.applicationServerKey;
  if (key && bytesToB64url(key) !== S.state.push.public_key) {
    await S.pushSub.unsubscribe();
    S.pushSub = null;
    await enablePush(true);
    return;
  }
  await api('/api/push/subscribe', { method: 'POST', body: { subscription: S.pushSub.toJSON() } }).catch(() => {});
}

async function enablePush(silent = false) {
  const st = pushState();
  if (st === 'insecure') { toast('Push работает только на http://localhost или по HTTPS'); return false; }
  if (st === 'unsupported') { toast('Этот браузер не поддерживает Web Push'); return false; }
  try {
    if (!S.reg) await initServiceWorker();
    const perm = await Notification.requestPermission();
    if (perm !== 'granted') { if (!silent) toast('Уведомления запрещены. Разрешите их для этого сайта в настройках браузера.', 6000); renderAll(); return false; }
    S.pushSub = await S.reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64urlToBytes(S.state.push.public_key) });
    await api('/api/push/subscribe', { method: 'POST', body: { subscription: S.pushSub.toJSON() } });
    if (!silent) toast('Push-уведомления включены ✓');
    await refresh();
    renderPushBox();
    return true;
  } catch (e) {
    console.warn(e);
    toast(`Не удалось включить push: ${e.message}. В Brave включите «Google services for push messaging».`, 8000);
    return false;
  }
}

async function disablePush() {
  if (!S.pushSub) return;
  await api('/api/push/unsubscribe', { method: 'POST', body: { endpoint: S.pushSub.endpoint } }).catch(() => {});
  await S.pushSub.unsubscribe().catch(() => {});
  S.pushSub = null;
  toast('Push-уведомления в этом браузере выключены');
  await refresh();
  renderPushBox();
}

function renderPushBox() {
  const st = pushState();
  const subs = S.state ? S.state.push.subscriptions : 0;
  const box = $('#push-box');
  if (!box) return;
  const txt = {
    on: '✅ Включены в этом браузере. Уведомления приходят, даже если вкладка закрыта (браузер должен быть запущен).',
    off: 'Выключены в этом браузере.',
    denied: '⛔ Браузер запретил уведомления для этого сайта — разрешите их через значок замка в адресной строке.',
    insecure: `⚠ Страница открыта не через localhost. Push работает только на <a href="http://localhost:${location.port}/">http://localhost:${location.port}</a> или по HTTPS.`,
    unsupported: 'Этот браузер не поддерживает Web Push.',
  }[st];
  box.innerHTML = `<p style="margin:0 0 8px">${txt} <span class="hint">Подписанных браузеров: ${subs}.</span></p>
    <div class="row" style="align-items:center">
      ${st === 'off' ? '<button type="button" class="btn primary" data-push-on>Включить уведомления</button>' : ''}
      ${st === 'on' ? '<button type="button" class="btn" data-push-test="alert">Тестовая тревога</button><button type="button" class="btn ghost" data-push-off>Выключить</button>' : ''}
    </div>`;
}

/* ---------------- диалоги ---------------- */
function openDialog(d) { if (!d.open) d.showModal(); }
$$('dialog [data-close]').forEach((b) => b.addEventListener('click', () => b.closest('dialog').close()));

// --- добавление поезда
let previewOk = false;
function resetAdd() {
  $('#form-add').reset();
  $('#add-preview').innerHTML = '';
  $('#btn-add-confirm').disabled = true;
  previewOk = false;
}
$('#form-add [name=url]').addEventListener('input', () => { previewOk = false; $('#btn-add-confirm').disabled = true; $('#add-preview').innerHTML = ''; });

$('#btn-preview').addEventListener('click', async () => {
  const f = $('#form-add');
  const btn = $('#btn-preview');
  btn.disabled = true;
  btn.innerHTML = '<span class="spin">⟳</span> Проверяю…';
  $('#add-preview').innerHTML = '';
  try {
    const p = await api('/api/watches/preview', { method: 'POST', body: { url: f.url.value, name: f.name.value } });
    const t = p.totals;
    $('#add-preview').innerHTML = `<div class="preview">
      ${p.exists ? '<div class="bad">Этот поезд уже отслеживается</div>' : '<div class="ok">✓ Ссылка работает</div>'}
      <div><b>${esc(p.train)}</b> ${esc(p.route || '')}</div>
      <div>${p.departure_text ? 'Отправление: ' + esc(p.departure_text) : p.departure ? 'Отправление: ' + fmtKZ(p.departure) : ''}</div>
      <div>${p.status === 'empty' ? 'Сейчас мест нет (или продажа ещё не открыта) — это нормально, сервис дождётся появления.' : `Сейчас: ${seats(t.free)} в ${t.cars} ${plural(t.cars, 'вагоне', 'вагонах', 'вагонах')} (${p.cars.map((c) => esc(c.number)).join(', ')}), свободных кабинок: ${t.cabins}`}</div>
    </div>`;
    previewOk = !p.exists;
    $('#btn-add-confirm').disabled = !previewOk;
  } catch (e) {
    $('#add-preview').innerHTML = `<div class="preview"><span class="bad">✗ ${esc(e.message)}</span></div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Проверить ссылку';
  }
});

$('#form-add').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  if (!previewOk) return;
  const f = ev.target;
  try {
    await api('/api/watches', { method: 'POST', body: { url: f.url.value, name: f.name.value } });
    $('#dlg-add').close();
    toast('Поезд добавлен — первая проверка уже идёт');
    refresh();
  } catch (e) {
    $('#add-preview').insertAdjacentHTML('beforeend', `<div class="preview"><span class="bad">✗ ${esc(e.message)}</span></div>`);
  }
});

// --- настройки
const NUM = ['check_interval_minutes', 'jitter_seconds', 'retry_delay_seconds', 'failure_alert_threshold', 'confirm_empty_checks'];
const BOOL = ['telegram_enabled', 'telegram_reports', 'quiet_reports', 'telegram_commands', 'push_reports'];

function syncQuietCheckbox() {
  const f = $('#form-settings');
  f.quiet_reports.disabled = !f.telegram_reports.checked;
  f.quiet_reports.closest('label').style.opacity = f.telegram_reports.checked ? '' : '.5';
}
$('#form-settings').telegram_reports.addEventListener('change', syncQuietCheckbox);
let settingsSnapshot = null;

async function openSettings() {
  const f = $('#form-settings');
  $('#settings-error').textContent = '';
  $('#tg-test-result').textContent = '';
  try {
    const s = await api('/api/settings');
    settingsSnapshot = s;
    NUM.forEach((k) => { f[k].value = s[k]; });
    BOOL.forEach((k) => { f[k].checked = !!s[k]; });
    syncQuietCheckbox();
    f.telegram_token.value = s.telegram_token_masked || '';
    f.telegram_chat_id.value = s.telegram_chat_id || '';
    $('#tg-env').hidden = !s.telegram_env;
    $('#sound-on').checked = store.get('sound', true);
    markPreset();
    renderPushBox();
    renderChats();
    openDialog($('#dlg-settings'));
  } catch (e) {
    toast('Не удалось загрузить настройки: ' + e.message);
  }
}

function renderChats() {
  const tg = S.state && S.state.telegram;
  const el = $('#tg-chats');
  if (!tg) return;
  const chats = tg.seen_chats || [];
  if (!tg.has_token) { el.innerHTML = 'Создайте бота у <a href="https://t.me/BotFather" target="_blank" rel="noopener">@BotFather</a> (/newbot), вставьте токен и сохраните. Затем напишите своему боту /start — chat_id появится здесь.'; return; }
  el.innerHTML = chats.length
    ? 'Писали боту: ' + chats.map((c) => `<button type="button" class="btn small chat-pick" data-chat="${esc(c.id)}">${esc(c.name)} · ${esc(c.id)}</button>`).join('')
    : `Напишите вашему боту${tg.bot_username ? ` <a href="https://t.me/${esc(tg.bot_username)}" target="_blank" rel="noopener">@${esc(tg.bot_username)}</a>` : ''} команду /start — chat_id появится здесь.`;
}

function markPreset() {
  const v = Number($('#form-settings').check_interval_minutes.value);
  $$('#interval-presets button').forEach((b) => b.classList.toggle('on', Number(b.dataset.v) === v));
  $('#interval-warn').classList.toggle('warn', v < 5);
}
$('#form-settings').check_interval_minutes.addEventListener('input', markPreset);
$('#interval-presets').addEventListener('click', (e) => {
  const b = e.target.closest('button');
  if (!b) return;
  $('#form-settings').check_interval_minutes.value = b.dataset.v;
  markPreset();
});
$('#sound-on').addEventListener('change', (e) => { store.set('sound', e.target.checked); if (e.target.checked) { unlockAudio(); siren(); } });

function collectSettings() {
  const f = $('#form-settings');
  const body = {};
  NUM.forEach((k) => { body[k] = Number(f[k].value); });
  BOOL.forEach((k) => { body[k] = f[k].checked; });
  const tok = f.telegram_token.value.trim();
  if (tok !== (settingsSnapshot.telegram_token_masked || '')) body.telegram_token = tok;   // пусто = удалить
  body.telegram_chat_id = f.telegram_chat_id.value.trim();
  return body;
}

$('#form-settings').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  try {
    settingsSnapshot = await api('/api/settings', { method: 'PUT', body: collectSettings() });
    $('#form-settings').telegram_token.value = settingsSnapshot.telegram_token_masked || '';
    $('#settings-error').textContent = '';
    toast('Настройки сохранены');
    await refresh();
    renderChats();
  } catch (e) {
    $('#settings-error').textContent = e.message;
  }
});

$('#btn-tg-test').addEventListener('click', async () => {
  const f = $('#form-settings');
  const r = $('#tg-test-result');
  r.textContent = 'Отправляю…';
  try {
    const tok = f.telegram_token.value.trim();
    const res = await api('/api/telegram/test', { method: 'POST', body: { token: tok, chat_id: f.telegram_chat_id.value.trim() } });
    r.innerHTML = `<span style="color:var(--good-ink)">✓ Отправлено через @${esc(res.bot)}. Не забудьте сохранить настройки.</span>`;
  } catch (e) {
    r.innerHTML = `<span style="color:var(--crit)">✗ ${esc(e.message)}</span>`;
  }
});

/* ---------------- обработчики кликов ---------------- */
document.addEventListener('click', async (e) => {
  const t = e.target.closest('button, a');
  if (!t) return;
  if (t.matches('[data-add]') || t.id === 'btn-add') { resetAdd(); openDialog($('#dlg-add')); return; }
  if (t.matches('[data-open-settings]') || t.id === 'btn-settings') { openSettings(); return; }
  if (t.matches('[data-push-on]')) { enablePush(); return; }
  if (t.matches('[data-push-off]')) { disablePush(); return; }
  if (t.matches('[data-push-test]')) {
    try { const r = await api('/api/push/test', { method: 'POST', body: { kind: t.dataset.pushTest } }); toast(`Отправлено в браузеров: ${r.sent}`); }
    catch (err) { toast(err.message, 6000); }
    return;
  }
  if (t.matches('[data-skip-tg]')) { store.set('skipTelegram', true); renderSetup(); return; }
  if (t.matches('[data-chat]')) { $('#form-settings').telegram_chat_id.value = t.dataset.chat; return; }
  if (t.id === 'hero-hide') { store.set('heroDismissed', t.dataset.key); renderHero(); return; }
  if (t.id === 'alarm-ok') { hideAlarm(); return; }
  if (t.id === 'btn-test-alarm') { unlockAudio(); $('#dlg-settings').close(); showAlarm(TEST_ALARM); return; }
  if (t.id === 'feed-more') { loadFeed(false); return; }
  if (t.id === 'btn-check-all') {
    t.disabled = true;
    const ws = S.state ? S.state.watches.filter((w) => w.enabled && w.status !== 'finished') : [];
    ws.forEach((w) => S.checking.add(w.id));
    renderWatches();
    try { await api('/api/check-all', { method: 'POST' }); toast('Проверка выполнена'); }
    catch (err) { toast(err.message); }
    finally { S.checking.clear(); t.disabled = false; refresh(); }
    return;
  }
  if (t.dataset.check) {
    const id = t.dataset.check;
    S.checking.add(id);
    renderWatches();
    try { await api(`/api/watches/${encodeURIComponent(id)}/check`, { method: 'POST' }); }
    catch (err) { toast(err.message); }
    finally { S.checking.delete(id); refresh(); }
    return;
  }
  if (t.dataset.toggle) {
    const enabled = t.dataset.enabled !== 'true';
    try { await api(`/api/watches/${encodeURIComponent(t.dataset.toggle)}`, { method: 'PATCH', body: { enabled } }); toast(enabled ? 'Отслеживание возобновлено' : 'Поставлено на паузу'); }
    catch (err) { toast(err.message); }
    refresh();
    return;
  }
  if (t.dataset.rename) {
    const w = S.state.watches.find((x) => x.id === t.dataset.rename);
    const name = prompt('Название поезда (пусто — по умолчанию):', (w && w.name) || '');
    if (name === null) return;
    try { await api(`/api/watches/${encodeURIComponent(t.dataset.rename)}`, { method: 'PATCH', body: { name } }); }
    catch (err) { toast(err.message); }
    refresh();
    return;
  }
  if (t.dataset.delete) {
    const w = S.state.watches.find((x) => x.id === t.dataset.delete);
    if (!confirm(`Удалить «${w ? w.title : ''}» вместе с историей и событиями?`)) return;
    try { await api(`/api/watches/${encodeURIComponent(t.dataset.delete)}`, { method: 'DELETE' }); toast('Удалено'); }
    catch (err) { toast(err.message); }
    refresh();
    loadFeed(true);
    return;
  }
  const seg = t.closest('[data-range-for]');
  if (seg && t.dataset.h !== undefined) {
    const id = seg.dataset.rangeFor;
    S.ranges[id] = Number(t.dataset.h);
    store.set('ranges', S.ranges);
    $$('button', seg).forEach((b) => b.classList.toggle('on', b === t));
    const w = S.state.watches.find((x) => x.id === id);
    if (w) loadHistory(w, true);
    return;
  }
  const ff = t.closest('#feed-filter');
  if (ff) {
    S.feedKind = t.dataset.k;
    $$('button', ff).forEach((b) => b.classList.toggle('on', b === t));
    S.feedOldest = null;
    loadFeed(true);
  }
});

document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !$('#alarm').hidden) hideAlarm(); });

/* ---------------- старт ---------------- */
(async function start() {
  if (location.hash === '#test-alarm') showAlarm(TEST_ALARM);
  // данные и живые обновления не ждут Service Worker — он может регистрироваться долго
  connect();
  loadFeed(true);
  await refresh();
  await initServiceWorker();
  if (S.state) { renderAll(); syncPushSubscription(); }
})();
