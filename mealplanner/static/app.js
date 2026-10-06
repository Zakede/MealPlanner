// Confirm buttons: <button data-confirm="Are you sure?">
document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-confirm]");
  if (el && !confirm(el.dataset.confirm)) e.preventDefault();
});

const calm = matchMedia("(prefers-reduced-motion: reduce)").matches;

// Messages fade away after a few seconds (errors stay until you leave the page).
document.querySelectorAll(".flash:not(.flash-error)").forEach((el, i) => {
  setTimeout(() => {
    el.classList.add("leaving");
    el.addEventListener("animationend", () => el.remove(), { once: true });
    if (calm) el.remove();
  }, 3500 + i * 300);
});

// Big numbers count up to their value once.
if (!calm) {
  document.querySelectorAll(".num-big").forEach((el) => {
    const match = el.firstChild && el.firstChild.nodeType === 3 && el.firstChild.textContent.match(/^(¥|\$|£|€|₩|₹|A\$|C\$|NT\$)?(-?[\d,]+)(\.\d)?$/);
    if (!match || match[3]) return;
    const prefix = match[1] || "";
    const target = parseInt(match[2].replace(/,/g, ""), 10);
    if (!target || Math.abs(target) < 10) return;
    const node = el.firstChild, start = performance.now(), fmt = new Intl.NumberFormat();
    const tick = (t) => {
      const k = Math.min(1, (t - start) / 900);
      node.textContent = prefix + fmt.format(Math.round(target * (1 - Math.pow(1 - k, 3)))).replace(/,/g, match[2].includes(",") ? "," : "");
      if (k < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}

// Country switch: swap shop and area lists, currency labels, and convert money fields in place.
(() => {
  const sw = document.querySelector("[data-country-switch]");
  const data = document.getElementById("country-options");
  if (!sw || !data) return;
  const options = JSON.parse(data.textContent);
  let current = sw.value;
  const fill = (select, list, keep) => {
    if (!select) return;
    const wanted = list.some(([k]) => k === keep) ? keep : (list.find(([k]) => k === "supermarket" || k === "city") || list[0])[0];
    select.replaceChildren(...list.map(([k, label]) => new Option(label, k, false, k === wanted)));
    select.animate?.([{ opacity: .3 }, { opacity: 1 }], { duration: 300 });
  };
  sw.addEventListener("change", () => {
    const from = options[current], to = options[sw.value];
    fill(document.querySelector("[data-shop-list]"), to.shops, document.querySelector("[data-shop-list]")?.value);
    fill(document.querySelector("[data-area-list]"), to.areas, document.querySelector("[data-area-list]")?.value);
    document.querySelectorAll(".cur-label").forEach((el) => { el.textContent = to.symbol; });
    document.querySelectorAll("input[data-money]").forEach((input) => {
      const n = parseFloat(input.value);
      if (Number.isNaN(n)) return;
      const converted = n / from.money * to.money;
      // round to a sensible step for the currency size
      const step = converted >= 10000 ? 100 : converted >= 1000 ? 10 : converted >= 100 ? 5 : 1;
      input.value = Math.round(converted / step) * step;
      input.animate?.([{ boxShadow: "0 0 0 4px rgba(184,161,238,.45)" }, { boxShadow: "0 0 0 0 rgba(184,161,238,0)" }], { duration: 700 });
    });
    current = sw.value;
  });
})();

// Chip editor: comma lists (allergies, things you won't eat) become chips you add and remove.
document.querySelectorAll("input[data-chips]").forEach((input) => {
  const box = document.createElement("div");
  box.className = "chip-box";
  const entry = document.createElement("input");
  entry.type = "text";
  entry.placeholder = input.placeholder || "Add one";
  entry.setAttribute("list", input.getAttribute("list") || "");
  entry.setAttribute("aria-label", "Add to " + input.name);
  const add = document.createElement("button");
  add.type = "button"; add.className = "btn small"; add.textContent = "Add";
  const chips = document.createElement("div");
  chips.className = "chip-list";
  const items = () => input.value.split(",").map((x) => x.trim()).filter(Boolean);
  const render = () => {
    chips.replaceChildren(...items().map((item) => {
      const chip = document.createElement("button");
      chip.type = "button"; chip.className = "chip removable"; chip.textContent = item + "  ✕";
      chip.setAttribute("aria-label", "Remove " + item);
      chip.addEventListener("click", () => { input.value = items().filter((x) => x !== item).join(", "); render(); });
      return chip;
    }));
  };
  const push = () => {
    const v = entry.value.trim().replace(/,/g, "");
    if (v && !items().map((x) => x.toLowerCase()).includes(v.toLowerCase())) input.value = [...items(), v].join(", ");
    entry.value = ""; render(); entry.focus();
  };
  add.addEventListener("click", push);
  entry.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === ",") { e.preventDefault(); push(); } });
  const row = document.createElement("div");
  row.className = "chip-entry";
  row.append(entry, add);
  box.append(chips, row);
  input.type = "hidden";
  input.after(box);
  render();
});

// Activities on the week plan: "+ Add" opens a small form under that day.
document.querySelectorAll("[data-act-open]").forEach((btn) => {
  const form = btn.closest(".day-info").nextElementSibling;
  if (!form || !form.classList.contains("act-form")) return;
  const toggle = (open) => {
    form.hidden = !open;
    btn.setAttribute("aria-expanded", open);
    btn.textContent = open ? "Close" : "+ Add";
    if (open) { burst(btn, 8); form.querySelector("input[name=label]").focus({ preventScroll: true }); }
  };
  btn.addEventListener("click", () => toggle(form.hidden));
  form.querySelector("[data-act-cancel]").addEventListener("click", () => toggle(false));
  // sensible effort for the kind picked
  const effort = { work: "desk", school: "desk", parttime: "standing", club: "standing", gym: "physical", other: "desk" };
  form.querySelectorAll("input[name=kind]").forEach((r) => r.addEventListener("change", () => {
    form.querySelector("select[name=intensity]").value = effort[r.value] || "desk";
  }));
});

// ---- motion ----

// Sparkles fly out of an element (ticks, adds, approvals).
function burst(el, count = 12) {
  if (calm || !el) return;
  const r = el.getBoundingClientRect();
  const colors = ["var(--fuji)", "var(--fuji-light)", "var(--seal)", "var(--ok)"];
  for (let i = 0; i < count; i++) {
    const s = document.createElement("i");
    const angle = (Math.PI * 2 * i) / count + Math.random() * 0.5;
    const dist = 28 + Math.random() * 30;
    s.className = "spark";
    s.style.left = r.left + r.width / 2 + "px";
    s.style.top = r.top + r.height / 2 + "px";
    s.style.setProperty("--x", Math.cos(angle) * dist + "px");
    s.style.setProperty("--y", Math.sin(angle) * dist + "px");
    s.style.setProperty("--r", Math.round(Math.random() * 360) + "deg");
    s.style.setProperty("--c", colors[i % colors.length]);
    if (i % 3 === 0) s.style.borderRadius = "50%";
    document.body.append(s);
    s.addEventListener("animationend", () => s.remove(), { once: true });
  }
}

// Thin bar along the top while the next page loads.
function loading() {
  const bar = document.querySelector(".loadbar");
  if (bar) requestAnimationFrame(() => bar.classList.add("go"));
}
document.addEventListener("submit", (e) => { if (!e.defaultPrevented) loading(); });
document.addEventListener("click", (e) => {
  const a = e.target.closest("a[href]");
  if (!a || e.defaultPrevented || a.target || e.metaKey || e.ctrlKey || a.getAttribute("href").startsWith("#")) return;
  loading();
});
// coming back with the browser's back button: no stuck bar
addEventListener("pageshow", () => document.querySelector(".loadbar")?.classList.remove("go"));

// Ripple from where you touched a key.
document.addEventListener("pointerdown", (e) => {
  if (calm) return;
  const el = e.target.closest(".btn, .chip, nav.bottom a, .menu a, .boost-add, .key, .opt span, .act-kinds span, .act-add");
  if (!el) return;
  const r = el.getBoundingClientRect();
  const size = Math.max(r.width, r.height) * 2.2;
  const dot = document.createElement("span");
  dot.className = "ripple";
  dot.style.width = dot.style.height = size + "px";
  dot.style.left = e.clientX - r.left + "px";
  dot.style.top = e.clientY - r.top + "px";
  el.append(dot);
  dot.addEventListener("animationend", () => dot.remove(), { once: true });
});

// Cards rise in as they scroll into view, a few at a time.
if (!calm && "IntersectionObserver" in window) {
  const targets = document.querySelectorAll(
    "main :is(.card, .plate, .day-head, .day-info, .boost, .menu a, .list > li, .tile):not(.rise)");
  let batch = 0, frame = 0;
  const io = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.style.setProperty("--d", Math.min(batch++, 8) * 55 + "ms");
      entry.target.classList.add("in");
      io.unobserve(entry.target);
    });
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => { batch = 0; });
  }, { rootMargin: "0px 0px -6% 0px" });
  targets.forEach((t) => io.observe(t));
} else {
  document.documentElement.classList.remove("motion");
}

