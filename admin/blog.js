/* Evision admin — Blog management.
   Full CRUD for posts + a lightweight HTML editor (WYSIWYG toolbar with a raw
   HTML source toggle), server-rendered preview, and per-post SEO / Open Graph
   fields. Reuses the shared Admin helper and the toast/nav DOM. */
(function () {
  if (!Admin.token()) return; // dashboard.js handles the redirect

  const IS_ADMIN = Admin.isAdmin();
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  let toastTimer;
  function toast(msg, kind = "ok") {
    const t = $("#toast"); if (!t) return;
    t.textContent = msg; t.className = "toast " + kind;
    clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.add("hidden"), 2600);
  }

  const listView = () => $("#view-blog");
  const editView = () => $("#view-blog-edit");
  function showList() { editView().classList.add("hidden"); listView().classList.remove("hidden"); }
  function showEditor() { listView().classList.add("hidden"); editView().classList.remove("hidden"); }

  // ════════════════ LIST ════════════════
  let POSTS = [];
  async function loadPosts() { POSTS = await Admin.api("/api/admin/posts"); renderList(); }
  function filtered() {
    const q = ($("#blogSearch").value || "").trim().toLowerCase();
    return q ? POSTS.filter(p => [p.title, p.tag, p.author, p.slug].join(" ").toLowerCase().includes(q)) : POSTS;
  }
  function fmtDate(iso) {
    if (!iso) return "—";
    const d = new Date(iso); if (isNaN(d)) return "—";
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  }
  function renderList() {
    const rows = filtered();
    if (!rows.length) {
      $("#blogWrap").innerHTML = `<div class="empty">No posts yet. Click “+ New post” to write your first article.</div>`;
      return;
    }
    $("#blogWrap").innerHTML = `<table class="tbl">
      <thead><tr><th>Title</th><th>Tag</th><th>Status</th><th>Updated</th><th></th></tr></thead>
      <tbody>${rows.map(p => `<tr data-id="${p.id}" class="clickable">
        <td><b>${esc(p.title)}</b><div class="muted">/blog/${esc(p.slug)}</div></td>
        <td>${p.tag ? `<span class="tag">${esc(p.tag)}</span>` : "—"}</td>
        <td>${p.status === "published"
            ? '<span class="pill pill-converted">published</span>'
            : '<span class="pill pill-closed">draft</span>'}</td>
        <td>${fmtDate(p.updated_at || p.created_at)}</td>
        <td>
          <a class="link-btn" href="/blog/${esc(p.slug)}${p.status === "published" ? "" : "?preview=" + encodeURIComponent(Admin.token())}" target="_blank" rel="noopener">View</a>
          <button class="link-btn danger" data-del="${p.id}">Delete</button>
        </td></tr>`).join("")}</tbody></table>`;
    $$("#blogWrap tr[data-id]").forEach(tr => tr.addEventListener("click", ev => {
      if (ev.target.closest("[data-del]") || ev.target.closest("a")) return;
      openEditor(Number(tr.dataset.id));
    }));
    $$("#blogWrap [data-del]").forEach(b => b.addEventListener("click", async ev => {
      ev.stopPropagation();
      if (!confirm("Delete this post permanently?")) return;
      await Admin.api("/api/admin/posts/" + b.dataset.del, { method: "DELETE" });
      toast("Post deleted"); loadPosts();
    }));
  }

  // ════════════════ EDITOR ════════════════
  let current = null;        // the post being edited (null = new)
  let sourceMode = false;    // body editor showing raw HTML?

  function slugify(s) {
    return String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 80);
  }

  // Status control: admins get the draft/publish select; authors can only save
  // drafts (publishing is reserved for the main admin account). A post an admin
  // already published stays published — authors just can't change that.
  function statusFieldHtml(p) {
    if (IS_ADMIN) {
      return `<select id="be_status">
            <option value="draft">Draft (hidden)</option>
            <option value="published">Published (live)</option>
          </select>`;
    }
    if (p && p.status === "published") {
      return `<div><span class="pill pill-converted">published</span></div>
          <input type="hidden" id="be_status" value="published">
          <p class="muted" style="margin:8px 0 0">Live on the site. Contact your admin to make changes to a published post.</p>`;
    }
    return `<select id="be_status"><option value="draft">Draft</option></select>
          <p class="muted" style="margin:8px 0 0">Only the admin can publish. Save your draft and an admin will review &amp; publish it.</p>`;
  }

  function editorMarkup(p) {
    p = p || {};
    const v = (k) => esc(p[k]);
    return `
    <div class="blog-editor">
      <div class="be-main">
        <label>Title</label>
        <input id="be_title" class="be-title" placeholder="Post headline" value="${v("title")}">

        <label>URL slug <span class="muted">(the /blog/… address)</span></label>
        <div class="be-slug"><span>/blog/</span><input id="be_slug" placeholder="auto from title" value="${v("slug")}"></div>

        <label>Body</label>
        <div class="be-toolbar" id="be_toolbar">
          <button type="button" data-cmd="formatBlock" data-val="h2" title="Heading">H2</button>
          <button type="button" data-cmd="formatBlock" data-val="h3" title="Subheading">H3</button>
          <button type="button" data-cmd="formatBlock" data-val="p" title="Paragraph">¶</button>
          <span class="be-sep"></span>
          <button type="button" data-cmd="bold" title="Bold"><b>B</b></button>
          <button type="button" data-cmd="italic" title="Italic"><i>I</i></button>
          <button type="button" data-cmd="insertUnorderedList" title="Bullet list">• List</button>
          <button type="button" data-cmd="insertOrderedList" title="Numbered list">1. List</button>
          <button type="button" data-cmd="formatBlock" data-val="blockquote" title="Quote">❝</button>
          <span class="be-sep"></span>
          <button type="button" id="be_link" title="Insert link">🔗 Link</button>
          <button type="button" id="be_img" title="Insert image">🖼 Image</button>
          <button type="button" data-cmd="removeFormat" title="Clear formatting">Clear</button>
          <span class="be-sep"></span>
          <button type="button" id="be_source" title="Edit raw HTML">&lt;/&gt; HTML</button>
        </div>
        <div id="be_body" class="be-body prose" contenteditable="true"></div>
        <textarea id="be_source_ta" class="be-source hidden" spellcheck="false"></textarea>
        <input type="file" id="be_img_file" accept="image/*" class="hidden">
      </div>

      <aside class="be-side">
        <div class="be-box">
          <label>Status</label>
          ${statusFieldHtml(p)}
          <label>Tag / category</label>
          <input id="be_tag" placeholder="e.g. AI Search" value="${v("tag")}">
          <div class="grid2">
            <div><label>Author</label><input id="be_author" value="${esc(p.author || (IS_ADMIN ? "" : Admin.name()))}" ${IS_ADMIN ? "" : "readonly"}></div>
            <div><label>Read (min)</label><input id="be_read_min" type="number" min="1" value="${p.read_min != null ? p.read_min : 5}"></div>
          </div>
          <label>Author role</label>
          <input id="be_author_role" placeholder="e.g. Head of SEO Strategy" value="${v("author_role")}">
          <label>Author bio <span class="muted">(optional — overrides your account bio for this post)</span></label>
          <textarea id="be_author_bio" rows="3" placeholder="Leave blank to use your account bio (Settings → Your account).">${v("author_bio")}</textarea>
          <label>Excerpt <span class="muted">(card summary + meta fallback)</span></label>
          <textarea id="be_excerpt" rows="3">${v("excerpt")}</textarea>
          <label>Cover image</label>
          ${imgFieldHtml("be_cover", p.cover)}
        </div>

        <div class="be-box">
          <h3 class="be-box-h">SEO &amp; social</h3>
          <label>Meta title <span class="muted">(&lt;title&gt;)</span></label>
          <input id="be_meta_title" placeholder="Falls back to the post title" value="${v("meta_title")}">
          <label>Meta description</label>
          <textarea id="be_meta_desc" rows="2" placeholder="Falls back to the excerpt">${v("meta_desc")}</textarea>
          <label>OG title <span class="muted">(social share)</span></label>
          <input id="be_og_title" placeholder="Falls back to meta title" value="${v("og_title")}">
          <label>OG description</label>
          <textarea id="be_og_desc" rows="2" placeholder="Falls back to meta description">${v("og_desc")}</textarea>
          <label>OG image</label>
          ${imgFieldHtml("be_og_image", p.og_image)}
        </div>
      </aside>
    </div>`;
  }

  // ── compact image field (upload or paste URL) ──
  function imgFieldHtml(id, url) {
    return `<div class="imgfield">
      <div class="imgprev" id="${id}_prev" style="${url ? `background-image:url('${esc(url)}')` : ""}">${url ? "" : "No image"}</div>
      <div class="imgctl">
        <input type="file" accept="image/*" id="${id}_file">
        <input id="${id}_url" placeholder="/uploads/… or https://…" value="${esc(url || "")}" style="margin-top:8px">
      </div></div>`;
  }
  async function uploadFile(f) {
    const dataUrl = await new Promise((res, rej) => {
      const r = new FileReader(); r.onload = () => res(r.result); r.onerror = rej; r.readAsDataURL(f);
    });
    const out = await Admin.api("/api/admin/upload", { method: "POST", body: JSON.stringify({ filename: f.name, data: dataUrl }) });
    return out.url;
  }
  function wireImg(id) {
    const file = $("#" + id + "_file"), url = $("#" + id + "_url"), prev = $("#" + id + "_prev");
    const setPrev = (u) => { if (u) { prev.style.backgroundImage = `url('${u}')`; prev.textContent = ""; } else { prev.style.backgroundImage = ""; prev.textContent = "No image"; } };
    url.addEventListener("input", () => setPrev(url.value.trim()));
    file.addEventListener("change", async () => {
      const f = file.files[0]; if (!f) return;
      try { const u = await uploadFile(f); url.value = u; setPrev(u); toast("Image uploaded"); }
      catch (ex) { toast(ex.message || "Upload failed", "err"); }
    });
  }
  const getImg = (id) => ($("#" + id + "_url").value || "").trim();

  // ── body editor helpers ──
  function getBody() {
    return sourceMode ? $("#be_source_ta").value : $("#be_body").innerHTML;
  }
  function setBody(htmlStr) {
    $("#be_body").innerHTML = htmlStr || "";
    $("#be_source_ta").value = htmlStr || "";
  }
  function wireEditor() {
    // toolbar exec commands
    $$("#be_toolbar [data-cmd]").forEach(btn => btn.addEventListener("mousedown", ev => {
      ev.preventDefault(); // keep selection in the editable
      $("#be_body").focus();
      document.execCommand(btn.dataset.cmd, false, btn.dataset.val || null);
    }));
    $("#be_link").addEventListener("mousedown", ev => {
      ev.preventDefault(); $("#be_body").focus();
      const u = prompt("Link URL:", "https://"); if (u) document.execCommand("createLink", false, u);
    });
    // insert image into the body
    $("#be_img").addEventListener("mousedown", ev => { ev.preventDefault(); $("#be_img_file").click(); });
    $("#be_img_file").addEventListener("change", async () => {
      const f = $("#be_img_file").files[0]; if (!f) return;
      try {
        const u = await uploadFile(f);
        $("#be_body").focus();
        document.execCommand("insertImage", false, u);
        toast("Image inserted");
      } catch (ex) { toast(ex.message || "Upload failed", "err"); }
      $("#be_img_file").value = "";
    });
    // raw HTML source toggle
    $("#be_source").addEventListener("click", () => {
      const body = $("#be_body"), ta = $("#be_source_ta");
      if (!sourceMode) { ta.value = body.innerHTML; ta.classList.remove("hidden"); body.classList.add("hidden"); $("#be_source").classList.add("on"); }
      else { body.innerHTML = ta.value; ta.classList.add("hidden"); body.classList.remove("hidden"); $("#be_source").classList.remove("on"); }
      sourceMode = !sourceMode;
    });
    // auto-suggest slug from title until the user edits the slug manually
    const slugInput = $("#be_slug"); let slugTouched = !!slugInput.value;
    slugInput.addEventListener("input", () => { slugTouched = true; });
    $("#be_title").addEventListener("input", () => { if (!slugTouched) slugInput.value = slugify($("#be_title").value); });
  }

  function readForm() {
    return {
      title: $("#be_title").value.trim(),
      slug: $("#be_slug").value.trim(),
      body: getBody(),
      tag: $("#be_tag").value.trim(),
      author: $("#be_author").value.trim(),
      author_role: $("#be_author_role").value.trim(),
      author_bio: $("#be_author_bio").value.trim(),
      read_min: Number($("#be_read_min").value || 5),
      excerpt: $("#be_excerpt").value.trim(),
      cover: getImg("be_cover"),
      meta_title: $("#be_meta_title").value.trim(),
      meta_desc: $("#be_meta_desc").value.trim(),
      og_title: $("#be_og_title").value.trim(),
      og_desc: $("#be_og_desc").value.trim(),
      og_image: getImg("be_og_image"),
      status: $("#be_status").value,
    };
  }

  function openEditor(id) {
    sourceMode = false;
    const post = id ? POSTS.find(p => p.id === id) : null;
    if (id && !post) return;
    // For an existing post we need the full row (body + SEO), so fetch it.
    if (id) {
      Admin.api("/api/admin/posts/" + id).then(full => mountEditor(full)).catch(ex => toast(ex.message || "Could not open post", "err"));
    } else {
      mountEditor(null);
    }
  }

  function mountEditor(post) {
    current = post;
    $("#blogEditHeading").textContent = post ? "Edit post" : "New post";
    $("#blogEditBody").innerHTML = editorMarkup(post || {});
    $("#be_status").value = (post && post.status) || "draft";
    setBody(post ? post.body : "");
    updateStatusPill();
    wireEditor(); wireImg("be_cover"); wireImg("be_og_image");
    showEditor();
    window.scrollTo(0, 0);
  }

  function updateStatusPill() {
    const pill = $("#blogStatusPill");
    if (!current) { pill.textContent = "Unsaved"; return; }
    pill.innerHTML = current.status === "published"
      ? '<span class="pill pill-converted">published</span>'
      : '<span class="pill pill-closed">draft</span>';
  }

  async function save() {
    const body = readForm();
    if (!body.title) { toast("Title is required", "err"); return null; }
    try {
      let res;
      if (current && current.id) {
        res = await Admin.api("/api/admin/posts/" + current.id, { method: "PATCH", body: JSON.stringify(body) });
        current = Object.assign({}, current, body, { slug: res.slug || current.slug });
      } else {
        res = await Admin.api("/api/admin/posts", { method: "POST", body: JSON.stringify(body) });
        current = Object.assign({ id: res.id }, body, { slug: res.slug });
        // reflect the new slug in the field
        if ($("#be_slug")) $("#be_slug").value = res.slug;
      }
      updateStatusPill();
      toast(IS_ADMIN ? (body.status === "published" ? "Post published" : "Draft saved") : "Draft saved");
      loadPosts().catch(() => {});
      return current;
    } catch (ex) { toast(ex.message || "Save failed", "err"); return null; }
  }

  // ── wire the editor's top-bar buttons (exist in static HTML) ──
  $("#newPostBtn").addEventListener("click", () => openEditor(null));
  $("#blogBack").addEventListener("click", () => { showList(); loadPosts().catch(() => {}); });
  $("#blogSaveBtn").addEventListener("click", () => { save(); });
  $("#blogPreviewBtn").addEventListener("click", async () => {
    // Open a tab synchronously (avoids popup blockers), then point it at the
    // real server-rendered preview once the post is saved.
    const tab = window.open("about:blank", "_blank");
    const saved = await save();
    if (!saved) { if (tab) tab.close(); return; }
    const url = "/blog/" + encodeURIComponent(saved.slug) +
      (saved.status === "published" ? "" : "?preview=" + encodeURIComponent(Admin.token()));
    if (tab) tab.location = url; else window.open(url, "_blank");
  });
  $("#blogSearch").addEventListener("input", renderList);

  // ── lazy-load the list the first time the Blog tab opens ──
  let loaded = false;
  $('[data-view="blog"]').addEventListener("click", () => {
    showList(); // ensure list (not a stale editor) shows when returning
    if (!loaded) { loaded = true; loadPosts().catch(() => {}); }
  });
})();
