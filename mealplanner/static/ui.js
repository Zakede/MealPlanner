// Dark / light switch: the new theme spreads out in a circle from the button, then gets saved.
(() => {
  const btn = document.querySelector("[data-theme-toggle]");
  if (!btn) return;
  const root = document.documentElement;
  const calmNow = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const effective = () => {
    const m = root.dataset.mode;
    if (m === "light" || m === "dark") return m;
    return matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  };
  const sync = () => { btn.dataset.now = effective(); };
  sync();
  btn.addEventListener("click", (e) => {
    const next = effective() === "light" ? "dark" : "light";
    const apply = () => {
      root.dataset.mode = next;
      document.querySelector('meta[name="theme-color"]')?.setAttribute("content", next === "light" ? "#f8f5fd" : "#000000");
      sync();
    };
    const body = new URLSearchParams({ mode: next });
    fetch(btn.dataset.url, { method: "POST", body }).catch(() => {});
    if (calmNow || !document.startViewTransition) { apply(); return; }
    const r = btn.getBoundingClientRect();
    const x = r.left + r.width / 2, y = r.top + r.height / 2;
    const radius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
    root.classList.add("theming");
    const t = document.startViewTransition(apply);
    t.ready.then(() => {
      root.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
        { duration: 650, easing: "cubic-bezier(0.65, 0, 0.35, 1)", pseudoElement: "::view-transition-new(root)" });
    });
    t.finished.finally(() => root.classList.remove("theming"));
  });
})();

