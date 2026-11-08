/* 이슈피클 공통 화면 기능: 화면 설정, 아래 메뉴, 문의 메일 */
(function () {
  var doc = document.documentElement;
  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function put(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  // ── 화면 설정 (밝게·편하게·어둡게 / 기본·크게·더 크게) ──
  var THEMES = [["light", "밝게"], ["soft", "편하게"], ["dark", "어둡게"]];
  var SIZES = [["m", "기본"], ["l", "크게"], ["xl", "더 크게"]];
  function setTheme(v) { doc.setAttribute("data-theme", v); put("theme", v); sync(); }
  function setSize(v) { doc.setAttribute("data-fs", v); put("fsize", v); sync(); }
  function sync() {
    document.querySelectorAll("[data-theme-v]").forEach(function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-theme-v") === doc.getAttribute("data-theme"));
    });
    document.querySelectorAll("[data-fs-v]").forEach(function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-fs-v") === doc.getAttribute("data-fs"));
    });
  }

  var btn = document.getElementById("settings-btn");
  if (btn) {
    var bg = document.createElement("div");
    bg.className = "sheet-bg"; bg.hidden = true;
    var sh = document.createElement("div");
    sh.className = "sheet"; sh.id = "settings"; sh.hidden = true;
    sh.setAttribute("role", "dialog"); sh.setAttribute("aria-modal", "true"); sh.setAttribute("aria-labelledby", "settings-t");
    sh.innerHTML =
      '<h2 id="settings-t">화면 설정<button class="icon-btn" id="settings-x" aria-label="화면 설정 닫기"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button></h2>' +
      '<h3>화면 밝기</h3><div class="opts">' + THEMES.map(function (t) { return '<button data-theme-v="' + t[0] + '">' + t[1] + '</button>'; }).join("") + '</div>' +
      '<h3>글자 크기</h3><div class="opts">' + SIZES.map(function (t) { return '<button data-fs-v="' + t[0] + '">' + t[1] + '</button>'; }).join("") + '</div>';
    document.body.appendChild(bg); document.body.appendChild(sh);
    var open = function () { bg.hidden = sh.hidden = false; btn.setAttribute("aria-expanded", "true"); sync(); sh.querySelector("button[aria-pressed=true]")?.focus(); };
    var close = function () { bg.hidden = sh.hidden = true; btn.setAttribute("aria-expanded", "false"); btn.focus(); };
    btn.setAttribute("aria-expanded", "false");
    btn.onclick = open; bg.onclick = close;
    document.getElementById("settings-x").onclick = close;
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !sh.hidden) close(); });
    sh.addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      if (b.dataset.themeV) setTheme(b.dataset.themeV);
      if (b.dataset.fsV) setSize(b.dataset.fsV);
    });
  }

  // ── 아래 메뉴 ──
  var nav = document.querySelector("nav.bnav");
  if (nav) {
    var here = nav.getAttribute("data-here") || "";
    var home = /index\.html$|\/$/.test(location.pathname) || !/\.html$/.test(location.pathname);
    var pre = home ? "" : "index.html";
    var items = [
      ["home", "index.html", "홈", '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>'],
      ["rank", pre + "#sec-top", "이슈 랭킹", '<path d="M6 20V11M12 20V4M18 20v-6"/>'],
      ["people", pre + "#sec-people", "인물", '<circle cx="12" cy="8" r="4"/><path d="M4 21c1-4 4-6 8-6s7 2 8 6"/>'],
      ["content", "content.html", "콘텐츠", '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m10 9 5 3-5 3z"/>'],
      ["memes", "memes.html", "밈절임", '<path d="M4 5h16v11H9l-5 4z"/><path d="M8.5 10.5h.01M12 10.5h.01M15.5 10.5h.01"/>']
    ];
    nav.setAttribute("aria-label", "주요 메뉴");
    nav.innerHTML = "<ul>" + items.map(function (it) {
      return '<li><a href="' + it[1] + '"' + (it[0] === here ? ' aria-current="page"' : "") + '><svg viewBox="0 0 24 24" aria-hidden="true">' + it[3] + "</svg>" + it[2] + "</a></li>";
    }).join("") + "</ul>";
  }

  // ── 문의 메일: 스팸 봇이 못 긁어 가도록 누를 때만 주소를 만들어요 ──
  document.querySelectorAll("a.mail").forEach(function (a) {
    a.onclick = function (e) {
      if (a.dataset.shown) return true;
      e.preventDefault();
      var m = a.dataset.u.split("").reverse().join("") + "@" + a.dataset.d.split("").reverse().join("");
      a.textContent = m; a.href = "mailto:" + m; a.dataset.shown = 1;
    };
  });
  sync();
})();
