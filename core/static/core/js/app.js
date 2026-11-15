(function () {
  // ---- modal oynalar ekran markazida turishi uchun <body> ga ko'chiriladi ----
  // (animatsiyali ota-element ichida position:fixed sahifa o'rtasiga tushib qoladi)
  function modallarniKochir() {
    document.querySelectorAll('.modal').forEach(function (m) { if (m.parentNode !== document.body) document.body.appendChild(m); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', modallarniKochir); else modallarniKochir();
  window.addEventListener('load', modallarniKochir);
})();
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

  // ---- hammasini tanlash ----
  var all = document.getElementById('hammasi');
  if (all) all.addEventListener('change', function () { document.querySelectorAll('input[name=tp]').forEach(function (c) { c.checked = all.checked; }); });

  // ---- bildirishnomalar: har qanday sahifada vazifa tugaganda «bajarildi / xato» xabari ----
  var BK = 'bild_korilgan';
  function oku(k) { try { return JSON.parse(localStorage.getItem(k) || '[]'); } catch (e) { return []; } }
  function yoz(k, v) { try { localStorage.setItem(k, JSON.stringify(v.slice(-300))); } catch (e) {} }
  // ---- xabar (toast) dizayni: ikonka, yopish tugmasi va qolgan vaqt chizig'i ----
  var IKON = {
    success: '<svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
    error: '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg>',
    warning: '<svg viewBox="0 0 24 24"><path d="M12 7v6.5M12 17.2v.1"/></svg>',
    info: '<svg viewBox="0 0 24 24"><path d="M12 11v6M12 7.2v.1"/></svg>'
  };
  var MUDDAT = { success: 6000, info: 6000, warning: 10000, error: 15000 };
  window.toastQur = function (el, muddat, yuklanmoqda) {
    if (el.getAttribute('data-q')) return el;
    el.setAttribute('data-q', '1');
    var tur = el.classList.contains('success') ? 'success' : el.classList.contains('error') ? 'error' : el.classList.contains('warning') ? 'warning' : 'info';
    var matn = el.textContent.trim();
    el.className = 'toast ' + tur; el.removeAttribute('style'); el.removeAttribute('title');
    el.innerHTML = '';
    el.setAttribute('role', tur === 'error' ? 'alert' : 'status');
    var ic = document.createElement('span'); ic.className = 't-ic' + (yuklanmoqda ? ' spin' : ''); ic.innerHTML = IKON[tur];
    var m = document.createElement('div'); m.className = 't-m'; m.textContent = matn;
    var x = document.createElement('button'); x.type = 'button'; x.className = 't-x'; x.setAttribute('aria-label', 'Yopish'); x.innerHTML = '&times;';
    var yop = function () { if (el.parentNode) { el.style.transition = 'opacity .3s, transform .3s'; el.style.opacity = 0; el.style.transform = 'translateX(20px)'; setTimeout(function () { el.remove(); }, 320); } };
    x.addEventListener('click', yop); el.yop = yop;
    el.appendChild(ic); el.appendChild(m); el.appendChild(x);
    var ms = muddat === undefined ? MUDDAT[tur] : muddat;
    if (ms > 0) {
      var bar = document.createElement('i'); bar.className = 't-bar'; bar.style.setProperty('--tm', ms + 'ms'); el.appendChild(bar);
      bar.addEventListener('animationend', yop);
    }
    return el;
  };
  function toastlarniQur() { document.querySelectorAll('.toast').forEach(function (t) { window.toastQur(t); }); }
  toastlarniQur();
  new MutationObserver(function (list) {
    list.forEach(function (r) { r.addedNodes.forEach(function (n) { if (n.nodeType === 1) { if (n.classList.contains('toast')) window.toastQur(n); else if (n.querySelectorAll) n.querySelectorAll('.toast').forEach(function (t) { window.toastQur(t); }); } }); });
  }).observe(document.body, { childList: true, subtree: true });

  // key berilsa, bir xil xabar bitta brauzerda faqat bir marta ko'rsatiladi.
  // opt: {muddat: ms (0 = o'zi yopilmaydi), yuklanmoqda: true}. Qaytaradi: xabar elementi (yopish uchun el.yop()) yoki false.
  window.bildirish = function (matn, tur, key, opt) {
    opt = opt || {};
    if (key) { var k = oku(BK); if (k.indexOf(key) >= 0) return false; k.push(key); yoz(BK, k); }
    var c = document.querySelector('.toasts');
    if (!c) { c = document.createElement('div'); c.className = 'toasts'; document.body.appendChild(c); }
    var e = document.createElement('div'); e.className = 'toast ' + (tur || 'info'); e.textContent = matn;
    window.toastQur(e, opt.muddat, opt.yuklanmoqda); c.appendChild(e);
    return e;
  };
  window.bildirKo = function (key) { var k = oku(BK); if (k.indexOf(key) < 0) { k.push(key); yoz(BK, k); } };
  try { var fl = sessionStorage.getItem('bild_flash'); if (fl) { sessionStorage.removeItem('bild_flash'); window.bildirish(fl, 'success'); } } catch (e) {}
  var bildUrl = document.body.getAttribute('data-bild');
  if (bildUrl) {
    (function sora() {
      fetch(bildUrl, { credentials: 'same-origin' }).then(function (r) { if (!r.ok) throw new Error('bild'); return r.json(); }).then(function (d) {
        var faol = false;
        d.ishlar.forEach(function (i) { if (i.faol) faol = true; else window.bildirish(i.matn, i.tur, i.k); });
        setTimeout(sora, faol ? 2500 : 20000);
      }).catch(function () { setTimeout(sora, 30000); });
    })();
  }

  // ---- fayl yuklab olish (Excel / PDF / ZIP): tayyorlanmoqda -> yuklab olindi yoki xato ----
  function fayloNomi(cd, zaxira) {
    var m = /filename\*=UTF-8''([^;]+)/i.exec(cd || ''); if (m) { try { return decodeURIComponent(m[1]); } catch (e) {} }
    m = /filename="?([^";]+)"?/i.exec(cd || ''); return m ? m[1] : zaxira;
  }
  document.addEventListener('click', function (e) {
    var a = e.target.closest('a[href*="format="], a[href*="/yuklab/"]');
    if (!a || e.button || e.ctrlKey || e.metaKey || e.shiftKey || !window.fetch || !window.URL || !window.Blob) return;
    e.preventDefault();
    if (a.getAttribute('data-band')) return;
    a.setAttribute('data-band', '1');
    var nom = a.textContent.replace(/\s+/g, ' ').trim() || 'Fayl';
    var kutish = window.bildirish('Fayl tayyorlanmoqda: ' + nom + '…', 'info', null, { muddat: 0, yuklanmoqda: true });
    fetch(a.href, { credentials: 'same-origin' }).then(function (r) {
      if (!r.ok) { var er = new Error('http'); er.status = r.status; throw er; }
      var fn = fayloNomi(r.headers.get('Content-Disposition'), 'fayl');
      return r.blob().then(function (b) { return { b: b, fn: fn }; });
    }).then(function (x) {
      var u = URL.createObjectURL(x.b), l = document.createElement('a'); l.href = u; l.download = x.fn; document.body.appendChild(l); l.click(); l.remove();
      setTimeout(function () { URL.revokeObjectURL(u); }, 20000);
      window.bildirish('Fayl yuklab olindi: ' + x.fn, 'success');
    }).catch(function (er) {
      var m = er && er.status === 403 ? 'Bu faylni yuklab olishga ruxsatingiz yo\'q.' : er && er.status === 404 ? 'Ma\'lumot topilmadi: fayl yaratib bo\'lmadi.' : er && er.status ? 'Server xatosi (' + er.status + '): fayl tayyorlanmadi.' : 'Tarmoq xatosi: fayl yuklab olinmadi. Aloqani tekshirib qayta urinib ko\'ring.';
      window.bildirish('' + nom + ': ' + m, 'error');
    }).then(function () { a.removeAttribute('data-band'); if (kutish && kutish.yop) kutish.yop(); });
  });

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