// Dropdowns: every <select> becomes a picker that pops open as a card (a sheet on phones).
// The real <select> stays in the form, hidden, so saving and other scripts work as before.
(() => {
  const CHECK = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12.5 4.5 4.5L19 7"/></svg>';
  const CHEV = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>';
  const phone = () => innerWidth < 560;
  let open = null;
  let uid = 0;

  function labelText(select) {
    const lab = select.labels && select.labels[0];
    if (lab) return [...lab.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join(" ").trim();
    return select.getAttribute("aria-label") || "Choose";
  }

  function enhance(select) {
    if (select.dataset.native !== undefined || select.closest(".fsel") || select.multiple) return;
    const wrap = document.createElement("div");
    wrap.className = "fsel";
    const id = "fsel" + uid++;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "fsel-btn";
    btn.setAttribute("aria-haspopup", "listbox");
    btn.setAttribute("aria-expanded", "false");
    btn.setAttribute("aria-controls", id);
    btn.innerHTML = `<span class="fsel-val"></span><span class="fsel-chev">${CHEV}</span>`;
    const panel = document.createElement("div");
    panel.className = "fsel-panel";
    panel.id = id;
    panel.hidden = true;
    select.before(wrap);
    wrap.append(select, btn, panel);
    select.classList.add("fsel-native");
    select.tabIndex = -1;
    btn.setAttribute("aria-label", labelText(select));

    const show = () => {
      const opt = select.selectedOptions[0];
      btn.querySelector(".fsel-val").textContent = opt ? opt.textContent : "";
      btn.classList.toggle("empty", !opt || opt.value === "");
    };

    function build() {
      const many = select.options.length > 8;
      panel.innerHTML = "";
      if (phone()) {
        const head = document.createElement("div");
        head.className = "fsel-title";
        head.textContent = labelText(select);
        panel.append(head);
      }
      let search = null;
      if (many) {
        search = document.createElement("input");
        search.type = "search";
        search.className = "fsel-search";
        search.placeholder = "Search…";
        search.setAttribute("aria-label", "Search " + labelText(select));
        panel.append(search);
      }
      const list = document.createElement("div");
      list.className = "fsel-list";
      list.setAttribute("role", "listbox");
      let n = 0;
      for (const node of select.children) {
        const opts = node.tagName === "OPTGROUP" ? [...node.children] : [node];
        if (node.tagName === "OPTGROUP") {
          const g = document.createElement("div");
          g.className = "fsel-group";
          g.textContent = node.label;
          list.append(g);
        }
        for (const o of opts) {
          const item = document.createElement("div");
          item.className = "fsel-opt";
          item.setAttribute("role", "option");
          item.dataset.value = o.value;
          item.style.setProperty("--n", Math.min(n++, 12));
          item.innerHTML = `<span></span><i>${CHECK}</i>`;
          item.firstChild.textContent = o.textContent;
          if (o.selected) { item.classList.add("on"); item.setAttribute("aria-selected", "true"); }
          if (o.disabled) item.classList.add("off");
          list.append(item);
        }
      }
      panel.append(list);
      if (search) {
        search.addEventListener("input", () => {
          const q = search.value.trim().toLowerCase();
          list.querySelectorAll(".fsel-opt").forEach((it) => { it.hidden = q && !it.textContent.toLowerCase().includes(q); });
          list.querySelectorAll(".fsel-group").forEach((g) => { g.hidden = !!q; });
          activate(list.querySelector(".fsel-opt:not([hidden])"));
        });
        search.addEventListener("keydown", keys);
      }
      return list;
    }

    let active = null;
    function activate(item) {
      active?.classList.remove("act");
      active = item;
      if (item) { item.classList.add("act"); item.scrollIntoView({ block: "nearest" }); }
    }

    function pick(item) {
      if (!item || item.classList.contains("off")) return;
      if (select.value !== item.dataset.value) {
        select.value = item.dataset.value;
        select.dispatchEvent(new Event("change", { bubbles: true }));
        select.dispatchEvent(new Event("input", { bubbles: true }));
      }
      show();
      close(true);
      btn.classList.remove("picked"); void btn.offsetWidth; btn.classList.add("picked");
    }

    function keys(e) {
      const items = [...panel.querySelectorAll(".fsel-opt:not([hidden]):not(.off)")];
      const i = items.indexOf(active);
      if (e.key === "ArrowDown") { e.preventDefault(); activate(items[Math.min(items.length - 1, i + 1)] || items[0]); }
      else if (e.key === "ArrowUp") { e.preventDefault(); activate(items[Math.max(0, i - 1)] || items[0]); }
      else if (e.key === "Home") { e.preventDefault(); activate(items[0]); }
      else if (e.key === "End") { e.preventDefault(); activate(items[items.length - 1]); }
      else if (e.key === "Enter" || (e.key === " " && e.target === btn)) { e.preventDefault(); pick(active); }
      else if (e.key === "Escape" || e.key === "Tab") { close(e.key === "Escape"); }
    }

    function openUp() {
      if (open && open !== api) open.close(false);
      const list = build();
      panel.hidden = false;
      wrap.classList.add("open");
      btn.setAttribute("aria-expanded", "true");
      const sheet = phone();
      panel.classList.toggle("sheet", sheet);
      if (sheet) {
        document.body.classList.add("fsel-lock");
        const shade = document.createElement("div");
        shade.className = "fsel-shade";
        shade.addEventListener("click", () => close(true));
        document.body.append(shade);
        document.body.append(panel);
      } else {
        const r = btn.getBoundingClientRect();
        panel.classList.toggle("up", r.bottom + 320 > innerHeight && r.top > 340);
      }
      activate(list.querySelector(".fsel-opt.on") || list.querySelector(".fsel-opt"));
      const search = panel.querySelector(".fsel-search");
      if (search && !sheet) search.focus({ preventScroll: true });
      open = api;
    }

    function close(focus) {
      if (panel.hidden) return;
      wrap.classList.remove("open");
      btn.setAttribute("aria-expanded", "false");
      const done = () => {
        panel.hidden = true;
        panel.classList.remove("closing");
        if (panel.parentNode !== wrap) wrap.append(panel);
      };
      document.querySelector(".fsel-shade")?.remove();
      document.body.classList.remove("fsel-lock");
      if (matchMedia("(prefers-reduced-motion: reduce)").matches) done();
      else { panel.classList.add("closing"); setTimeout(done, 160); }
      if (focus) btn.focus({ preventScroll: true });
      if (open === api) open = null;
    }

    const api = { close, wrap, panel };
    btn.addEventListener("click", () => (panel.hidden ? openUp() : close(true)));
    btn.addEventListener("keydown", (e) => {
      if (panel.hidden && ["ArrowDown", "ArrowUp", "Enter", " "].includes(e.key)) { e.preventDefault(); openUp(); return; }
      if (!panel.hidden) keys(e);
    });
    panel.addEventListener("click", (e) => pick(e.target.closest(".fsel-opt")));
    panel.addEventListener("pointermove", (e) => { const it = e.target.closest(".fsel-opt"); if (it && it !== active) activate(it); });
    // labels point at the hidden select: open the picker instead
    [...(select.labels || [])].forEach((lab) => lab.addEventListener("click", (e) => {
      if (e.target.closest(".fsel")) return;
      e.preventDefault();
      btn.focus();
    }));
    select.addEventListener("change", show);
    new MutationObserver(show).observe(select, { childList: true, subtree: true, attributes: true });
    // a required select with nothing picked: show the problem on the button
    select.addEventListener("invalid", () => { btn.classList.add("bad"); btn.focus(); });
    show();
  }

  document.addEventListener("pointerdown", (e) => {
    if (open && !open.wrap.contains(e.target) && !open.panel.contains(e.target)) open.close(false);
  });
  addEventListener("resize", () => open?.close(false));
  document.querySelectorAll("select").forEach(enhance);
  // pages swapped in without a reload (after a receipt scan) get the same pickers
  window.zettaiEnhance = (root) => root.querySelectorAll("select").forEach(enhance);
})();

// Mini notifications: the page asks every minute what's worth knowing (cook soon, thaw tonight, drink water...).
// New ones pop up as a toast; all of today's live under the bell. Dismissed ones stay dismissed for the day.
(() => {
  const bell = document.querySelector("[data-bell]");
  if (!bell) return;
  const panel = document.getElementById("nudge-panel"), list = panel.querySelector(".nudge-list");
  const count = bell.querySelector(".bell-count"), toasts = document.getElementById("toasts");
  const store = {
    get(k) { try { return JSON.parse(localStorage.getItem(k) || "{}"); } catch { return {}; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
  };
  let day = "", items = [];
  const key = () => "nudges-" + day;
  const state = () => store.get(key());   // id -> "seen" | "gone"

  function card(n, inToast) {
    const el = document.createElement(n.url ? "a" : "div");
    el.className = "nudge" + (n.urgent ? " urgent" : "") + (inToast ? " toast" : "");
    if (n.url) el.href = n.url;
    el.innerHTML = `<span class="nudge-ico">${n.svg}</span><span class="nudge-text"><b></b><small></small></span>`;
    el.querySelector("b").textContent = n.title;
    el.querySelector("small").textContent = n.body || "";
    const x = document.createElement("button");
    x.type = "button"; x.className = "nudge-x"; x.setAttribute("aria-label", "Dismiss"); x.textContent = "×";
    x.addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); dismiss(n.id, el); });
    el.append(x);
    return el;
  }
  function dismiss(id, el) {
    const s = state(); s[id] = "gone"; store.set(key(), s);
    el.classList.add("leaving");
    setTimeout(() => { el.remove(); render(); }, 250);
  }
  function render() {
    const s = state();
    const live = items.filter((n) => s[n.id] !== "gone");
    list.replaceChildren(...(live.length ? live.map((n) => card(n, false)) : [Object.assign(document.createElement("p"), { className: "muted small nudge-none", textContent: "All caught up." })]));
    count.hidden = !live.length;
    count.textContent = live.length;
    bell.classList.toggle("has", live.length > 0);
  }
  function toast(n) {
    const el = card(n, true);
    toasts.append(el);
    burst(el.querySelector(".nudge-ico"), 6);
    setTimeout(() => { el.classList.add("leaving"); setTimeout(() => el.remove(), 300); }, n.urgent ? 12000 : 7000);
  }
  async function poll() {
    try {
      const r = await fetch(bell.dataset.url, { headers: { Accept: "application/json" } });
      if (!r.ok) return;
      const d = await r.json();
      day = d.day; items = d.nudges;
      const s = state();
      items.filter((n) => !s[n.id]).slice(0, 3).forEach((n, i) => setTimeout(() => toast(n), 600 + i * 450));
      items.forEach((n) => { if (!s[n.id]) s[n.id] = "seen"; });
      store.set(key(), s);
      render();
    } catch {}
  }
  bell.addEventListener("click", () => {
    panel.hidden = !panel.hidden;
    bell.setAttribute("aria-expanded", !panel.hidden);
  });
  panel.querySelector("[data-nudge-clear]").addEventListener("click", () => {
    const s = state(); items.forEach((n) => { s[n.id] = "gone"; }); store.set(key(), s); render();
  });
  document.addEventListener("pointerdown", (e) => {
    if (!panel.hidden && !panel.contains(e.target) && !bell.contains(e.target)) { panel.hidden = true; bell.setAttribute("aria-expanded", "false"); }
  });
  poll();
  setInterval(() => { if (document.visibilityState === "visible") poll(); }, 60000);
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") poll(); });
})();
