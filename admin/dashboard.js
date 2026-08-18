/* Evision admin dashboard — views, data loading, drawer detail, actions. */
(function () {
  // Gate: must be logged in.
  if (!Admin.token()) { location.replace("login.html"); return; }

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fmtDate = (iso) => { try { return new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }); } catch { return iso; } };

  let ENQUIRIES = [];
  let CLIENTS = [];
  const IS_ADMIN = Admin.isAdmin();

  $("#whoami").textContent = (Admin.name() || Admin.email() || "") + (IS_ADMIN ? "" : " · author");
  { const bs = document.getElementById("brandSub"); if (bs) bs.textContent = IS_ADMIN ? "Admin" : "Author"; }

  // ── Settings: account profile card (name + bio, editable) ──
  (function initProfile() {
    const em = Admin.email() || "";
    const initialsOf = (nm) => ((nm ? nm.split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join("")
      : em.slice(0, 1)).toUpperCase() || "?");
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    function paintHeader(nm) {
      set("setAvatar", initialsOf(nm));
      set("setName", nm || em || "—");
      set("setEmail", em);
      const roleEl = document.getElementById("setRole");
      if (roleEl) {
        roleEl.textContent = IS_ADMIN ? "Main admin" : "Author";
        roleEl.className = "pill " + (IS_ADMIN ? "pill-converted" : "pill-contacted");
      }
    }
    paintHeader(Admin.name() || "");
    const nameInp = document.getElementById("pfName"), bioInp = document.getElementById("pfBio");
    if (nameInp) nameInp.value = Admin.name() || "";
    // Pull the freshest name + bio from the server.
    Admin.api("/api/admin/me").then(me => {
      if (nameInp) nameInp.value = me.name || "";
      if (bioInp) bioInp.value = me.bio || "";
      paintHeader(me.name || "");
    }).catch(() => {});
    const form = document.getElementById("profileForm");
    if (form) form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const msg = document.getElementById("pfMsg"); if (msg) { msg.textContent = ""; msg.className = "auth-err"; }
      const name = (nameInp.value || "").trim(), bio = (bioInp.value || "").trim();
      try {
        const res = await Admin.api("/api/admin/profile", { method: "POST", body: JSON.stringify({ name, bio }) });
        localStorage.setItem("evision_admin_name", res.name || "");   // byline default + sidebar
        paintHeader(res.name || "");
        $("#whoami").textContent = (res.name || em) + (IS_ADMIN ? "" : " · author");
        if (msg) { msg.className = "auth-err ok"; msg.textContent = "Profile saved."; }
        toast("Profile saved");
      } catch (ex) { if (msg) msg.textContent = ex.message || "Save failed"; else toast(ex.message || "Save failed", "err"); }
    });
  })();

  // ── Toast ──
  let toastTimer;
  function toast(msg, kind = "ok") {
    const t = $("#toast");
    t.textContent = msg; t.className = "toast " + kind;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.add("hidden"), 2600);
  }

  // ── Navigation ──
  $$(".nav-item").forEach(btn => btn.addEventListener("click", () => {
    $$(".nav-item").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    const view = btn.dataset.view;
    $$(".view").forEach(v => v.classList.add("hidden"));
    $("#view-" + view).classList.remove("hidden");
    closeDrawer();
  }));

  $("#logoutBtn").addEventListener("click", async () => {
    try { await Admin.api("/api/admin/logout", { method: "POST" }); } catch {}
    Admin.clear();
    location.replace("login.html");
  });

  // ── Drawer ──
  function openDrawer(html) {
    $("#drawerBody").innerHTML = html;
    $("#drawer").classList.remove("hidden");
    $("#overlay").classList.remove("hidden");
  }
  function closeDrawer() {
    $("#drawer").classList.add("hidden");
    $("#overlay").classList.add("hidden");
  }
  $("#drawerClose").addEventListener("click", closeDrawer);
  $("#overlay").addEventListener("click", closeDrawer);

  // ───────────────── Data loading ─────────────────
  let LAST_NEW = null;   // previous unread count, for the new-lead chime

  async function loadStats() {
    try {
      const s = await Admin.api("/api/admin/stats");
      $("#sEnq").textContent = s.enquiries;
      $("#sNew").textContent = s.new;
      $("#sCli").textContent = s.clients;
      $("#sAct").textContent = s.active;
      $("#sSpam").textContent = s.spam ?? 0;
      $("#navNew").textContent = s.new ? s.new : "";
      $("#navNew").style.display = s.new ? "" : "none";
      // Never fires on the first load — LAST_NEW is null until then.
      if (LAST_NEW !== null && s.new > LAST_NEW) Ring.announce(s.new - LAST_NEW);
      LAST_NEW = s.new;
    } catch (e) { /* handled by api() */ }
  }

  let ENQ_SIG = "";
  async function loadEnquiries() {
    ENQUIRIES = await Admin.api("/api/admin/enquiries");
    // The 30s poll calls this repeatedly; only repaint when something actually
    // changed, so the table doesn't blink under whoever is reading it.
    const sig = ENQUIRIES.map(e => e.id + ":" + e.status).join(",");
    if (sig === ENQ_SIG) return;
    ENQ_SIG = sig;
    renderEnquiries();
    renderRecent();
  }

  async function loadClients() {
    CLIENTS = await Admin.api("/api/admin/clients");
    renderClients();
  }

  // ───────────────── New-lead ring (while the panel is open) ─────────────────
  // The server pushes to your phone (Telegram / ntfy / call). This is the
  // desk-side twin: the panel polls every 30s and chimes so a lead sitting on
  // the site doesn't wait for someone to notice an email.
  const Ring = (function () {
    const KEY = "evision_ring";
    const btn = $("#ringToggle");
    let on = localStorage.getItem(KEY) !== "0";
    let ctx = null, baseTitle = document.title;

    function paint() { if (btn) btn.textContent = on ? "🔔 Alerts on" : "🔕 Alerts off"; }
    // Browsers keep audio suspended until the user interacts with the page.
    function unlock() {
      try {
        ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
        if (ctx.state === "suspended") ctx.resume();
      } catch (e) { /* no audio available — the toast still shows */ }
    }
    function chime() {
      unlock();
      if (!ctx) return;
      // Three rising beeps — recognisable across a room, over in half a second.
      [0, 0.18, 0.36].forEach((at, i) => {
        const osc = ctx.createOscillator(), gain = ctx.createGain();
        osc.type = "sine";
        osc.frequency.value = [880, 1108, 1318][i];
        gain.gain.setValueAtTime(0.0001, ctx.currentTime + at);
        gain.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + at + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + at + 0.16);
        osc.connect(gain).connect(ctx.destination);
        osc.start(ctx.currentTime + at);
        osc.stop(ctx.currentTime + at + 0.18);
      });
    }
    function desktopNote(count, lead) {
      if (!window.Notification || Notification.permission !== "granted") return;
      const n = new Notification(count > 1 ? `${count} new leads` : "New lead — " + (lead?.name || ""),
        { body: lead ? [lead.phone, lead.service].filter(Boolean).join(" · ") : "Open the admin panel",
          tag: "evision-lead" });
      n.onclick = () => { window.focus(); n.close(); };
    }

    if (btn) btn.addEventListener("click", () => {
      on = !on;
      localStorage.setItem(KEY, on ? "1" : "0");
      paint();
      if (on) {
        chime();                                    // confirm it's audible
        if (window.Notification && Notification.permission === "default") {
          Notification.requestPermission();         // needs this user gesture
        }
        toast("You'll be alerted when a new lead arrives");
      } else { toast("Alerts muted"); }
    });
    // First click anywhere is enough to let audio play later.
    document.addEventListener("click", unlock, { once: true });
    window.addEventListener("focus", () => { document.title = baseTitle; });
    paint();

    return {
      announce(count) {
        // ENQUIRIES is id-descending and refreshed just before this runs.
        const lead = ENQUIRIES.find(e => e.status === "new");
        toast(count > 1 ? `${count} new enquiries` : "New enquiry just came in");
        document.title = `(${count}) New lead — ${baseTitle}`;
        if (!on) return;
        chime();
        desktopNote(count, lead);
      },
    };
  })();

  // ───────────────── Status pills ─────────────────
  const statusClass = (s) => "pill pill-" + (s || "new");

  // ───────────────── Dashboard recent ─────────────────
  function renderRecent() {
    const rows = ENQUIRIES.filter(e => e.status !== "spam").slice(0, 6);
    if (!rows.length) { $("#recentWrap").innerHTML = empty("No enquiries yet."); return; }
    $("#recentWrap").innerHTML = table(
      ["Name", "Service", "Type", "Status", "Received"],
      rows.map(e => `<tr data-enq="${e.id}" class="clickable">
        <td><b>${esc(e.name)}</b><div class="muted">${esc(e.email)}</div></td>
        <td>${esc(e.service) || "—"}</td>
        <td><span class="tag">${esc(e.type || "quote")}</span></td>
        <td><span class="${statusClass(e.status)}">${esc(e.status)}</span></td>
        <td class="muted">${fmtDate(e.created_at)}</td></tr>`).join("")
    );
    wireEnquiryRows("#recentWrap");
  }

  // ───────────────── Enquiries view ─────────────────
  function filteredEnquiries() {
    const q = $("#enqSearch").value.trim().toLowerCase();
    const type = $("#enqType").value;
    const status = $("#enqStatus").value;
    return ENQUIRIES.filter(e => {
      // Quarantined spam only shows when it's explicitly asked for.
      if (status !== "spam" && e.status === "spam") return false;
      if (type && (e.type || "quote") !== type) return false;
      if (status && e.status !== status) return false;
      if (q) {
        const hay = [e.name, e.email, e.company, e.phone, e.service].join(" ").toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }

  function renderEnquiries() {
    const rows = filteredEnquiries();
    const spamView = $("#enqStatus").value === "spam";
    $("#purgeSpamBtn").classList.toggle("hidden", !spamView);
    if (!rows.length) {
      $("#enqWrap").innerHTML = empty(spamView ? "No spam in quarantine. 🎉" : "No enquiries match.");
      return;
    }
    $("#enqWrap").innerHTML = table(
      ["Name", "Contact", "Service", "Budget", "Type", "Status", "Received", ""],
      rows.map(e => `<tr data-enq="${e.id}" class="clickable">
        <td><b>${esc(e.name)}</b>${e.company ? `<div class="muted">${esc(e.company)}</div>` : ""}${
          e.status === "spam" && e.spam_reason ? `<div class="muted">🚫 ${esc(e.spam_reason)}</div>` : ""}</td>
        <td>${esc(e.email)}<div class="muted">${esc(e.phone) || ""}</div></td>
        <td>${esc(e.service) || "—"}</td>
        <td>${esc(e.budget) || "—"}</td>
        <td><span class="tag">${esc(e.type || "quote")}</span></td>
        <td><span class="${statusClass(e.status)}">${esc(e.status)}</span></td>
        <td class="muted">${fmtDate(e.created_at)}</td>
        <td><button class="link-btn danger" data-del-enq="${e.id}">Delete</button></td></tr>`).join("")
    );
    wireEnquiryRows("#enqWrap");
  }

  function wireEnquiryRows(scope) {
    $$(scope + " tr[data-enq]").forEach(tr => {
      tr.addEventListener("click", (ev) => {
        if (ev.target.closest("[data-del-enq]")) return;
        showEnquiry(Number(tr.dataset.enq));
      });
    });
    $$(scope + " [data-del-enq]").forEach(b => b.addEventListener("click", async (ev) => {
      ev.stopPropagation();
      if (!confirm("Delete this enquiry permanently?")) return;
      await Admin.api("/api/admin/enquiries/" + b.dataset.delEnq, { method: "DELETE" });
      toast("Enquiry deleted");
      await loadEnquiries(); await loadStats();
    }));
  }

  function showEnquiry(id) {
    const e = ENQUIRIES.find(x => x.id === id);
    if (!e) return;
    openDrawer(`
      <h2 class="drawer-title">${esc(e.name)}</h2>
      <span class="${statusClass(e.status)}">${esc(e.status)}</span>
      <span class="tag" style="margin-left:6px">${esc(e.type || "quote")}</span>
      <dl class="kv">
        <dt>Email</dt><dd><a href="mailto:${esc(e.email)}">${esc(e.email)}</a></dd>
        <dt>Phone</dt><dd>${e.phone ? `<a href="tel:${esc(e.phone)}">${esc(e.phone)}</a>` : "—"}</dd>
        <dt>Company</dt><dd>${esc(e.company) || "—"}</dd>
        <dt>Website</dt><dd>${e.website ? `<a href="${esc(e.website)}" target="_blank" rel="noopener">${esc(e.website)}</a>` : "—"}</dd>
        <dt>Service</dt><dd>${esc(e.service) || "—"}</dd>
        <dt>Budget</dt><dd>${esc(e.budget) || "—"}</dd>
        <dt>Source</dt><dd>${esc(e.source) || "—"}</dd>
        <dt>Contact consent</dt><dd>${e.consent ? "✅ SMS/RCS/Call/Email/WhatsApp + T&amp;C" : "— not given"}</dd>
        <dt>Marketing</dt><dd>${e.marketing ? "✅ Opted in" : "Not opted in"}</dd>
        <dt>Received</dt><dd>${fmtDate(e.created_at)}</dd>
        <dt>IP</dt><dd>${esc(e.ip) || "—"}</dd>
        <dt>Spam score</dt><dd>${e.spam_score || 0}${e.spam_reason ? ` — ${esc(e.spam_reason)}` : ""}</dd>
      </dl>
      <h3 class="drawer-h3">Message</h3>
      <p class="msg-box">${esc(e.message) || "<span class='muted'>No message provided.</span>"}</p>

      <h3 class="drawer-h3">Status</h3>
      <select id="dStatus" class="full">
        ${["new", "contacted", "converted", "closed", "spam"].map(s => `<option value="${s}" ${e.status === s ? "selected" : ""}>${s}</option>`).join("")}
      </select>

      <h3 class="drawer-h3">Internal notes</h3>
      <textarea id="dNotes" class="full" rows="4" placeholder="Add notes…">${esc(e.notes)}</textarea>

      <div class="drawer-actions">
        <button class="btn-primary" id="dSave">Save changes</button>
        ${e.status === "spam"
          ? `<button class="btn-ghost" id="dNotSpam">Not spam — restore</button>`
          : `<button class="btn-ghost" id="dSpam">Mark as spam</button>`}
        ${e.status !== "converted" && e.status !== "spam" ? `<button class="btn-ghost" id="dConvert">Convert to client →</button>` : ""}
      </div>
    `);
    // One-click spam / not-spam, so triaging a junk lead is a single action.
    async function setStatus(status, note) {
      await Admin.api("/api/admin/enquiries/" + id, {
        method: "PATCH", body: JSON.stringify({ status }),
      });
      toast(note);
      closeDrawer(); await loadEnquiries(); await loadStats();
    }
    const spamBtn = $("#dSpam"), notSpamBtn = $("#dNotSpam");
    if (spamBtn) spamBtn.addEventListener("click", () => setStatus("spam", "Marked as spam"));
    if (notSpamBtn) notSpamBtn.addEventListener("click", () => setStatus("new", "Restored to new enquiries"));
    $("#dSave").addEventListener("click", async () => {
      await Admin.api("/api/admin/enquiries/" + id, {
        method: "PATCH",
        body: JSON.stringify({ status: $("#dStatus").value, notes: $("#dNotes").value }),
      });
      toast("Saved");
      closeDrawer(); await loadEnquiries(); await loadStats();
    });
    const conv = $("#dConvert");
    if (conv) conv.addEventListener("click", async () => {
      if (!confirm("Create a client record from this enquiry?")) return;
      await Admin.api("/api/admin/enquiries/" + id + "/convert", { method: "POST" });
      toast("Converted to client");
      closeDrawer();
      await loadEnquiries(); await loadClients(); await loadStats();
    });
  }

  $("#enqSearch").addEventListener("input", renderEnquiries);
  $("#enqType").addEventListener("change", renderEnquiries);
  $("#enqStatus").addEventListener("change", renderEnquiries);

  $("#purgeSpamBtn").addEventListener("click", async () => {
    const n = ENQUIRIES.filter(e => e.status === "spam").length;
    if (!n || !confirm(`Permanently delete ${n} spam enquir${n === 1 ? "y" : "ies"}?`)) return;
    const r = await Admin.api("/api/admin/enquiries/spam", { method: "DELETE" });
    toast(`Deleted ${r.deleted} spam enquiries`);
    await loadEnquiries(); await loadStats();
  });

  // ───────────────── Clients view ─────────────────
  function filteredClients() {
    const q = $("#cliSearch").value.trim().toLowerCase();
    if (!q) return CLIENTS;
    return CLIENTS.filter(c => [c.name, c.email, c.company, c.service].join(" ").toLowerCase().includes(q));
  }

  function renderClients() {
    const rows = filteredClients();
    if (!rows.length) { $("#cliWrap").innerHTML = empty("No clients yet. Add one or convert an enquiry."); return; }
    $("#cliWrap").innerHTML = table(
      ["Name", "Contact", "Service", "Plan", "Value", "Status", ""],
      rows.map(c => `<tr data-cli="${c.id}" class="clickable">
        <td><b>${esc(c.name)}</b>${c.company ? `<div class="muted">${esc(c.company)}</div>` : ""}</td>
        <td>${esc(c.email) || "—"}<div class="muted">${esc(c.phone) || ""}</div></td>
        <td>${esc(c.service) || "—"}</td>
        <td>${esc(c.plan) || "—"}</td>
        <td>${esc(c.value) || "—"}</td>
        <td><span class="${statusClass(c.status === 'active' ? 'converted' : c.status)}">${esc(c.status)}</span></td>
        <td><button class="link-btn danger" data-del-cli="${c.id}">Delete</button></td></tr>`).join("")
    );
    $$("#cliWrap tr[data-cli]").forEach(tr => tr.addEventListener("click", (ev) => {
      if (ev.target.closest("[data-del-cli]")) return;
      showClient(Number(tr.dataset.cli));
    }));
    $$("#cliWrap [data-del-cli]").forEach(b => b.addEventListener("click", async (ev) => {
      ev.stopPropagation();
      if (!confirm("Delete this client?")) return;
      await Admin.api("/api/admin/clients/" + b.dataset.delCli, { method: "DELETE" });
      toast("Client deleted");
      await loadClients(); await loadStats();
    }));
  }

  function clientForm(c) {
    c = c || {};
    const f = (k) => esc(c[k]);
    return `
      <div class="grid2">
        <div><label>Name</label><input id="cf_name" value="${f('name')}"></div>
        <div><label>Company</label><input id="cf_company" value="${f('company')}"></div>
        <div><label>Email</label><input id="cf_email" value="${f('email')}"></div>
        <div><label>Phone</label><input id="cf_phone" value="${f('phone')}"></div>
        <div><label>Website</label><input id="cf_website" value="${f('website')}"></div>
        <div><label>Service</label><input id="cf_service" value="${f('service')}"></div>
        <div><label>Plan</label><input id="cf_plan" value="${f('plan')}"></div>
        <div><label>Value (₹/mo)</label><input id="cf_value" value="${f('value')}"></div>
        <div><label>Status</label><select id="cf_status">
          ${["active", "paused", "churned"].map(s => `<option ${c.status === s ? "selected" : ""}>${s}</option>`).join("")}
        </select></div>
      </div>
      <label>Notes</label><textarea id="cf_notes" rows="3" class="full">${f('notes')}</textarea>`;
  }

  function readClientForm() {
    return {
      name: $("#cf_name").value, company: $("#cf_company").value,
      email: $("#cf_email").value, phone: $("#cf_phone").value,
      website: $("#cf_website").value, service: $("#cf_service").value,
      plan: $("#cf_plan").value, value: $("#cf_value").value,
      status: $("#cf_status").value, notes: $("#cf_notes").value,
    };
  }

  function showClient(id) {
    const c = CLIENTS.find(x => x.id === id);
    if (!c) return;
    openDrawer(`<h2 class="drawer-title">Edit client</h2>${clientForm(c)}
      <div class="drawer-actions"><button class="btn-primary" id="cSave">Save changes</button></div>`);
    $("#cSave").addEventListener("click", async () => {
      await Admin.api("/api/admin/clients/" + id, { method: "PATCH", body: JSON.stringify(readClientForm()) });
      toast("Client updated"); closeDrawer(); await loadClients();
    });
  }

  $("#addClientBtn").addEventListener("click", () => {
    openDrawer(`<h2 class="drawer-title">Add client</h2>${clientForm()}
      <div class="drawer-actions"><button class="btn-primary" id="cCreate">Create client</button></div>`);
    $("#cCreate").addEventListener("click", async () => {
      const body = readClientForm();
      if (!body.name.trim()) { toast("Name is required", "err"); return; }
      await Admin.api("/api/admin/clients", { method: "POST", body: JSON.stringify(body) });
      toast("Client added"); closeDrawer(); await loadClients(); await loadStats();
    });
  });

  $("#cliSearch").addEventListener("input", renderClients);

  // ───────────────── Settings ─────────────────
  $("#pwForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = $("#pwMsg"); msg.textContent = ""; msg.className = "auth-err";
    try {
      await Admin.api("/api/admin/change-password", {
        method: "POST",
        body: JSON.stringify({ current: $("#pwCurrent").value, new: $("#pwNew").value }),
      });
      msg.className = "auth-err ok"; msg.textContent = "Password updated.";
      $("#pwForm").reset();
    } catch (ex) { msg.textContent = ex.message; }
  });

  // ───────────────── Pricing & Offers ─────────────────
  let SERVICES = [], OFFERS = [];

  async function loadPricing() {
    [SERVICES, OFFERS] = await Promise.all([
      Admin.api("/api/admin/services"),
      Admin.api("/api/admin/offers"),
    ]);
    renderOffers();
    renderServices();
  }

  function renderOffers() {
    if (!OFFERS.length) { $("#offersWrap").innerHTML = `<div class="muted">No offers yet.</div>`; return; }
    $("#offersWrap").innerHTML = OFFERS.map(o => `
      <div class="offer-row">
        <div>
          <b>${esc(o.name)}</b> <span class="tag">${o.discount_pct}% off</span>
          ${o.active ? '<span class="pill pill-converted">active</span>' : ''}
          ${o.note ? `<div class="muted">${esc(o.note)}</div>` : ''}
        </div>
        <div class="offer-actions">
          <button class="link-btn" data-offer-toggle="${o.id}" data-active="${o.active}">${o.active ? 'Deactivate' : 'Activate'}</button>
          <button class="link-btn danger" data-offer-del="${o.id}">Delete</button>
        </div>
      </div>`).join("");
    $$("[data-offer-toggle]").forEach(b => b.addEventListener("click", async () => {
      await Admin.api("/api/admin/offers/" + b.dataset.offerToggle, {
        method: "PATCH", body: JSON.stringify({ active: b.dataset.active === "1" ? 0 : 1 }) });
      toast("Offer updated"); await loadPricing();
    }));
    $$("[data-offer-del]").forEach(b => b.addEventListener("click", async () => {
      if (!confirm("Delete this offer?")) return;
      await Admin.api("/api/admin/offers/" + b.dataset.offerDel, { method: "DELETE" });
      toast("Offer deleted"); await loadPricing();
    }));
  }

  $("#ofAdd").addEventListener("click", async () => {
    const name = $("#ofName").value.trim();
    if (!name) { toast("Offer name required", "err"); return; }
    await Admin.api("/api/admin/offers", { method: "POST", body: JSON.stringify({
      name, discount_pct: Number($("#ofPct").value || 0),
      note: $("#ofNote").value.trim(), active: $("#ofActive").checked ? 1 : 0,
    })});
    $("#ofName").value = ""; $("#ofPct").value = ""; $("#ofNote").value = ""; $("#ofActive").checked = false;
    toast("Offer added"); await loadPricing();
  });

  function renderServices() {
    const cats = {};
    SERVICES.forEach(s => { (cats[s.category] = cats[s.category] || []).push(s); });
    let html = "";
    Object.keys(cats).forEach(cat => {
      html += `<div class="svc-cat">${esc(cat)}</div>`;
      html += `<table class="tbl"><thead><tr><th>Service</th><th>Price ₹</th><th>Unit</th><th>Starting</th><th>Discount %</th><th>Active</th><th></th></tr></thead><tbody>`;
      cats[cat].forEach(s => {
        html += `<tr data-svc="${s.id}">
          <td><input class="mini" value="${esc(s.name)}" data-f="name" style="width:180px"><div class="muted">/${esc(s.slug)}</div></td>
          <td><input class="mini" type="number" value="${s.price}" data-f="price"></td>
          <td><input class="mini" value="${esc(s.unit)}" data-f="unit" style="width:84px"></td>
          <td style="text-align:center"><input type="checkbox" data-f="starting" ${s.starting ? "checked" : ""}></td>
          <td><input class="mini" type="number" value="${s.discount_pct}" data-f="discount_pct" style="width:64px"></td>
          <td style="text-align:center"><input type="checkbox" data-f="active" ${s.active ? "checked" : ""}></td>
          <td><button class="btn-primary sm" data-svc-save="${s.id}">Save</button></td></tr>`;
      });
      html += `</tbody></table>`;
    });
    $("#svcWrap").innerHTML = html;
    $$("[data-svc-save]").forEach(b => b.addEventListener("click", async () => {
      const tr = b.closest("tr");
      const body = {};
      tr.querySelectorAll("[data-f]").forEach(inp => {
        body[inp.dataset.f] = inp.type === "checkbox" ? (inp.checked ? 1 : 0)
          : (inp.type === "number" ? Number(inp.value || 0) : inp.value);
      });
      await Admin.api("/api/admin/services/" + b.dataset.svcSave, { method: "PATCH", body: JSON.stringify(body) });
      toast("Saved");
    }));
  }

  document.querySelector('[data-view="pricing"]').addEventListener("click", loadPricing);

  // ───────────────── Authors & team (admin only) ─────────────────
  let ACCOUNTS = [];
  async function loadAccounts() {
    if (!IS_ADMIN) return;
    try { ACCOUNTS = await Admin.api("/api/admin/accounts"); renderAccounts(); }
    catch (e) { /* handled by api() */ }
  }
  function renderAccounts() {
    const wrap = $("#accountsWrap"); if (!wrap) return;
    if (!ACCOUNTS.length) { wrap.innerHTML = empty("No accounts yet."); return; }
    wrap.innerHTML = table(["Name", "Email", "Role", ""],
      ACCOUNTS.map(a => `<tr>
        <td style="white-space:nowrap"><b>${esc(a.name) || "—"}</b></td>
        <td style="white-space:nowrap">${esc(a.email)}</td>
        <td><span class="${a.role === "admin" ? "pill pill-converted" : "tag"}">${esc(a.role)}</span></td>
        <td style="white-space:nowrap;text-align:right">${a.role === "admin" ? '<span class="muted">main account</span>'
          : `<button class="link-btn" data-ac-pw="${a.id}">Reset password</button>
             <button class="link-btn danger" data-ac-del="${a.id}" style="margin-left:10px">Delete</button>`}</td>
      </tr>`).join(""));
    $$("#accountsWrap [data-ac-del]").forEach(b => b.addEventListener("click", async () => {
      if (!confirm("Delete this author account? Their posts stay, but they lose access.")) return;
      try { await Admin.api("/api/admin/accounts/" + b.dataset.acDel, { method: "DELETE" }); toast("Author removed"); loadAccounts(); }
      catch (ex) { toast(ex.message || "Delete failed", "err"); }
    }));
    $$("#accountsWrap [data-ac-pw]").forEach(b => b.addEventListener("click", async () => {
      const pw = prompt("Set a new password for this author (min 8 characters):");
      if (pw == null) return;
      try { await Admin.api("/api/admin/accounts/" + b.dataset.acPw, { method: "PATCH", body: JSON.stringify({ password: pw }) }); toast("Password reset"); }
      catch (ex) { toast(ex.message || "Reset failed", "err"); }
    }));
  }
  const acForm = $("#acForm");
  if (acForm) acForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = $("#acName").value.trim(), email = $("#acEmail").value.trim(), password = $("#acPass").value;
    if (!name) { toast("Name is required", "err"); return; }
    if (!email) { toast("Email is required", "err"); return; }
    if ((password || "").length < 8) { toast("Password must be at least 8 characters", "err"); return; }
    try {
      await Admin.api("/api/admin/accounts", { method: "POST", body: JSON.stringify({ name, email, password }) });
      $("#acName").value = ""; $("#acEmail").value = ""; $("#acPass").value = "";
      toast("Author added"); loadAccounts();
    } catch (ex) { toast(ex.message || "Could not add author", "err"); }
  });

  // ───────────────── Author panel: blog-only console ─────────────────
  // Authors don't get access to enquiries, clients, pricing or team management.
  if (!IS_ADMIN) {
    const allowed = new Set(["blog", "settings"]);
    // Hide (don't remove) so other scripts can still bind to these nav nodes.
    $$(".nav-item").forEach(b => { if (!allowed.has(b.dataset.view)) b.style.display = "none"; });
    $$(".view").forEach(v => v.classList.add("hidden"));
    const teamCard = $("#teamCard"); if (teamCard) teamCard.style.display = "none";
    // Land straight on the Blog view once every script has wired its handlers.
    document.addEventListener("DOMContentLoaded", () => { $('[data-view="blog"]').click(); });
  }

  // ───────────────── tiny view helpers ─────────────────
  function table(heads, bodyRows) {
    return `<table class="tbl"><thead><tr>${heads.map(h => `<th>${h}</th>`).join("")}</tr></thead><tbody>${bodyRows}</tbody></table>`;
  }
  function empty(text) { return `<div class="empty">${esc(text)}</div>`; }

  // ───────────────── init ─────────────────
  (async function init() {
    // Authors have no access to enquiries/clients/stats — the blog list loads
    // itself on tab open. Only the admin console loads the full dataset.
    if (!IS_ADMIN) return;
    await Promise.all([loadStats(), loadEnquiries(), loadClients()]);
    loadAccounts().catch(() => {});
    // Watch for new leads: enquiries first, so the chime can name the lead.
    setInterval(async () => {
      await loadEnquiries().catch(() => {});
      await loadStats();
    }, 30000);
  })();
})();
