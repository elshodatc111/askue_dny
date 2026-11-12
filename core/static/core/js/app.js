(function () {
  // ---- mavzu (yorug' / qorong'i) ----
  var root = document.documentElement;
  function setTheme(t) { root.setAttribute('data-theme', t); try { localStorage.setItem('tema', t); } catch (e) {} window.dispatchEvent(new Event('tema-ozgardi')); }
  document.addEventListener('click', function (e) {
    var b = e.target.closest('#theme-btn');
    if (b) { setTheme(root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark'); }
    var m = e.target.closest('#menu-btn');
    if (m) { toggleSide(); }
    if (e.target.closest('#scrim') || (window.innerWidth <= 900 && e.target.closest('.nav a'))) { toggleSide(false); }
    // chiqishni tasdiqlash
    if (e.target.closest('[data-logout]')) { logoutModal(true); }
    if (e.target.closest('[data-logout-cancel]') || e.target === document.getElementById('logout-modal')) { logoutModal(false); }
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { logoutModal(false); toggleSide(false); } });
  function toggleSide(force) {
    var s = document.getElementById('side'), sc = document.getElementById('scrim');
    if (!s) return;
    var on = typeof force === 'boolean' ? force : !s.classList.contains('open');
    s.classList.toggle('open', on); if (sc) sc.classList.toggle('on', on);
  }
  function logoutModal(on) {
    var m = document.getElementById('logout-modal');
    if (!m) return;
    m.hidden = !on;
    if (on) { var c = m.querySelector('[data-logout-cancel]'); if (c) c.focus(); }
  }

  // ---- filtr o'zgarganda avtomatik yuborish ----
  document.querySelectorAll('form[data-auto] select, form[data-auto] input[type=date]').forEach(function (el) {
    el.addEventListener('change', function () { el.form.submit(); });
  });

  // ---- raqam sanagich animatsiyasi ----
  function fmt(n) { return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ' '); }
  document.querySelectorAll('[data-count]').forEach(function (el) {
    var to = parseFloat(el.getAttribute('data-count')) || 0, t0 = null, dur = 1100;
    function step(ts) {
      if (!t0) t0 = ts;
      var p = Math.min((ts - t0) / dur, 1), e = 1 - Math.pow(1 - p, 3);
      el.textContent = fmt(to * e);
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  });

  // ---- progress barlar ----
  setTimeout(function () {
    document.querySelectorAll('.bar i[data-w]').forEach(function (i) { i.style.width = i.getAttribute('data-w') + '%'; });
  }, 150);

  // ---- xabarlar avtomatik yo'qolishi ----
  setTimeout(function () {
    document.querySelectorAll('.toast').forEach(function (t) { t.style.transition = 'opacity .5s'; t.style.opacity = 0; setTimeout(function () { t.remove(); }, 600); });
  }, 6500);

  // ---- hammasini tanlash ----
  var all = document.getElementById('hammasi');
  if (all) all.addEventListener('change', function () { document.querySelectorAll('input[name=tp]').forEach(function (c) { c.checked = all.checked; }); });

  // ---- diagramma yordamchilari ----
  window.ranglar = function () {
    var cs = getComputedStyle(root);
    return { text: cs.getPropertyValue('--text').trim(), muted: cs.getPropertyValue('--muted').trim(), line: cs.getPropertyValue('--line').trim(), card: cs.getPropertyValue('--card').trim() };
  };
  window.chartlar = [];
  window.chartYarat = function (id, optFn) {
    var el = document.getElementById(id); if (!el || !window.echarts) return null;
    var c = echarts.init(el); window.chartlar.push({ c: c, f: optFn });
    c.setOption(optFn(window.ranglar())); return c;
  };
  window.addEventListener('tema-ozgardi', function () { setTimeout(function () { window.chartlar.forEach(function (x) { x.c.setOption(x.f(window.ranglar()), true); }); }, 30); });
  window.addEventListener('resize', function () { window.chartlar.forEach(function (x) { x.c.resize(); }); });
  window.sonFmt = fmt;
})();
