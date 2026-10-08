// Receipt / order scanning with something to look at, right under the photo (the page stays usable):
// shrink the photo, upload with progress, then a scan over the photo while the AI reads it.
// Cancel any time. If the phone drops the connection, the server still keeps the result (see lastscan.py).
(() => {
  const MAX_SIDE = 1600;

  async function shrink(file) {
    if (!file || !file.type.startsWith("image/") || file.size < 600 * 1024) return file;
    try {
      const bmp = await createImageBitmap(file);
      const k = Math.min(1, MAX_SIDE / Math.max(bmp.width, bmp.height));
      const c = document.createElement("canvas");
      c.width = Math.round(bmp.width * k); c.height = Math.round(bmp.height * k);
      c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
      bmp.close?.();
      const blob = await new Promise((ok) => c.toBlob(ok, "image/jpeg", 0.82));
      c.width = c.height = 0;   // frees the canvas memory right away on iPhone
      return blob && blob.size < file.size ? new File([blob], "receipt.jpg", { type: "image/jpeg" }) : file;
    } catch (e) { return file; }
  }

  function panel(kind) {
    const p = document.createElement("div");
    p.className = "scan-inline";
    p.setAttribute("aria-live", "polite");
    p.innerHTML = `
      <div class="si-top"><b class="si-title">Getting ready…</b><span class="si-time">0 s</span></div>
      <div class="ss-bar"><i></i></div>
      <ol class="ss-steps">
        <li data-step="up">Uploading</li>
        <li data-step="read">Reading the ${kind}</li>
        <li data-step="find">Finding the items</li>
      </ol>
      <p class="si-sub">Usually 15–40 s. You can scroll around while it works.</p>
      <div class="ss-err" hidden><p></p></div>
      <div class="si-actions">
        <button type="button" class="btn secondary" data-cancel>Cancel</button>
        <button type="button" class="btn" data-retry hidden>Try again</button>
        <a class="btn" data-last hidden>Check for it</a>
      </div>`;
    return p;
  }

  function attach(form) {
    const kind = form.dataset.scan || "receipt";
    let busy = false;
    form.addEventListener("submit", async (e) => {
      if (!window.FormData || !window.XMLHttpRequest) return;   // old browser: normal post
      e.preventDefault();
      if (busy) return;
      busy = true;
      form.querySelectorAll(".rc-wait").forEach((x) => x.hidden = true);   // the old "reading…" line
      const drop = form.querySelector(".drop");
      const goBtn = form.querySelector("button:not([type=button])");
      const fileInput = form.querySelector('input[type=file][name="photo"]');
      const original = fileInput && fileInput.files[0];
      form.querySelector(".scan-inline")?.remove();
      const p = panel(kind);
      (goBtn || form.lastElementChild).after(p);
      if (goBtn) goBtn.hidden = true;
      drop?.classList.add("reading");
      p.scrollIntoView({ block: "nearest", behavior: "smooth" });

      const title = p.querySelector(".si-title"), bar = p.querySelector(".ss-bar i");
      const step = (name, state) => p.querySelector(`[data-step="${name}"]`).className = state;
      const t0 = Date.now();
      const tick = setInterval(() => { p.querySelector(".si-time").textContent = `${Math.round((Date.now() - t0) / 1000)} s`; }, 500);
      let creep = null, xhr = null, done = false;
      const stop = () => { clearInterval(tick); clearInterval(creep); drop?.classList.remove("reading"); };
      const finish = () => { done = true; busy = false; stop(); };
      const reset = () => { finish(); p.remove(); if (goBtn) { goBtn.hidden = false; goBtn.disabled = false; } };
      const fail = (msg, lastUrl) => {
        finish();
        p.classList.add("failed");
        title.textContent = "Couldn't read it";
        const box = p.querySelector(".ss-err");
        box.hidden = false; box.querySelector("p").textContent = msg;
        p.querySelector("[data-cancel]").textContent = "Close";
        p.querySelector("[data-retry]").hidden = false;
        if (lastUrl) { const a = p.querySelector("[data-last]"); a.href = lastUrl; a.hidden = false; }
      };
      p.querySelector("[data-cancel]").onclick = () => { if (xhr && !done) xhr.abort(); reset(); };
      p.querySelector("[data-retry]").onclick = () => { reset(); form.requestSubmit(goBtn || undefined); };

      const data = new FormData(form);
      if (original) {
        title.textContent = "Preparing the photo…";
        data.set("photo", await shrink(original));
      }
      if (done) return;   // cancelled while shrinking
      step("up", "now"); title.textContent = original ? "Uploading…" : "Sending…";
      // reading has no real progress, so the bar creeps towards 95% and finishes when the answer comes
      const reading = () => {
        if (creep || done) return;
        step("up", "done"); step("read", "now");
        title.textContent = `Scanning your ${kind}…`;
        let pct = 30;
        creep = setInterval(() => {
          pct += (95 - pct) * 0.03; bar.style.width = pct + "%";
          if (pct > 60) { step("read", "done"); step("find", "now"); title.textContent = "Finding the items…"; }
        }, 400);
      };

      xhr = new XMLHttpRequest();
      xhr.open("POST", form.action || location.href);
      xhr.upload.onprogress = (ev) => {
        if (!ev.lengthComputable) return;
        const f = ev.loaded / ev.total;
        bar.style.width = (f * 30) + "%";
        title.textContent = `Uploading… ${Math.round(f * 100)}%`;
        if (f >= 1) reading();
      };
      xhr.upload.onload = reading;
      const dropped = "The connection dropped (it happens when the screen locks or you switch apps). " +
        "The scan may still have finished: tap Check for it.";
      xhr.onerror = () => { if (!done) fail(dropped, form.dataset.last); };
      xhr.ontimeout = () => { if (!done) fail("That took too long. Tap Check for it, or try a closer photo.", form.dataset.last); };
      xhr.timeout = 150000;
      xhr.onload = () => {
        if (done) return;
        const doc = new DOMParser().parseFromString(xhr.responseText, "text/html");
        const back = new URL(xhr.responseURL || location.href).pathname === location.pathname;
        const err = doc.querySelector(".flash-error");
        if (xhr.status >= 400) return fail("Something went wrong on the server. Try again in a moment.");
        if (back && err) return fail(err.textContent.trim());
        finish();
        bar.style.width = "100%";
        ["up", "read", "find"].forEach((s) => step(s, "done"));
        p.classList.add("found");
        title.textContent = "Done!";
        // swap in the new page's content and run only its own inline scripts (app.js / ui.js are already running)
        setTimeout(() => {
          const main = doc.querySelector("main");
          if (!main) { location.href = form.dataset.last || location.href; return; }
          const scripts = [...doc.body.querySelectorAll("script:not([src])")].map((s) => s.textContent);
          main.querySelectorAll("script").forEach((s) => s.remove());
          document.querySelector("main").replaceWith(document.adoptNode(main));
          document.title = doc.title;
          window.zettaiEnhance?.(document.querySelector("main"));
          scrollTo(0, 0);
          scripts.forEach((code) => {
            const s = document.createElement("script");
            s.textContent = `(() => {${code}\n})();`;
            document.body.append(s);
          });
        }, 400);
      };
      xhr.send(data);
    });
  }

  document.querySelectorAll("form[data-scan]").forEach(attach);
})();
