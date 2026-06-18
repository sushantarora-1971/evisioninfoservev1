/* Evision admin — Testimonials & Portfolio management (CRUD + image upload).
   Reuses the shared Admin helper and the drawer/toast DOM from dashboard.js. */
(function () {
  if (!Admin.token()) return; // dashboard.js handles the redirect

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // ── toast + drawer (shared DOM, own handlers) ──
  let toastTimer;
  function toast(msg, kind = "ok") {
    const t = $("#toast"); if (!t) return;
    t.textContent = msg; t.className = "toast " + kind;
    clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.add("hidden"), 2600);
  }
  function openDrawer(html) {
    $("#drawerBody").innerHTML = html;
    $("#drawer").classList.remove("hidden"); $("#overlay").classList.remove("hidden");
  }
  function closeDrawer() {
    $("#drawer").classList.add("hidden"); $("#overlay").classList.add("hidden");
  }

  // ── shared view helpers ──
  function table(heads, rows) {
    return `<table class="tbl"><thead><tr>${heads.map(h => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table>`;
  }
  const empty = (t) => `<div class="empty">${esc(t)}</div>`;
  const stars = (n) => "★".repeat(Math.max(0, Math.min(5, n || 0))) || "—";
  const thumbImg = (url, round) => url
    ? `<img class="thumb ${round ? "round" : ""}" src="${esc(url)}" alt="" onerror="this.removeAttribute('src')">`
    : `<div class="thumb ${round ? "round" : ""}"></div>`;

  // ── reusable image-upload field ──
  function imgField(id, url, round) {
    return `<div class="imgfield">
      <div class="imgprev ${round ? "round" : ""}" id="${id}_prev" style="${url ? `background-image:url('${esc(url)}')` : ""}">${url ? "" : "No image"}</div>
      <div class="imgctl">
        <input type="file" accept="image/*" id="${id}_file">
        <input id="${id}_url" placeholder="/uploads/… or https://…" value="${esc(url || "")}" style="margin-top:8px">
      </div></div>`;
  }
  function wireImg(id) {
    const file = $("#" + id + "_file"), url = $("#" + id + "_url"), prev = $("#" + id + "_prev");
    const setPrev = (u) => {
      if (u) { prev.style.backgroundImage = `url('${u}')`; prev.textContent = ""; }
      else { prev.style.backgroundImage = ""; prev.textContent = "No image"; }
    };
    url.addEventListener("input", () => setPrev(url.value.trim()));
    file.addEventListener("change", async () => {
      const f = file.files[0]; if (!f) return;
      const dataUrl = await new Promise((res, rej) => {
        const r = new FileReader(); r.onload = () => res(r.result); r.onerror = rej; r.readAsDataURL(f);
      });
      setPrev(dataUrl); // instant local preview
      try {
        const out = await Admin.api("/api/admin/upload", { method: "POST", body: JSON.stringify({ filename: f.name, data: dataUrl }) });
        url.value = out.url; setPrev(out.url); toast("Image uploaded");
      } catch (ex) { toast(ex.message || "Upload failed", "err"); }
    });
  }
  const getImg = (id) => $("#" + id + "_url").value.trim();

  // ════════════════ TESTIMONIALS ════════════════
  let TESTI = [];
  async function loadTesti() { TESTI = await Admin.api("/api/admin/testimonials"); renderTesti(); }
  function filteredTesti() {
    const q = $("#tSearch").value.trim().toLowerCase();
    return q ? TESTI.filter(t => [t.name, t.role, t.quote].join(" ").toLowerCase().includes(q)) : TESTI;
  }
  function renderTesti() {
    const rows = filteredTesti();
    if (!rows.length) { $("#tWrap").innerHTML = empty("No testimonials yet. Add one to show it on the Clients page."); return; }
    $("#tWrap").innerHTML = table(["", "Name", "Comment", "Rating", "Sort", "Status", ""],
      rows.map(t => `<tr data-t="${t.id}" class="clickable">
        <td>${thumbImg(t.photo, true)}</td>
        <td><b>${esc(t.name)}</b><div class="muted">${esc(t.role)}</div></td>
        <td>${esc(String(t.quote).slice(0, 90))}${String(t.quote).length > 90 ? "…" : ""}</td>
        <td style="color:#e0a800">${stars(t.rating)}</td>
        <td>${t.sort}</td>
        <td>${t.active ? '<span class="pill pill-converted">live</span>' : '<span class="pill pill-closed">hidden</span>'}</td>
        <td><button class="link-btn danger" data-del-t="${t.id}">Delete</button></td></tr>`).join(""));
    $$("#tWrap tr[data-t]").forEach(tr => tr.addEventListener("click", ev => {
      if (ev.target.closest("[data-del-t]")) return; editTesti(Number(tr.dataset.t));
    }));
    $$("#tWrap [data-del-t]").forEach(b => b.addEventListener("click", async ev => {
      ev.stopPropagation(); if (!confirm("Delete this testimonial?")) return;
      await Admin.api("/api/admin/testimonials/" + b.dataset.delT, { method: "DELETE" });
      toast("Testimonial deleted"); loadTesti();
    }));
  }
  function testiForm(t) {
    t = t || {}; const f = (k) => esc(t[k]);
    return `<div class="grid2">
        <div><label>Name</label><input id="tf_name" value="${f("name")}"></div>
        <div><label>Role / company</label><input id="tf_role" value="${f("role")}"></div>
      </div>
      <label>Comment</label><textarea id="tf_quote" rows="4" class="full">${f("quote")}</textarea>
      <div class="grid2">
        <div><label>Rating (1–5)</label><input id="tf_rating" type="number" min="1" max="5" value="${t.rating != null ? t.rating : 5}"></div>
        <div><label>Sort order (lower = first)</label><input id="tf_sort" type="number" value="${t.sort != null ? t.sort : 0}"></div>
      </div>
      <label>Photo</label>${imgField("tf_photo", t.photo, true)}
      <label class="ck"><input type="checkbox" id="tf_active" ${t.active === 0 ? "" : "checked"}> Show on the website</label>`;
  }
  const readTesti = () => ({
    name: $("#tf_name").value, role: $("#tf_role").value, quote: $("#tf_quote").value,
    rating: Number($("#tf_rating").value || 5), sort: Number($("#tf_sort").value || 0),
    photo: getImg("tf_photo"), active: $("#tf_active").checked ? 1 : 0,
  });
  function editTesti(id) {
    const t = TESTI.find(x => x.id === id); if (!t) return;
    openDrawer(`<h2 class="drawer-title">Edit testimonial</h2>${testiForm(t)}
      <div class="drawer-actions"><button class="btn-primary" id="tSave">Save changes</button></div>`);
    wireImg("tf_photo");
    $("#tSave").addEventListener("click", async () => {
      const b = readTesti();
      if (!b.name.trim() || !b.quote.trim()) { toast("Name and comment are required", "err"); return; }
      await Admin.api("/api/admin/testimonials/" + id, { method: "PATCH", body: JSON.stringify(b) });
      toast("Saved"); closeDrawer(); loadTesti();
    });
  }
  $("#addTestiBtn").addEventListener("click", () => {
    openDrawer(`<h2 class="drawer-title">Add testimonial</h2>${testiForm()}
      <div class="drawer-actions"><button class="btn-primary" id="tCreate">Add testimonial</button></div>`);
    wireImg("tf_photo");
    $("#tCreate").addEventListener("click", async () => {
      const b = readTesti();
      if (!b.name.trim() || !b.quote.trim()) { toast("Name and comment are required", "err"); return; }
      await Admin.api("/api/admin/testimonials", { method: "POST", body: JSON.stringify(b) });
      toast("Testimonial added"); closeDrawer(); loadTesti();
    });
  });
  $("#tSearch").addEventListener("input", renderTesti);

  // ════════════════ PORTFOLIO ════════════════
  let WORK = [];
  async function loadPortfolio() { WORK = await Admin.api("/api/admin/portfolio"); renderPortfolio(); }
  function filteredWork() {
    const q = $("#pSearch").value.trim().toLowerCase();
    return q ? WORK.filter(w => [w.title, w.client, w.category, w.summary].join(" ").toLowerCase().includes(q)) : WORK;
  }
  function renderPortfolio() {
    const rows = filteredWork();
    if (!rows.length) { $("#pWrap").innerHTML = empty("No portfolio items yet. Add your first case study."); return; }
    $("#pWrap").innerHTML = table(["", "Title", "Category", "Result", "Sort", "Status", ""],
      rows.map(w => `<tr data-p="${w.id}" class="clickable">
        <td>${thumbImg(w.image, false)}</td>
        <td><b>${esc(w.title)}</b><div class="muted">${esc(w.client)}</div></td>
        <td><span class="tag">${esc(w.category) || "—"}</span></td>
        <td>${esc(w.metric) || "—"}</td>
        <td>${w.sort}</td>
        <td>${w.active ? '<span class="pill pill-converted">live</span>' : '<span class="pill pill-closed">hidden</span>'}</td>
        <td><button class="link-btn danger" data-del-p="${w.id}">Delete</button></td></tr>`).join(""));
    $$("#pWrap tr[data-p]").forEach(tr => tr.addEventListener("click", ev => {
      if (ev.target.closest("[data-del-p]")) return; editWork(Number(tr.dataset.p));
    }));
    $$("#pWrap [data-del-p]").forEach(b => b.addEventListener("click", async ev => {
      ev.stopPropagation(); if (!confirm("Delete this portfolio item?")) return;
      await Admin.api("/api/admin/portfolio/" + b.dataset.delP, { method: "DELETE" });
      toast("Item deleted"); loadPortfolio();
    }));
  }
  function workForm(w) {
    w = w || {}; const f = (k) => esc(w[k]);
    return `<div class="grid2">
        <div><label>Title</label><input id="pf_title" value="${f("title")}"></div>
        <div><label>Client</label><input id="pf_client" value="${f("client")}"></div>
        <div><label>Category</label><input id="pf_category" value="${f("category")}" placeholder="e.g. SEO, PPC, Local SEO"></div>
        <div><label>Headline result</label><input id="pf_metric" value="${f("metric")}" placeholder="e.g. +212% organic"></div>
      </div>
      <label>Summary</label><textarea id="pf_summary" rows="3" class="full">${f("summary")}</textarea>
      <label>Case-study / live link (optional)</label><input id="pf_url" value="${f("url")}" placeholder="https://…">
      <div class="grid2">
        <div><label>Sort order (lower = first)</label><input id="pf_sort" type="number" value="${w.sort != null ? w.sort : 0}"></div>
      </div>
      <label>Cover image</label>${imgField("pf_image", w.image, false)}
      <label class="ck"><input type="checkbox" id="pf_active" ${w.active === 0 ? "" : "checked"}> Show on the website</label>`;
  }
  const readWork = () => ({
    title: $("#pf_title").value, client: $("#pf_client").value, category: $("#pf_category").value,
    metric: $("#pf_metric").value, summary: $("#pf_summary").value, url: $("#pf_url").value,
    sort: Number($("#pf_sort").value || 0), image: getImg("pf_image"), active: $("#pf_active").checked ? 1 : 0,
  });
  function editWork(id) {
    const w = WORK.find(x => x.id === id); if (!w) return;
    openDrawer(`<h2 class="drawer-title">Edit portfolio item</h2>${workForm(w)}
      <div class="drawer-actions"><button class="btn-primary" id="pSave">Save changes</button></div>`);
    wireImg("pf_image");
    $("#pSave").addEventListener("click", async () => {
      const b = readWork();
      if (!b.title.trim()) { toast("Title is required", "err"); return; }
      await Admin.api("/api/admin/portfolio/" + id, { method: "PATCH", body: JSON.stringify(b) });
      toast("Saved"); closeDrawer(); loadPortfolio();
    });
  }
  $("#addWorkBtn").addEventListener("click", () => {
    openDrawer(`<h2 class="drawer-title">Add portfolio item</h2>${workForm()}
      <div class="drawer-actions"><button class="btn-primary" id="pCreate">Add item</button></div>`);
    wireImg("pf_image");
    $("#pCreate").addEventListener("click", async () => {
      const b = readWork();
      if (!b.title.trim()) { toast("Title is required", "err"); return; }
      await Admin.api("/api/admin/portfolio", { method: "POST", body: JSON.stringify(b) });
      toast("Portfolio item added"); closeDrawer(); loadPortfolio();
    });
  });
  $("#pSearch").addEventListener("input", renderPortfolio);

  // ── lazy-load each section the first time its tab is opened ──
  let tLoaded = false, pLoaded = false;
  $('[data-view="testimonials"]').addEventListener("click", () => { if (!tLoaded) { tLoaded = true; loadTesti().catch(() => {}); } });
  $('[data-view="portfolio"]').addEventListener("click", () => { if (!pLoaded) { pLoaded = true; loadPortfolio().catch(() => {}); } });
})();
