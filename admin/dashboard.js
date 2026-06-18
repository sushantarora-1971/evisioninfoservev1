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

  $("#whoami").textContent = Admin.email() || "";

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
  async function loadStats() {
    try {
      const s = await Admin.api("/api/admin/stats");
      $("#sEnq").textContent = s.enquiries;
      $("#sNew").textContent = s.new;
      $("#sCli").textContent = s.clients;
      $("#sAct").textContent = s.active;
      $("#navNew").textContent = s.new ? s.new : "";
      $("#navNew").style.display = s.new ? "" : "none";
    } catch (e) { /* handled by api() */ }
  }

  async function loadEnquiries() {
    ENQUIRIES = await Admin.api("/api/admin/enquiries");
    renderEnquiries();
    renderRecent();
  }

  async function loadClients() {
    CLIENTS = await Admin.api("/api/admin/clients");
    renderClients();
  }

  // ───────────────── Status pills ─────────────────
  const statusClass = (s) => "pill pill-" + (s || "new");

  // ───────────────── Dashboard recent ─────────────────
  function renderRecent() {
    const rows = ENQUIRIES.slice(0, 6);
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
    if (!rows.length) { $("#enqWrap").innerHTML = empty("No enquiries match."); return; }
    $("#enqWrap").innerHTML = table(
      ["Name", "Contact", "Service", "Budget", "Type", "Status", "Received", ""],
      rows.map(e => `<tr data-enq="${e.id}" class="clickable">
        <td><b>${esc(e.name)}</b>${e.company ? `<div class="muted">${esc(e.company)}</div>` : ""}</td>
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
        <dt>Consent (T&amp;C)</dt><dd>${e.consent ? "✅ Accepted" : "—"}</dd>
        <dt>Marketing</dt><dd>${e.marketing ? "✅ Opted in" : "Not opted in"}</dd>
        <dt>Received</dt><dd>${fmtDate(e.created_at)}</dd>
      </dl>
      <h3 class="drawer-h3">Message</h3>
      <p class="msg-box">${esc(e.message) || "<span class='muted'>No message provided.</span>"}</p>

      <h3 class="drawer-h3">Status</h3>
      <select id="dStatus" class="full">
        ${["new", "contacted", "converted", "closed"].map(s => `<option value="${s}" ${e.status === s ? "selected" : ""}>${s}</option>`).join("")}
      </select>

      <h3 class="drawer-h3">Internal notes</h3>
      <textarea id="dNotes" class="full" rows="4" placeholder="Add notes…">${esc(e.notes)}</textarea>

      <div class="drawer-actions">
        <button class="btn-primary" id="dSave">Save changes</button>
        ${e.status !== "converted" ? `<button class="btn-ghost" id="dConvert">Convert to client →</button>` : ""}
      </div>
    `);
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

  // ───────────────── tiny view helpers ─────────────────
  function table(heads, bodyRows) {
    return `<table class="tbl"><thead><tr>${heads.map(h => `<th>${h}</th>`).join("")}</tr></thead><tbody>${bodyRows}</tbody></table>`;
  }
  function empty(text) { return `<div class="empty">${esc(text)}</div>`; }

  // ───────────────── init ─────────────────
  (async function init() {
    await Promise.all([loadStats(), loadEnquiries(), loadClients()]);
  })();
})();