// Approve and taste-booster adds: sparkle first, then send.
document.querySelectorAll("form").forEach((form) => {
  const add = form.querySelector(".boost-add");
  const approve = /\/approve/.test(form.action) ? form.querySelector(".btn") : null;
  const el = add || approve;
  if (!el || calm) return;
  form.addEventListener("submit", (e) => {
    if (form.dataset.sent) return;
    e.preventDefault();
    form.dataset.sent = "1";
    el.classList.add("sent");
    burst(el, approve ? 18 : 12);
    loading();
    setTimeout(() => form.submit(), 320);
  });
});

// Booster page: the jump chip for the section you're reading lights up.
const jumps = document.querySelectorAll(".boost-jump a[href^='#']");
if (jumps.length && "IntersectionObserver" in window) {
  const byId = new Map([...jumps].map((a) => [a.getAttribute("href").slice(1), a]));
  const spy = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      jumps.forEach((a) => a.classList.remove("here"));
      byId.get(entry.target.id)?.classList.add("here");
    });
  }, { rootMargin: "-30% 0px -60% 0px" });
  byId.forEach((_, id) => { const sec = document.getElementById(id); if (sec) spy.observe(sec); });
  jumps.forEach((a) => a.addEventListener("click", (e) => {
    const sec = document.getElementById(a.getAttribute("href").slice(1));
    if (!sec) return;
    e.preventDefault();
    sec.scrollIntoView({ behavior: calm ? "auto" : "smooth", block: "start" });
    history.replaceState(null, "", a.getAttribute("href"));
  }));
}

// Next-meal ticket and tiles lean toward the pointer (mouse only, phones keep the press).
if (!calm && matchMedia("(hover: hover) and (pointer: fine)").matches) {
  document.querySelectorAll(".ticket, .plate, .keys > .key").forEach((el) => {
    el.addEventListener("pointermove", (e) => {
      const r = el.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
      el.style.transform = `perspective(700px) rotateX(${-y * 6}deg) rotateY(${x * 8}deg) translateY(-2px)`;
    });
    el.addEventListener("pointerleave", () => { el.style.transform = ""; });
  });
}
