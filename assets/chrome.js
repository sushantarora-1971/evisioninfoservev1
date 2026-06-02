/* ============================================================
   EVISION INFOSERVE — Shared chrome injector + interactions
   Injects header, footer, chat + WhatsApp widgets on every page.
   Reads document.body.dataset.page for active nav state.
   ============================================================ */
(function () {
  var page = document.body.dataset.page || "";
  var P = (window.SITE_PREFIX || "/"); // absolute links → server 301s .html to clean URLs

  var MARK = '<svg class="brand-mark" viewBox="0 0 36 36" fill="none" aria-hidden="true">' +
    '<rect width="36" height="36" rx="9" fill="#0B1930"/>' +
    '<rect x="9" y="20" width="4.6" height="7" rx="1.4" fill="#6FA3F5"/>' +
    '<rect x="15.7" y="15" width="4.6" height="12" rx="1.4" fill="#1A5FC8"/>' +
    '<rect x="22.4" y="9" width="4.6" height="18" rx="1.4" fill="#F5C400"/>' +
    '</svg>';

  var BRAND = '<a href="' + P + 'index.html" class="brand" aria-label="Evision Infoserve home">' + MARK +
    '<div><div class="brand-name">Evision<span>Infoserve</span></div>' +
    '<div class="brand-sub">Digital Marketing Agency</div></div></a>';

  var SERVICES = [
    ["SEO &amp; AI Search", "Technical, local, LLMO &amp; AEO", "search", "seo.html"],
    ["Social Media (SMO)", "Organic growth &amp; community", "thumbs-up", "social-media.html"],
    ["PPC &amp; Paid Ads", "Google, Meta &amp; LinkedIn ROI", "target", "ppc.html"],
    ["Content Marketing", "Blogs, topic clusters, video", "pen-tool", "content-marketing.html"],
    ["ORM &amp; Reputation", "Reviews &amp; brand defense", "shield-check", "orm.html"],
    ["AI Digital Marketing", "GEO, automation &amp; analytics", "sparkles", "ai-marketing.html"]
  ];

  var SEO_SUB = [["AI SEO", "ai-seo.html"], ["LLM Optimization", "llm-optimization.html"],
    ["Agentic AI SEO", "agentic-ai-seo.html"], ["Enterprise SEO", "enterprise-seo.html"], ["Ecommerce SEO", "ecommerce-seo.html"],
    ["Technical SEO", "technical-seo.html"], ["Local SEO", "local-seo.html"], ["Multilingual SEO", "multilingual-seo.html"],
    ["Link Building", "link-building.html"], ["White Label SEO", "white-label-seo.html"], ["SEO Audit", "seo-audit.html"]];
  var CONTENT_SUB = [["Content Writing", "content-writing.html"],
    ["Guest Posting", "guest-posting.html"], ["Digital PR", "digital-pr.html"]];
  var OTHER_SUB = [["Social Media (SMO)", "social-media.html"], ["PPC & Paid Ads", "ppc.html"],
    ["ORM & Reputation", "orm.html"], ["AI Digital Marketing", "ai-marketing.html"]];
  function megaCol(title, items, href) {
    var head = href
      ? '<a class="mega-h mega-h-link" href="' + P + href + '">' + title + ' <i data-lucide="arrow-right" class="mega-h-ar"></i></a>'
      : '<div class="mega-h">' + title + '</div>';
    return '<div class="mega-col">' + head +
      items.map(function (s) { return '<a href="' + P + s[1] + '">' + s[0] + '</a>'; }).join("") + '</div>';
  }
  // Parent service page is the column header; its child pages are listed under it.
  var MEGA = megaCol("SEO &amp; AI Search", SEO_SUB, "seo.html") +
    megaCol("Content Marketing", CONTENT_SUB, "content-marketing.html") +
    megaCol("More Services", OTHER_SUB);
  var ALL_SUB = [["SEO &amp; AI Search", "seo.html"]].concat(SEO_SUB,
    [["Content Marketing", "content-marketing.html"]], CONTENT_SUB, OTHER_SUB);

  function navItem(href, label, key) {
    return '<a href="' + P + href + '" class="nav-link' + (page === key ? " active" : "") + '">' + label + '</a>';
  }

  var HEADER =
    '<header class="site-header"><div class="container"><nav class="nav">' +
      BRAND +
      '<div class="nav-links">' +
        navItem("index.html", "Home", "home") +
        '<div class="nav-dd"><span class="nav-link' + (page === "services" ? " active" : "") + '">Services ' +
          '<i data-lucide="chevron-down" class="caret"></i></span>' +
          '<div class="dd-panel mega">' + MEGA +
            '<div class="dd-foot"><span>Not sure what you need? <b class="text-gold">Get a free audit.</b></span>' +
            '<a href="' + P + 'contact.html" data-audit-open class="btn btn-secondary btn-sm">Free Audit</a></div>' +
          '</div></div>' +
        navItem("pricing.html", "Pricing", "pricing") +
        navItem("blog.html", "Blog", "blog") +
        navItem("about.html", "About", "about") +
        navItem("contact.html", "Contact", "contact") +
      '</div>' +
      '<div class="nav-actions">' +
        '<a href="tel:+919811722064" class="nav-phone"><i data-lucide="phone" class="ic"></i>+91 98117 22064</a>' +
        '<a href="' + P + 'contact.html" data-audit-open class="btn btn-primary btn-sm">Get a Free Audit</a>' +
        '<button class="nav-burger" id="navBurger" aria-label="Open menu"><i data-lucide="menu" class="ic"></i></button>' +
      '</div>' +
    '</nav></div></header>';

  // mobile drawer
  var mLinks = [
    ["index.html", "Home", "home"], ["pricing.html", "Pricing", "pricing"],
    ["blog.html", "Blog", "blog"], ["about.html", "About", "about"], ["contact.html", "Contact", "contact"]
  ].map(function (l) {
    return '<a href="' + P + l[0] + '" class="m-link' + (page === l[2] ? " active" : "") + '">' + l[1] + '</a>';
  }).join("");
  var mServices = ALL_SUB.map(function (s) {
    return '<a class="m-sublink" href="' + P + s[1] + '">' + s[0] + '</a>';
  }).join("");
  var DRAWER = '<div class="m-drawer" id="mDrawer"><div class="m-scrim" data-close></div><div class="m-panel">' +
    '<div class="m-head">' + BRAND + '<button class="m-close" data-close aria-label="Close"><i data-lucide="x"></i></button></div>' +
    '<a href="' + P + 'index.html" class="m-link' + (page === "home" ? " active" : "") + '">Home</a>' +
    '<div class="m-sub">Services</div>' + mServices +
    '<a href="' + P + 'pricing.html" class="m-link' + (page === "pricing" ? " active" : "") + '">Pricing</a>' +
    '<a href="' + P + 'blog.html" class="m-link' + (page === "blog" ? " active" : "") + '">Blog</a>' +
    '<a href="' + P + 'about.html" class="m-link' + (page === "about" ? " active" : "") + '">About</a>' +
    '<a href="' + P + 'contact.html" class="m-link' + (page === "contact" ? " active" : "") + '">Contact</a>' +
    '<a href="' + P + 'contact.html" data-audit-open class="btn btn-primary btn-block" style="margin-top:18px">Get a Free Audit</a>' +
    '<a href="https://wa.me/919811722064" class="btn btn-ghost-light btn-block" style="margin-top:10px"><i data-lucide="message-circle" class="ic"></i>Chat on WhatsApp</a>' +
    '</div></div>';

  var FOOTER =
    '<footer class="site-footer"><div class="container"><div class="foot-top">' +
      '<div class="foot-brand">' + BRAND.replace('class="brand"', 'class="brand foot-brand-link"') +
        '<p class="foot-about">A digital marketing agency engineered for the AI-search era — we build sites that rank on Google and get cited by ChatGPT, Gemini &amp; Perplexity.</p>' +
        '<div class="foot-socials">' +
          '<a href="#" aria-label="LinkedIn"><svg class="ic" viewBox="0 0 24 24" fill="currentColor"><path d="M4.98 3.5a2.5 2.5 0 11-.02 5 2.5 2.5 0 01.02-5zM3 9h4v12H3zM10 9h3.8v1.7h.05c.53-1 1.83-2.05 3.77-2.05 4.03 0 4.78 2.65 4.78 6.1V21h-4v-5.4c0-1.29-.02-2.95-1.8-2.95-1.8 0-2.07 1.4-2.07 2.85V21h-4z"/></svg></a>' +
          '<a href="#" aria-label="Instagram"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none"/></svg></a>' +
          '<a href="#" aria-label="YouTube"><svg class="ic" viewBox="0 0 24 24" fill="currentColor"><path d="M23 12s0-3.2-.4-4.7a2.5 2.5 0 00-1.77-1.77C19.3 5.1 12 5.1 12 5.1s-7.3 0-8.83.42A2.5 2.5 0 001.4 7.3C1 8.8 1 12 1 12s0 3.2.4 4.7a2.5 2.5 0 001.77 1.77c1.53.43 8.83.43 8.83.43s7.3 0 8.83-.43a2.5 2.5 0 001.77-1.77C23 15.2 23 12 23 12zM9.75 15.02V8.98L15.5 12z"/></svg></a>' +
          '<a href="#" aria-label="Facebook"><svg class="ic" viewBox="0 0 24 24" fill="currentColor"><path d="M22 12a10 10 0 10-11.56 9.88v-6.99H7.9V12h2.54V9.8c0-2.5 1.49-3.89 3.78-3.89 1.09 0 2.24.2 2.24.2v2.46h-1.26c-1.24 0-1.63.77-1.63 1.56V12h2.78l-.44 2.89h-2.34v6.99A10 10 0 0022 12z"/></svg></a>' +
        '</div>' +
      '</div>' +
      '<div class="foot-col"><h4>Services</h4>' +
        '<a href="' + P + 'seo.html">SEO &amp; AI Search</a>' +
        '<a href="' + P + 'social-media.html">Social Media</a>' +
        '<a href="' + P + 'ppc.html">PPC &amp; Paid Ads</a>' +
        '<a href="' + P + 'content-marketing.html">Content Marketing</a>' +
        '<a href="' + P + 'orm.html">ORM</a>' +
        '<a href="' + P + 'ai-marketing.html">AI Digital Marketing</a></div>' +
      '<div class="foot-col"><h4>Company</h4>' +
        '<a href="' + P + 'about.html">About Us</a>' +
        '<a href="' + P + 'pricing.html">Pricing</a>' +
        '<a href="' + P + 'blog.html">Blog</a>' +
        '<a href="' + P + 'portfolio.html">Case Studies</a>' +
        '<a href="' + P + 'clients.html">Our Clients</a>' +
        '<a href="' + P + 'testimonials.html">Testimonials</a>' +
        '<a href="' + P + 'career.html">Careers</a>' +
        '<a href="' + P + 'contact.html">Contact</a></div>' +
      '<div class="foot-col foot-contact"><h4>Get in touch</h4>' +
        '<div><i data-lucide="map-pin" class="ic"></i><span>Gaur City Mall, Greater Noida West,<br>Uttar Pradesh 201009</span></div>' +
        '<div><i data-lucide="phone" class="ic"></i><a href="tel:+919811722064">+91 98117 22064</a></div>' +
        '<div><i data-lucide="mail" class="ic"></i><a href="mailto:info@evisioninfoserve.com">info@evisioninfoserve.com</a></div>' +
        '<a href="' + P + 'contact.html" class="btn btn-primary btn-sm" style="margin-top:4px">Request a Quote</a>' +
      '</div>' +
    '</div>' +
    '<div class="foot-bottom"><div class="copy">© 2026 Evision Infoserve. All rights reserved.</div>' +
      '<div class="foot-layers"><i data-lucide="sparkles" style="width:15px;height:15px"></i>Built for <b>SEO · AEO · GEO · LLMO</b></div>' +
      '<div class="legal"><a href="' + P + 'privacy-policy.html">Privacy</a><a href="' + P + 'terms.html">Terms</a><a href="' + P + 'refund-policy.html">Refund</a><a href="' + P + 'pricing.html">Pricing</a></div>' +
    '</div></div></footer>';

  var WIDGETS =
    '<div class="chat-panel" id="chatPanel"><div class="chat-head">' +
      '<div class="chat-ava">Ei</div><div><div class="t">Evision Assistant</div><div class="s">Typically replies in a minute</div></div>' +
      '<span class="x" id="chatClose"><i data-lucide="x"></i></span></div>' +
      '<div class="chat-body" id="chatBody">' +
        '<div class="bubble bot">Hi 👋 Welcome to Evision Infoserve! Looking to rank higher on Google — or get cited by AI search? How can we help?</div>' +
      '</div>' +
      '<div class="chat-quick" id="chatQuick">' +
        '<button data-q="I want an SEO audit">Get an SEO audit</button>' +
        '<button data-q="What do your packages cost?">Pricing &amp; packages</button>' +
        '<button data-q="Tell me about AI search (GEO/LLMO)">AI search (GEO/LLMO)</button>' +
      '</div>' +
      '<form class="chat-foot" id="chatForm"><input id="chatInput" placeholder="Type your message…" autocomplete="off">' +
        '<button type="submit" aria-label="Send"><i data-lucide="send" style="width:18px;height:18px"></i></button></form>' +
    '</div>' +
    '<div class="floaties">' +
      '<a class="fab fab-wa fab-pulse" href="https://wa.me/919811722064" aria-label="WhatsApp"><i data-lucide="message-circle" class="ic"></i></a>' +
      '<button class="fab fab-chat" id="chatToggle" aria-label="Open chat"><i data-lucide="messages-square" class="ic"></i></button>' +
    '</div>';

  // ── Free Audit modal ──
  var auditOpts = SERVICES.map(function (s) { return '<option>' + s[0] + '</option>'; }).join("");
  var AUDIT_MODAL =
    '<div class="audit-modal" id="auditModal" aria-hidden="true">' +
      '<div class="audit-scrim" data-audit-close></div>' +
      '<div class="audit-dialog" role="dialog" aria-modal="true" aria-labelledby="auditTitle">' +
        '<button class="audit-x" data-audit-close aria-label="Close">&times;</button>' +
        '<div id="auditFormWrap">' +
          '<span class="audit-eyebrow"><i data-lucide="sparkles"></i> Free SEO + AI Visibility Audit</span>' +
          '<h3 id="auditTitle">Get your free audit report</h3>' +
          '<p class="audit-sub">Tell us where to send it. A strategist emails you a 12-point audit within <b>24 hours</b> — no cost, no obligation.</p>' +
          '<form id="auditForm" novalidate>' +
            '<div class="audit-row">' +
              '<input type="text" name="name" placeholder="Full name *" autocomplete="name">' +
              '<input type="email" name="email" placeholder="Work email *" autocomplete="email">' +
            '</div>' +
            '<div class="audit-row">' +
              '<input type="tel" name="phone" placeholder="Phone / WhatsApp *" autocomplete="tel">' +
              '<input type="text" name="website" placeholder="Website URL">' +
            '</div>' +
            '<select name="service"><option value="">Service you want audited…</option>' + auditOpts + '</select>' +
            '<label class="audit-consent"><input type="checkbox" id="auditConsent">' +
              '<span>I accept the <a href="' + P + 'contact.html" data-audit-noop>Terms &amp; Conditions</a> and agree to receive my audit report and marketing emails from Evision Infoserve.</span></label>' +
            '<div class="audit-err" id="auditErr"></div>' +
            '<button type="submit" class="btn btn-primary btn-block btn-lg">Send me my free audit <i data-lucide="arrow-right" class="ic"></i></button>' +
            '<p class="audit-fine">We respect your inbox — unsubscribe anytime.</p>' +
          '</form>' +
        '</div>' +
        '<div class="audit-success" id="auditSuccess" style="display:none">' +
          '<div class="audit-ok"><i data-lucide="check"></i></div>' +
          '<h3>You\'re all set! 🎉</h3>' +
          '<p>Thanks — we\'ve received your details. Our team will email your free audit report within <b>24 hours</b>. Need it faster? Ping us on WhatsApp.</p>' +
          '<a href="https://wa.me/919811722064" class="btn btn-secondary btn-block">Chat on WhatsApp</a>' +
        '</div>' +
      '</div>' +
    '</div>';

  // ── Get Started modal (service-specific lead → call & WhatsApp) ──
  var START_MODAL =
    '<div class="audit-modal" id="startModal" aria-hidden="true">' +
      '<div class="audit-scrim" data-start-close></div>' +
      '<div class="audit-dialog" role="dialog" aria-modal="true" aria-labelledby="startTitle">' +
        '<button class="audit-x" data-start-close aria-label="Close">&times;</button>' +
        '<div id="startFormWrap">' +
          '<span class="audit-eyebrow"><i data-lucide="rocket"></i> Get Started</span>' +
          '<h3 id="startTitle">Let\'s get you started</h3>' +
          '<p class="audit-sub">Leave your details and our team will contact you <b>shortly via call &amp; WhatsApp</b>.</p>' +
          '<form id="startForm" novalidate>' +
            '<input type="hidden" name="type" value="get-started">' +
            '<input type="hidden" name="service" id="startService">' +
            '<div class="start-svc-chip" id="startSvcChip" style="display:none"></div>' +
            '<div class="audit-row">' +
              '<input type="text" name="name" placeholder="Full name *" autocomplete="name">' +
              '<input type="tel" name="phone" placeholder="Phone / WhatsApp *" autocomplete="tel">' +
            '</div>' +
            '<input type="email" name="email" placeholder="Email (optional)" autocomplete="email">' +
            '<textarea name="message" rows="2" placeholder="Anything we should know? (optional)"></textarea>' +
            '<div class="audit-err" id="startErr"></div>' +
            '<button type="submit" class="btn btn-primary btn-block btn-lg">Request a callback <i data-lucide="phone-call" class="ic"></i></button>' +
            '<p class="audit-fine">We\'ll reach out via call &amp; WhatsApp. No spam, ever.</p>' +
          '</form>' +
        '</div>' +
        '<div class="audit-success" id="startSuccess" style="display:none">' +
          '<div class="audit-ok"><i data-lucide="check"></i></div>' +
          '<h3>Thank you! 🎉</h3>' +
          '<p>We\'ve received your request. Our team will contact you <b>shortly via call and WhatsApp</b>. Prefer to chat now?</p>' +
          '<a href="https://wa.me/919811722064" class="btn btn-secondary btn-block">Message us on WhatsApp</a>' +
        '</div>' +
      '</div>' +
    '</div>';

  // ── inject ──
  document.body.insertAdjacentHTML("afterbegin", HEADER + DRAWER);
  document.body.insertAdjacentHTML("beforeend", FOOTER + WIDGETS + AUDIT_MODAL + START_MODAL);

  // ── interactions ──
  var header = document.querySelector(".site-header");
  function onScroll() { header.classList.toggle("scrolled", window.scrollY > 8); }
  window.addEventListener("scroll", onScroll, { passive: true }); onScroll();

  var drawer = document.getElementById("mDrawer");
  document.getElementById("navBurger").addEventListener("click", function () { drawer.classList.add("open"); document.body.style.overflow = "hidden"; });
  drawer.querySelectorAll("[data-close]").forEach(function (el) {
    el.addEventListener("click", function () { drawer.classList.remove("open"); document.body.style.overflow = ""; });
  });

  // chat
  var chat = document.getElementById("chatPanel");
  var body = document.getElementById("chatBody");
  function openChat(o) { chat.classList.toggle("open", o); }
  document.getElementById("chatToggle").addEventListener("click", function () { openChat(!chat.classList.contains("open")); });
  document.getElementById("chatClose").addEventListener("click", function () { openChat(false); });
  function botReply(text) {
    var map = {
      audit: "Great — our team can run a free SEO + AI-visibility audit and email you a 12-point report. What's your website URL?",
      pricing: "Our retainers start at ₹14,999/mo (Starter), ₹34,999/mo (Growth) and custom Scale plans. Want me to open the pricing page?",
      ai: "We optimise across 4 layers — SEO, AEO, GEO &amp; LLMO — so you rank on Google AND get cited by ChatGPT, Gemini &amp; Perplexity. Shall I send our AI-search guide?",
      default: "Thanks! A strategist will reach out shortly. You can also reach us on WhatsApp at +91 98117 22064 for an instant reply. 🚀"
    };
    var t = text.toLowerCase(), r = map.default;
    if (/audit/.test(t)) r = map.audit;
    else if (/pric|cost|package|plan/.test(t)) r = map.pricing;
    else if (/ai|geo|llmo|chatgpt|gemini|perplex/.test(t)) r = map.ai;
    var b = document.createElement("div"); b.className = "bubble bot typing"; b.textContent = "…"; body.appendChild(b); body.scrollTop = body.scrollHeight;
    setTimeout(function () { b.classList.remove("typing"); b.innerHTML = r; body.scrollTop = body.scrollHeight; }, 800);
  }
  function sendMsg(text) {
    if (!text.trim()) return;
    var m = document.createElement("div"); m.className = "bubble me"; m.textContent = text; body.appendChild(m); body.scrollTop = body.scrollHeight;
    botReply(text);
  }
  document.getElementById("chatForm").addEventListener("submit", function (e) {
    e.preventDefault(); var i = document.getElementById("chatInput"); sendMsg(i.value); i.value = "";
  });
  document.getElementById("chatQuick").querySelectorAll("button").forEach(function (b) {
    b.addEventListener("click", function () { sendMsg(b.dataset.q); });
  });

  // ── Free Audit modal interactions ──
  var auditModal = document.getElementById("auditModal");
  var auditForm = document.getElementById("auditForm");

  // Auto-wire every "free audit / quote" CTA across the site to open the popup.
  // (Any <a> pointing at contact.html whose label is an audit/quote ask.)
  var CTA_RE = /free audit|free quote|request a quote|get a quote/i;
  document.querySelectorAll('a[href]').forEach(function (a) {
    if (/contact\.html(\?|#|$)/i.test(a.getAttribute("href") || "") && CTA_RE.test(a.textContent)) {
      a.setAttribute("data-audit-open", "");
    }
  });
  function openAudit() {
    document.getElementById("auditFormWrap").style.display = "";
    document.getElementById("auditSuccess").style.display = "none";
    auditModal.classList.add("open");
    auditModal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    var first = auditForm.querySelector("input"); if (first) setTimeout(function () { first.focus(); }, 50);
  }
  function closeAudit() {
    auditModal.classList.remove("open");
    auditModal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  }
  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-audit-open]")) {
      e.preventDefault();
      if (drawer) { drawer.classList.remove("open"); }  // close mobile drawer if open
      openAudit();
    } else if (e.target.closest("[data-audit-close]")) {
      e.preventDefault(); closeAudit();
    } else if (e.target.closest("[data-audit-noop]")) {
      e.preventDefault();  // T&C placeholder link
    }
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && auditModal.classList.contains("open")) closeAudit();
  });
  // Deep-link: open the audit popup from ?audit=1 or #audit (great for email campaigns).
  if (/[?&]audit(=|&|$)/.test(location.search) || location.hash === "#audit") openAudit();

  // ── Get Started modal interactions ──
  var startModal = document.getElementById("startModal");
  var startForm = document.getElementById("startForm");
  function openStart(service) {
    document.getElementById("startFormWrap").style.display = "";
    document.getElementById("startSuccess").style.display = "none";
    var chip = document.getElementById("startSvcChip");
    document.getElementById("startService").value = service || "";
    if (service) {
      chip.innerHTML = '<i data-lucide="tag" style="width:14px;height:14px"></i> ' + service;
      chip.style.display = "";
    } else { chip.style.display = "none"; }
    startModal.classList.add("open");
    startModal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    if (window.lucide) lucide.createIcons();
    var first = startForm.querySelector('input[name="name"]'); if (first) setTimeout(function () { first.focus(); }, 50);
  }
  function closeStart() {
    startModal.classList.remove("open");
    startModal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  }
  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-start-open]");
    if (t) { e.preventDefault(); openStart(t.getAttribute("data-service") || ""); return; }
    if (e.target.closest("[data-start-close]")) { e.preventDefault(); closeStart(); }
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && startModal.classList.contains("open")) closeStart();
  });
  startForm.addEventListener("submit", function (e) {
    e.preventDefault();
    var err = document.getElementById("startErr"); err.textContent = "";
    var get = function (n) { return startForm.querySelector('[name="' + n + '"]'); };
    var nameV = get("name").value.trim();
    var phoneV = get("phone").value.trim();
    var emailV = get("email").value.trim();
    if (!nameV) { err.textContent = "Please enter your name."; return; }
    if (phoneV.replace(/\D/g, "").length < 8) { err.textContent = "Please enter a valid phone number."; return; }
    if (emailV && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(emailV)) { err.textContent = "Enter a valid email, or leave it blank."; return; }
    var payload = {
      type: "get-started", name: nameV, phone: phoneV, email: emailV,
      service: get("service").value, message: get("message").value.trim(),
      source: (location.pathname.split("/").pop() || "home") + " (get started)",
    };
    var btn = startForm.querySelector("button[type=submit]");
    btn.disabled = true; btn.textContent = "Sending…";
    function done() {
      document.getElementById("startFormWrap").style.display = "none";
      document.getElementById("startSuccess").style.display = "";
      if (window.lucide) lucide.createIcons();
    }
    fetch("/api/enquiry", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    }).then(done).catch(done);
  });
  auditForm.addEventListener("submit", function (e) {
    e.preventDefault();
    var err = document.getElementById("auditErr"); err.textContent = "";
    var get = function (n) { return auditForm.querySelector('[name="' + n + '"]'); };
    var nameV = get("name").value.trim();
    var emailV = get("email").value.trim();
    var phoneV = get("phone").value.trim();
    var consent = document.getElementById("auditConsent");
    if (!nameV) { err.textContent = "Please enter your name."; return; }
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(emailV)) { err.textContent = "Please enter a valid email."; return; }
    if (phoneV.replace(/\D/g, "").length < 8) { err.textContent = "Please enter a valid phone number."; return; }
    if (!consent.checked) { err.textContent = "Please accept the Terms to receive your free audit."; return; }
    var payload = {
      name: nameV, email: emailV, phone: phoneV,
      website: get("website").value.trim(),
      service: get("service").value,
      type: "audit",
      source: (location.pathname.split("/").pop() || "home") + " (audit popup)",
      consent: 1, marketing: 1
    };
    var btn = auditForm.querySelector("button[type=submit]");
    btn.disabled = true; btn.textContent = "Sending…";
    function done() {
      document.getElementById("auditFormWrap").style.display = "none";
      document.getElementById("auditSuccess").style.display = "";
      if (window.lucide) lucide.createIcons();
    }
    fetch("/api/enquiry", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    }).then(done).catch(done);
  });

  // reveal on scroll
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); } });
  }, { threshold: 0.12 });
  document.querySelectorAll(".reveal").forEach(function (el) { io.observe(el); });

  if (window.lucide) lucide.createIcons();
})();
