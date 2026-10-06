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

// "Got work" tick on the week plan: ticking opens the hours, unticking makes it a day off right away.
document.querySelectorAll(".work-tick").forEach((form) => {
  const tick = form.querySelector("[data-work-tick]");
  tick.addEventListener("change", () => {
    if (tick.checked) {
      form.classList.add("open");
      form.querySelector("input[type=time]").focus();
    } else {
      form.submit();
    }
  });
  form.querySelector("[data-work-open]")?.addEventListener("click", () => form.classList.toggle("open"));
});
