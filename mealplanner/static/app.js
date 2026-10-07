// Confirm buttons: <button data-confirm="Are you sure?" data-confirm-yes="Delete">, asked in the page, not a browser box.
const askBox = (() => {
  const dlg = document.createElement("dialog");
  dlg.className = "ask-box";
  dlg.innerHTML = '<p class="ask-box-msg"></p><div class="ask-box-actions">' +
    '<button type="button" class="btn secondary" value="no">Cancel</button>' +
    '<button type="button" class="btn" value="yes">Yes</button></div>';
  document.body.append(dlg);
  let done = null;
  dlg.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (b) dlg.close(b.value);
    else if (e.target === dlg) dlg.close("no");          // tap outside the box
  });
  dlg.addEventListener("close", () => { if (done) done(dlg.returnValue === "yes"); done = null; });
  return (msg, yes) => new Promise((resolve) => {
    dlg.querySelector(".ask-box-msg").textContent = msg;
    dlg.querySelector('[value="yes"]').textContent = yes || "Yes";
    done = resolve;
    dlg.returnValue = "no";
    dlg.showModal();
    dlg.querySelector('[value="yes"]').focus();
  });
})();
document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-confirm]");
  if (!el || el.dataset.confirmed) { if (el) delete el.dataset.confirmed; return; }
  e.preventDefault();
  askBox(el.dataset.confirm, el.dataset.confirmYes).then((ok) => {
    if (!ok) return;
    el.dataset.confirmed = "1";
    el.click();                          // runs the button or link for real this time
  });
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

// Week plan: one "+ Add" per day. It flips to two choices: a meal, or an activity (school, a shift...).
document.querySelectorAll(".add-menu").forEach((menu) => {
  const main = menu.querySelector("[data-add-toggle]"), choices = menu.querySelector(".add-choices");
  const set = (open) => {
    choices.hidden = !open;
    menu.classList.toggle("open", open);
    main.setAttribute("aria-expanded", open);
  };
  main.addEventListener("click", (e) => { e.preventDefault(); set(choices.hidden); if (!choices.hidden) burst(main, 6); });
  document.addEventListener("pointerdown", (e) => { if (!menu.contains(e.target)) set(false); });
  menu.addEventListener("keydown", (e) => { if (e.key === "Escape") { set(false); main.focus(); } });
});

