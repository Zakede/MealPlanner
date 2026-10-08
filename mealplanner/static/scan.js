// Receipt / order scanning with something to look at: shrink the photo, upload with progress,
// then a scan over the photo while the AI reads it. Errors stay on the sheet with Try again.
(() => {
  const MAX_SIDE = 1800;

  async function shrink(file) {
    if (!file || !file.type.startsWith("image/") || file.size < 700 * 1024) return file;
    try {
      const bmp = await createImageBitmap(file);
      const k = Math.min(1, MAX_SIDE / Math.max(bmp.width, bmp.height));
      const c = document.createElement("canvas");
      c.width = Math.round(bmp.width * k); c.height = Math.round(bmp.height * k);
      c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
      const blob = await new Promise((ok) => c.toBlob(ok, "image/jpeg", 0.85));
      return blob && blob.size < file.size ? new File([blob], "receipt.jpg", { type: "image/jpeg" }) : file;
    } catch (e) { return file; }
  }

  function sheet(kind, imgSrc) {
    const d = document.createElement("dialog");
    d.className = "scan-sheet";
    d.innerHTML = `
      <div class="ss-photo ${imgSrc ? "" : "no-photo"}">${imgSrc ? `<img alt="">` : `<span class="ss-doc"></span>`}<span class="ss-beam"></span></div>
      <h2 class="ss-title">Getting ready…</h2>
      <div class="ss-bar"><i></i></div>
      <ol class="ss-steps">
        <li data-step="up">Uploading</li>
        <li data-step="read">Reading the ${kind}</li>
        <li data-step="find">Finding the items</li>
      </ol>
      <p class="ss-sub"><span class="ss-time">0 s</span> · usually 10–30 s, keep this open</p>
      <div class="ss-err" hidden><p></p><div class="ss-err-actions">
        <button type="button" class="btn secondary" data-close>Close</button>
        <button type="button" class="btn" data-retry>Try again</button></div></div>`;
    if (imgSrc) d.querySelector("img").src = imgSrc;
    d.addEventListener("cancel", (e) => { if (!d.classList.contains("failed")) e.preventDefault(); });
    document.body.append(d);
    return d;
  }

  function attach(form) {
    const kind = form.dataset.scan || "receipt";
    form.addEventListener("submit", async (e) => {
      if (!window.FormData || !window.XMLHttpRequest) return;   // old browser: normal post
      e.preventDefault();
      const fileInput = form.querySelector('input[type=file][name="photo"]');
      const original = fileInput && fileInput.files[0];
      const img = form.querySelector(".drop-preview img");
      const d = sheet(kind, original && img && img.src ? img.src : "");
      d.showModal();
      const title = d.querySelector(".ss-title"), bar = d.querySelector(".ss-bar i");
      const step = (name, state) => d.querySelector(`[data-step="${name}"]`).className = state;
      const t0 = Date.now();
      const tick = setInterval(() => { d.querySelector(".ss-time").textContent = `${Math.round((Date.now() - t0) / 1000)} s`; }, 500);
      const reset = () => {
        form.querySelectorAll("button").forEach((b) => { if (b.id && b.id.endsWith("go")) b.disabled = false; });
        form.querySelectorAll(".drop").forEach((x) => x.classList.remove("reading"));
        form.querySelectorAll(".rc-wait").forEach((x) => x.hidden = true);
      };
      const fail = (msg) => {
        clearInterval(tick);
        d.classList.add("failed");
        title.textContent = "Couldn't read it";
        const box = d.querySelector(".ss-err");
        box.hidden = false; box.querySelector("p").textContent = msg;
        d.querySelector("[data-close]").onclick = () => { d.close(); d.remove(); reset(); };
        d.querySelector("[data-retry]").onclick = () => { d.close(); d.remove(); form.requestSubmit(); };
      };

      const data = new FormData(form);
      if (original) {
        title.textContent = "Preparing the photo…";
        data.set("photo", await shrink(original));
      }
      step("up", "now"); title.textContent = original ? "Uploading…" : "Sending…";
      // reading has no real progress, so the bar creeps towards 95% and finishes when the answer comes
      let creep = null;
      const reading = () => {
        if (creep) return;
        step("up", "done"); step("read", "now");
        title.textContent = `Scanning your ${kind}…`;
        d.classList.add("scanning");
        let p = 30;
        creep = setInterval(() => {
          p += (95 - p) * 0.04; bar.style.width = p + "%";
          if (p > 62) { step("read", "done"); step("find", "now"); title.textContent = "Finding the items…"; }
        }, 400);
      };

      const xhr = new XMLHttpRequest();
      xhr.open(form.method || "POST", form.action || location.href);
      xhr.upload.onprogress = (ev) => {
        if (!ev.lengthComputable) return;
        const pct = ev.loaded / ev.total;
        bar.style.width = (pct * 30) + "%";
        title.textContent = `Uploading… ${Math.round(pct * 100)}%`;
        if (pct >= 1) reading();
      };
      xhr.upload.onload = reading;
      xhr.onerror = () => { clearInterval(creep); fail("No connection. Check your internet and try again."); };
      xhr.ontimeout = () => { clearInterval(creep); fail("That took too long. Try again, or a smaller, sharper photo."); };
      xhr.timeout = 120000;
      xhr.onload = () => {
        clearInterval(creep);
        reading();
        clearInterval(creep);
        const doc = new DOMParser().parseFromString(xhr.responseText, "text/html");
        const back = new URL(xhr.responseURL || location.href).pathname === location.pathname;
        const err = doc.querySelector(".flash-error");
        if (xhr.status >= 400) return fail("Something went wrong on the server. Try again in a moment.");
        if (back && err) return fail(err.textContent.trim());
        bar.style.width = "100%";
        ["up", "read", "find"].forEach((s) => step(s, "done"));
        d.classList.remove("scanning"); d.classList.add("found");
        title.textContent = "Done!";
        clearInterval(tick);
        // swap in the new page's content and run only its own inline scripts (app.js / ui.js are already running)
        setTimeout(() => {
          const main = doc.querySelector("main");
          if (!main) { document.open(); document.write(xhr.responseText); document.close(); return; }
          const scripts = [...doc.body.querySelectorAll("script:not([src])")].map((s) => s.textContent);
          main.querySelectorAll("script").forEach((s) => s.remove());
          document.querySelector("main").replaceWith(document.adoptNode(main));
          document.title = doc.title;
          window.zettaiEnhance?.(document.querySelector("main"));
          d.close(); d.remove();
          scrollTo(0, 0);
          scripts.forEach((code) => {
            const s = document.createElement("script");
            s.textContent = `(() => {${code}\n})();`;
            document.body.append(s);
          });
        }, 450);
      };
      xhr.send(data);
    });
  }

  document.querySelectorAll("form[data-scan]").forEach(attach);
})();