// Activities: "Activity" opens a small form under that day.
document.querySelectorAll("[data-act-open]").forEach((btn) => {
  const form = btn.closest(".keys").previousElementSibling;
  if (!form || !form.classList.contains("act-form")) return;
  const menu = btn.closest(".add-menu");
  const toggle = (open) => {
    form.hidden = !open;
    if (menu) { menu.querySelector(".add-choices").hidden = true; menu.classList.remove("open"); }
    if (open) {
      form.scrollIntoView({ behavior: calm ? "auto" : "smooth", block: "nearest" });
      form.querySelector("input[name=label]").focus({ preventScroll: true });
    }
  };
  btn.addEventListener("click", () => toggle(form.hidden));
  form.querySelector("[data-act-cancel]").addEventListener("click", () => toggle(false));
  // sensible effort for the kind picked
  const effort = { work: "desk", school: "desk", parttime: "standing", club: "standing", gym: "physical", other: "desk" };
  form.querySelectorAll("input[name=kind]").forEach((r) => r.addEventListener("change", () => {
    const sel = form.querySelector("select[name=intensity]");
    sel.value = effort[r.value] || "desk";
    sel.dispatchEvent(new Event("change"));
  }));
  const sel = form.querySelector("select[name=intensity]");
  const set = (name, value) => { const el = form.querySelector(`[name=${name}]`); if (el) el.value = value; };
  // one you've added before: fill the form with it
  form.querySelectorAll("[data-act-fill]").forEach((chip) => chip.addEventListener("click", () => {
    const a = JSON.parse(chip.dataset.actFill);
    const kind = form.querySelector(`input[name=kind][value="${a.kind}"]`);
    if (kind) kind.checked = true;
    set("label", a.label); set("start", a.start); set("end", a.end); set("commute", a.commute || 0);
    sel.value = a.intensity; sel.dispatchEvent(new Event("change"));
    form.querySelectorAll("[data-act-fill]").forEach((c) => c.classList.toggle("ok", c === chip));
    burst(chip, 6);
  }));
  // guess how active it is from the name, until you pick it yourself
  let picked = false;
  sel.addEventListener("input", () => { picked = true; });
  const words = [[/warehouse|construct|moving|mover|deliver|farm|clean|kitchen|cook|labou?r|factory|build|lift/i, "physical"],
                 [/shift|konbini|store|shop|retail|wait|cafe|café|restaurant|bar|teach|nurse|cashier|barista|hospital|sales/i, "standing"],
                 [/class|lecture|study|school|office|desk|meeting|exam|lab|remote/i, "desk"]];
  form.querySelector("input[name=label]").addEventListener("input", (e) => {
    if (picked) return;
    const hit = words.find(([re]) => re.test(e.target.value));
    if (hit && sel.value !== hit[1]) { sel.value = hit[1]; sel.dispatchEvent(new Event("change")); }
  });
  // live "about N kcal" for what's in the form (same numbers as nutrition.activity_burn)
  const out = form.querySelector(".act-estimate"), bmr = +form.dataset.bmr;
  const mets = { desk: 1.5, standing: 2.5, physical: 3.5 };
  const estimate = () => {
    if (!out) return;
    const [sh, sm] = (form.start.value || "0:0").split(":").map(Number), [eh, em] = (form.end.value || "0:0").split(":").map(Number);
    const hours = Math.min(16, Math.max(0, (eh * 60 + em - sh * 60 - sm) / 60));
    const gym = form.querySelector("input[name=kind]:checked")?.value === "gym";
    const kcal = Math.round(bmr / 24 * hours * ((gym ? 5 : mets[sel.value] || 1.5) - 1) / 10) * 10;
    out.textContent = hours ? `Burns about ${kcal} kcal on top of resting.` : "";
  };
  form.addEventListener("input", estimate); form.addEventListener("change", estimate); estimate();
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

// Picking a diet hides options it already rules out (no "fish" choices for a vegetarian).
(() => {
  const pickers = document.querySelectorAll('input[name="diet"], select[name="diet"]');
  if (!pickers.length) return;
  const current = () => {
    const r = document.querySelector('input[name="diet"]:checked');
    return r ? r.value : (document.querySelector('select[name="diet"]')?.value || "any");
  };
  const apply = () => {
    const diet = current();
    document.querySelectorAll("[data-diet-hide]").forEach((el) => {
      el.hidden = el.dataset.dietHide.split(" ").includes(diet);
    });
  };
  pickers.forEach((p) => p.addEventListener("change", apply));
  apply();
})();

// "Set all" for the protein rules and All / None for checkbox groups. Hidden (diet-ruled-out) rows are left alone.
document.addEventListener("click", (e) => {
  const rule = e.target.closest("[data-rule-all]");
  if (rule) {
    rule.closest(".rules").querySelectorAll(".rule-row:not(.rule-all):not([hidden])").forEach((row) => {
      const r = row.querySelector(`input[value="${rule.dataset.ruleAll}"]`);
      if (r) { r.checked = true; r.dispatchEvent(new Event("change", { bubbles: true })); }
    });
    return;
  }
  const all = e.target.closest("[data-check-all]");
  if (!all) return;
  const box = document.getElementById(all.dataset.checkAll);
  box?.querySelectorAll('input[type="checkbox"]').forEach((c) => {
    if (c.closest("[hidden]")) return;
    c.checked = all.dataset.on === "1";
    c.dispatchEvent(new Event("change", { bubbles: true }));
  });
});
