/* ============================================================
   EVISION INFOSERVE — Shared chrome injector + interactions
   Injects header, footer, chat + WhatsApp widgets on every page.
   Reads document.body.dataset.page for active nav state.
   ============================================================ */
/* ── Anti-spam for every enquiry form ────────────────────────────────────────
   Two traps, added in one place so every form (contact, popups, lead magnets,
   scorecard, newsletter) is covered without touching its submit handler:
     1. Honeypot — a hidden text input injected into each form. Humans never
        see it; form-filling bots fill everything they find.
     2. Timing  — how long the page was open before the POST. Bots submit in
        milliseconds; humans take seconds.
   Both ride along as _hp / _t on the JSON body, and server.py scores them.
   ─────────────────────────────────────────────────────────────────────────── */
(function () {
  var T0 = Date.now();
  // Named so a bot's "fill every text input" pass takes the bait, but browser
  // autofill/password managers don't recognise it (they fill hidden url/email/
  // name fields, which is the classic way a honeypot flags a real visitor).
  var HP_NAME = "subject_line";

  function addHoneypots(root) {
    (root || document).querySelectorAll("form").forEach(function (f) {
      if (f.querySelector("[data-hp]")) return;
      var wrap = document.createElement("div");
      wrap.setAttribute("aria-hidden", "true");
      wrap.style.cssText = "position:absolute!important;left:-9999px!important;" +
        "top:auto;width:1px;height:1px;overflow:hidden;opacity:0;pointer-events:none";
      wrap.innerHTML = '<label>Subject line (leave blank)<input type="text" data-hp name="' +
        HP_NAME + '" tabindex="-1" autocomplete="off"></label>';
      f.appendChild(wrap);
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { addHoneypots(); });
  } else { addHoneypots(); }
  // Header/footer/modals are injected later in this file — catch those too.
  setTimeout(function () { addHoneypots(); }, 1200);

  function honeypotValue() {
    var v = "";
    document.querySelectorAll("[data-hp]").forEach(function (i) { v += i.value || ""; });
    return v;
  }

  // Stamp every enquiry POST, whoever sends it.
  var origFetch = window.fetch;
  window.fetch = function (input, init) {
    try {
      var url = typeof input === "string" ? input : (input && input.url) || "";
      if (url.indexOf("/api/enquiry") !== -1 && init && typeof init.body === "string") {
        var p = JSON.parse(init.body);
        p._t = Date.now() - T0;
        p._hp = honeypotValue();
        init = Object.assign({}, init, { body: JSON.stringify(p) });
      }
    } catch (e) { /* never block a submission on this */ }
    return origFetch.call(this, input, init);
  };
})();

(function () {
  var page = document.body.dataset.page || "";
  var P = (window.SITE_PREFIX || "/"); // absolute links → server 301s .html to clean URLs

  // Canonical clean-URL map (mirrors server.py FILE_TO_CLEAN). Links are authored
  // with .html filenames; we rewrite every internal anchor to its clean URL after
  // injection so the browser status bar / hover never shows the old .html path.
  var _SEOC = ["ai-seo", "llm-optimization", "agentic-ai-seo", "enterprise-seo", "ecommerce-seo",
    "technical-seo", "local-seo", "multilingual-seo", "link-building", "white-label-seo", "seo-audit", "industry-seo"];
  var _CONTC = ["content-writing", "guest-posting", "digital-pr"];
  var CLEAN = {
    "index.html": "/", "web-design.html": "/services/web-design", "web-development.html": "/services/web-development",
    "seo.html": "/services/seo", "content-marketing.html": "/services/content-marketing",
    "social-media.html": "/services/social-media", "ppc.html": "/services/ppc", "orm.html": "/services/orm",
    "ai-marketing.html": "/services/ai-digital-marketing", "affiliate-marketing.html": "/services/affiliate-marketing",
    "youtube-marketing.html": "/services/youtube-marketing", "email-marketing.html": "/services/email-marketing",
    "mobile-app-marketing.html": "/services/mobile-app-marketing", "services.html": "/services",
    "pricing.html": "/pricing", "about.html": "/about", "blog.html": "/blog", "contact.html": "/contact",
    "website-scorecard.html": "/website-health-check",
    "portfolio.html": "/portfolio", "clients.html": "/clients", "career.html": "/career", "testimonials.html": "/testimonials",
    "privacy-policy.html": "/privacy-policy", "refund-policy.html": "/refund-policy", "terms.html": "/terms", "service.html": "/service"
  };
  _SEOC.forEach(function (c) { CLEAN[c + ".html"] = "/services/seo/" + c; });
  _CONTC.forEach(function (c) { CLEAN[c + ".html"] = "/services/content-marketing/" + c; });
  function cleanHrefs(root) {
    (root || document).querySelectorAll('a[href]').forEach(function (a) {
      var m = (a.getAttribute("href") || "").match(/^\/?([A-Za-z0-9_-]+\.html)(#.*)?$/);
      if (m && CLEAN[m[1]]) a.setAttribute("href", CLEAN[m[1]] + (m[2] || ""));
    });
  }

  var MARK = '<svg class="brand-mark" viewBox="0 0 36 36" fill="none" aria-hidden="true">' +
    '<rect width="36" height="36" rx="9" fill="#0A0E1C"/>' +
    '<rect x="9" y="20" width="4.6" height="7" rx="1.4" fill="#B7ADFF"/>' +
    '<rect x="15.7" y="15" width="4.6" height="12" rx="1.4" fill="#6D5EFB"/>' +
    '<rect x="22.4" y="9" width="4.6" height="18" rx="1.4" fill="#F5B62B"/>' +
    '</svg>';

  var BRAND = '<a href="' + P + 'index.html" class="brand" aria-label="Evision Infoserve home">' + MARK +
    '<div><div class="brand-name">Evision<span>Infoserve</span></div>' +
    '<div class="brand-sub">Web Design · Development · SEO</div></div></a>';

  // Service options for the Free Quote / Audit modal dropdown.
  var SERVICES = [
    ["Website Design", "", "", ""], ["Website Development", "", "", ""],
    ["E-commerce Website", "", "", ""], ["Website Redesign", "", "", ""],
    ["SEO Services", "", "", ""], ["Local SEO", "", "", ""],
    ["AI SEO / LLMO", "", "", ""], ["Content Marketing", "", "", ""],
    ["PPC & Paid Ads", "", "", ""], ["Social Media (SMO)", "", "", ""],
    ["Website + SEO Package", "", "", ""], ["Not sure — need advice", "", "", ""]
  ];

  // ── Two co-equal pillars: Design & Build (violet) · Rank & Grow / SEO (amber) ──
  var DESIGN_SUB = [["Website Design", "web-design.html"], ["UI/UX Design", "web-design.html#ux"],
    ["Website Redesign", "web-design.html#redesign"], ["Landing Pages", "web-design.html#landing"],
    ["Web Development", "web-development.html"], ["E-commerce Development", "web-development.html#ecommerce"],
    ["Web Apps & CMS", "web-development.html#apps"], ["Maintenance & Support", "web-development.html#care"]];
  var SEO_SUB = [["SEO Services", "seo.html"], ["Technical SEO", "technical-seo.html"],
    ["Local SEO", "local-seo.html"], ["AI SEO / LLMO", "ai-seo.html"], ["Ecommerce SEO", "ecommerce-seo.html"],
    ["Link Building", "link-building.html"], ["SEO Audit", "seo-audit.html"], ["Content Marketing", "content-marketing.html"]];
  var OTHER_SUB = [["PPC & Paid Ads", "ppc.html"], ["Social Media (SMO)", "social-media.html"],
    ["ORM & Reputation", "orm.html"], ["AI Digital Marketing", "ai-marketing.html"],
    ["Content Writing", "content-writing.html"], ["Email Marketing", "email-marketing.html"],
    ["YouTube Marketing", "youtube-marketing.html"], ["Mobile App Marketing", "mobile-app-marketing.html"]];
  function megaCol(title, items, href) {
    var head = href
      ? '<a class="mega-h mega-h-link" href="' + P + href + '">' + title + ' <i data-lucide="arrow-right" class="mega-h-ar"></i></a>'
      : '<div class="mega-h">' + title + '</div>';
    return '<div class="mega-col">' + head +
      items.map(function (s) { return '<a href="' + P + s[1] + '">' + s[0] + '</a>'; }).join("") + '</div>';
  }
  var MEGA = megaCol("Design &amp; Build", DESIGN_SUB, "web-design.html") +
    megaCol("Rank &amp; Grow (SEO)", SEO_SUB, "seo.html") +
    megaCol("Marketing &amp; More", OTHER_SUB);
  var ALL_SUB = [["— Design & Build —", "web-design.html"]].concat(DESIGN_SUB,
    [["— Rank & Grow (SEO) —", "seo.html"]], SEO_SUB, OTHER_SUB);

  function navItem(href, label, key) {
    return '<a href="' + P + href + '" class="nav-link' + (page === key ? " active" : "") + '">' + label + '</a>';
  }

  var HEADER =
    '<header class="site-header"><div class="container"><nav class="nav">' +
      BRAND +
      '<div class="nav-links">' +
        navItem("index.html", "Home", "home") +
        '<div class="nav-dd"><a href="' + P + 'services.html" class="nav-link' + (page === "services" ? " active" : "") + '">Services ' +
          '<i data-lucide="chevron-down" class="caret"></i></a>' +
          '<div class="dd-panel mega">' + MEGA +
            '<div class="dd-foot"><span>Need a website, SEO, or both? <b class="text-gold">Get a free quote.</b></span>' +
            '<a href="' + P + 'contact.html" data-audit-open class="btn btn-secondary btn-sm">Free Quote</a></div>' +
          '</div></div>' +
        navItem("pricing.html", "Pricing", "pricing") +
        navItem("blog.html", "Blog", "blog") +
        navItem("about.html", "About", "about") +
        navItem("contact.html", "Contact", "contact") +
      '</div>' +
      '<div class="nav-actions">' +
        '<a href="tel:+919311221517" class="nav-phone"><i data-lucide="phone" class="ic"></i>+91 93112 21517</a>' +
        '<a href="' + P + 'contact.html" data-audit-open class="btn btn-primary btn-sm">Get a Free Audit</a>' +
        '<button class="nav-burger" id="navBurger" aria-label="Open menu"><i data-lucide="menu" class="ic"></i></button>' +
      '</div>' +
    '</nav></div></header>';

  // mobile drawer
  var mLinks = [
    ["index.html", "Home", "home"],
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
    '<a href="' + P + 'pricing.html" class="m-link' + (page === "pricing" ? " active" : "") + '">Packages &amp; Pricing</a>' +
    '<a href="' + P + 'blog.html" class="m-link' + (page === "blog" ? " active" : "") + '">Blog</a>' +
    '<a href="' + P + 'about.html" class="m-link' + (page === "about" ? " active" : "") + '">About</a>' +
    '<a href="' + P + 'contact.html" class="m-link' + (page === "contact" ? " active" : "") + '">Contact</a>' +
    '<a href="' + P + 'contact.html" data-audit-open class="btn btn-primary btn-block" style="margin-top:18px">Get a Free Audit</a>' +
    '<a href="https://wa.me/919311221517" class="btn btn-ghost-light btn-block" style="margin-top:10px"><i data-lucide="message-circle" class="ic"></i>Chat on WhatsApp</a>' +
    '</div></div>';

  var FOOTER =
    '<footer class="site-footer"><div class="container"><div class="foot-top">' +
      '<div class="foot-brand">' + BRAND.replace('class="brand"', 'class="brand foot-brand-link"') +
        '<p class="foot-about">A web design, development &amp; SEO studio in Greater Noida. We design and build fast, beautiful websites — then engineer them to rank on Google and get cited by AI search.</p>' +
        '<div class="foot-socials">' +
          '<a href="https://www.linkedin.com/company/evisioninfoserve/" target="_blank" rel="noopener" aria-label="LinkedIn"><svg class="ic" viewBox="0 0 24 24" fill="currentColor"><path d="M4.98 3.5a2.5 2.5 0 11-.02 5 2.5 2.5 0 01.02-5zM3 9h4v12H3zM10 9h3.8v1.7h.05c.53-1 1.83-2.05 3.77-2.05 4.03 0 4.78 2.65 4.78 6.1V21h-4v-5.4c0-1.29-.02-2.95-1.8-2.95-1.8 0-2.07 1.4-2.07 2.85V21h-4z"/></svg></a>' +
          '<a href="https://www.instagram.com/evisioninfoserve/" target="_blank" rel="noopener" aria-label="Instagram"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none"/></svg></a>' +
          '<a href="https://www.youtube.com/@evisioninfoserve" target="_blank" rel="noopener" aria-label="YouTube"><svg class="ic" viewBox="0 0 24 24" fill="currentColor"><path d="M23 12s0-3.2-.4-4.7a2.5 2.5 0 00-1.77-1.77C19.3 5.1 12 5.1 12 5.1s-7.3 0-8.83.42A2.5 2.5 0 001.4 7.3C1 8.8 1 12 1 12s0 3.2.4 4.7a2.5 2.5 0 001.77 1.77c1.53.43 8.83.43 8.83.43s7.3 0 8.83-.43a2.5 2.5 0 001.77-1.77C23 15.2 23 12 23 12zM9.75 15.02V8.98L15.5 12z"/></svg></a>' +
          '<a href="https://www.facebook.com/EvisionInfoservepvtltd/" target="_blank" rel="noopener" aria-label="Facebook"><svg class="ic" viewBox="0 0 24 24" fill="currentColor"><path d="M22 12a10 10 0 10-11.56 9.88v-6.99H7.9V12h2.54V9.8c0-2.5 1.49-3.89 3.78-3.89 1.09 0 2.24.2 2.24.2v2.46h-1.26c-1.24 0-1.63.77-1.63 1.56V12h2.78l-.44 2.89h-2.34v6.99A10 10 0 0022 12z"/></svg></a>' +
        '</div>' +
      '</div>' +
      '<div class="foot-col"><h4>Design &amp; Build</h4>' +
        '<a href="' + P + 'web-design.html">Website Design</a>' +
        '<a href="' + P + 'web-development.html">Web Development</a>' +
        '<a href="' + P + 'web-development.html#ecommerce">E-commerce Development</a>' +
        '<a href="' + P + 'web-design.html#redesign">Website Redesign</a>' +
        '<a href="' + P + 'web-development.html#care">Maintenance &amp; Support</a>' +
        '<a href="' + P + 'pricing.html">Packages &amp; Pricing</a></div>' +
      '<div class="foot-col"><h4>Rank &amp; Grow</h4>' +
        '<a href="' + P + 'seo.html">SEO Services</a>' +
        '<a href="' + P + 'ai-seo.html">AI SEO / LLMO</a>' +
        '<a href="' + P + 'content-marketing.html">Content Marketing</a>' +
        '<a href="' + P + 'ppc.html">PPC &amp; Paid Ads</a>' +
        '<a href="' + P + 'social-media.html">Social Media</a>' +
        '<a href="' + P + 'orm.html">ORM &amp; Reputation</a></div>' +
      '<div class="foot-col"><h4>Company</h4>' +
        '<a href="' + P + 'about.html">About Us</a>' +
        '<a href="' + P + 'website-scorecard.html">Free Website Score</a>' +
        '<a href="' + P + 'blog.html">Blog</a>' +
        '<a href="' + P + 'portfolio.html">Case Studies</a>' +
        '<a href="' + P + 'clients.html">Our Clients</a>' +
        '<a href="' + P + 'testimonials.html">Testimonials</a>' +
        '<a href="' + P + 'career.html">Careers</a>' +
        '<a href="' + P + 'contact.html">Contact</a></div>' +
      '<div class="foot-col foot-contact"><h4>Get in touch</h4>' +
        '<div><i data-lucide="map-pin" class="ic"></i><span>Gaur City Mall, Greater Noida West,<br>Uttar Pradesh 201009</span></div>' +
        '<div><i data-lucide="phone" class="ic"></i><a href="tel:+919311221517">+91 93112 21517</a></div>' +
        '<div><i data-lucide="mail" class="ic"></i><a href="mailto:info@evisioninfoserve.com">info@evisioninfoserve.com</a></div>' +
        '<a href="' + P + 'contact.html" class="btn btn-primary btn-sm" style="margin-top:4px">Request a Quote</a>' +
      '</div>' +
    '</div>' +
    '<div class="foot-news">' +
      '<div class="fn-copy"><h4>Get 1 practical web &amp; SEO tip a week</h4>' +
        '<p>Join 2,000+ founders &amp; marketers. No spam — unsubscribe anytime.</p></div>' +
      '<form class="fn-form" id="footNews" novalidate>' +
        '<input type="email" name="email" placeholder="Your email address" autocomplete="email" aria-label="Email address">' +
        '<button type="submit" class="btn btn-primary btn-sm">Subscribe <i data-lucide="arrow-right" class="ic"></i></button>' +
        '<span class="fn-msg" id="footNewsMsg"></span>' +
        '<p class="fn-fine">By subscribing you authorize Evision Infoserve to send you updates by email, and you accept our ' +
          '<a href="' + P + 'terms.html">Terms</a> and <a href="' + P + 'privacy-policy.html">Privacy Policy</a>. Unsubscribe anytime.</p>' +
      '</form>' +
    '</div>' +
    '<div class="foot-bottom"><div class="copy">© 2026 Evision Infoserve. All rights reserved.</div>' +
      '<div class="foot-layers"><i data-lucide="sparkles" style="width:15px;height:15px"></i>Design &amp; build · <b>SEO · AEO · GEO · LLMO</b></div>' +
      '<div class="legal"><a href="' + P + 'privacy-policy.html">Privacy</a><a href="' + P + 'terms.html">Terms</a><a href="' + P + 'refund-policy.html">Refund</a></div>' +
    '</div></div></footer>';

  var WIDGETS =
    '<div class="chat-panel" id="chatPanel"><div class="chat-head">' +
      '<div class="chat-ava">Ei</div><div><div class="t">Evision Assistant</div><div class="s">Typically replies in a minute</div></div>' +
      '<span class="x" id="chatClose"><i data-lucide="x"></i></span></div>' +
      '<div class="chat-body" id="chatBody">' +
        '<div class="bubble bot">Hi 👋 Welcome to Evision Infoserve! Need a new website, SEO, or a combined package? Tell us what you\'re after.</div>' +
      '</div>' +
      '<div class="chat-quick" id="chatQuick">' +
        '<button data-q="I need a new website designed and developed">I need a website</button>' +
        '<button data-q="I want an SEO / website audit">Get a free audit</button>' +
        '<button data-q="I would like to talk to your team">Talk to our team</button>' +
        '<button data-q="Tell me about AI search (GEO/LLMO)">AI search (GEO/LLMO)</button>' +
      '</div>' +
      '<form class="chat-foot" id="chatForm"><input id="chatInput" placeholder="Type your message…" autocomplete="off">' +
        '<button type="submit" aria-label="Send"><i data-lucide="send" style="width:18px;height:18px"></i></button></form>' +
    '</div>' +
    '<div class="floaties">' +
      '<a class="fab fab-wa fab-pulse" href="https://wa.me/919311221517" aria-label="WhatsApp"><i data-lucide="message-circle" class="ic"></i></a>' +
      '<button class="fab fab-chat" id="chatToggle" aria-label="Open chat"><i data-lucide="messages-square" class="ic"></i></button>' +
    '</div>';

  // ── Mobile bottom action bar (phones only; styled via .m-cta-bar media query) ──
  var M_CTA =
    '<div class="m-cta-bar">' +
      '<a href="tel:+919311221517" class="m-cta m-cta-call"><i data-lucide="phone" class="ic"></i>Call Us</a>' +
      '<a href="mailto:info@evisioninfoserve.com" class="m-cta m-cta-mail"><i data-lucide="mail" class="ic"></i>Email Us</a>' +
      '<a href="https://wa.me/919311221517" class="m-cta m-cta-wa"><i data-lucide="message-circle" class="ic"></i>WhatsApp</a>' +
    '</div>';

  // ── Free Audit modal ──
  var auditOpts = SERVICES.map(function (s) { return '<option>' + s[0] + '</option>'; }).join("");
  var AUDIT_MODAL =
    '<div class="audit-modal" id="auditModal" aria-hidden="true">' +
      '<div class="audit-scrim" data-audit-close></div>' +
      '<div class="audit-dialog" role="dialog" aria-modal="true" aria-labelledby="auditTitle">' +
        '<button class="audit-x" data-audit-close aria-label="Close">&times;</button>' +
        '<div id="auditFormWrap">' +
          '<span class="audit-eyebrow"><i data-lucide="sparkles"></i> Free Website + SEO Consult</span>' +
          '<h3 id="auditTitle">Get your free quote &amp; audit</h3>' +
          '<p class="audit-sub">Tell us what you need — a new website, SEO, or both. A strategist sends you a tailored quote and a 12-point audit within <b>24 hours</b> — no cost, no obligation.</p>' +
          '<form id="auditForm" novalidate>' +
            '<div class="audit-row">' +
              '<input type="text" name="name" placeholder="Full name *" autocomplete="name">' +
              '<input type="email" name="email" placeholder="Work email *" autocomplete="email">' +
            '</div>' +
            '<div class="audit-row">' +
              '<input type="tel" name="phone" placeholder="Phone / WhatsApp *" autocomplete="tel">' +
              '<input type="text" name="website" placeholder="Website URL">' +
            '</div>' +
            '<select name="service"><option value="">What are you looking for?…</option>' + auditOpts + '</select>' +
            '<label class="audit-consent"><input type="checkbox" id="auditConsent">' +
              '<span>I authorize <b>Evision Infoserve</b> to send me my audit report and related notifications via ' +
              '<b>SMS, RCS, Call, Email &amp; WhatsApp</b> — including on a number registered with DND/NCPR — and I accept the ' +
              '<a href="' + P + 'terms.html" target="_blank" rel="noopener" data-audit-noop>Terms &amp; Conditions</a> and ' +
              '<a href="' + P + 'privacy-policy.html" target="_blank" rel="noopener" data-audit-noop>Privacy Policy</a>.</span></label>' +
            '<div class="audit-err" id="auditErr"></div>' +
            '<button type="submit" class="btn btn-primary btn-block btn-lg">Get my free quote &amp; audit <i data-lucide="arrow-right" class="ic"></i></button>' +
            '<p class="audit-fine">We respect your inbox — unsubscribe anytime.</p>' +
          '</form>' +
        '</div>' +
        '<div class="audit-success" id="auditSuccess" style="display:none">' +
          '<div class="audit-ok"><i data-lucide="check"></i></div>' +
          '<h3>You\'re all set! 🎉</h3>' +
          '<p>Thanks — we\'ve received your details. Our team will email your free audit report within <b>24 hours</b>. Need it faster? Ping us on WhatsApp.</p>' +
          '<a href="https://wa.me/919311221517" class="btn btn-secondary btn-block">Chat on WhatsApp</a>' +
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
            '<label class="audit-consent"><input type="checkbox" id="startConsent">' +
              '<span>I authorize <b>Evision Infoserve</b> to contact me via <b>SMS, RCS, Call, Email &amp; WhatsApp</b> ' +
              '— including on a number registered with DND/NCPR — and I accept the ' +
              '<a href="' + P + 'terms.html" target="_blank" rel="noopener" data-audit-noop>Terms &amp; Conditions</a> and ' +
              '<a href="' + P + 'privacy-policy.html" target="_blank" rel="noopener" data-audit-noop>Privacy Policy</a>.</span></label>' +
            '<div class="audit-err" id="startErr"></div>' +
            '<button type="submit" class="btn btn-primary btn-block btn-lg">Request a callback <i data-lucide="phone-call" class="ic"></i></button>' +
            '<p class="audit-fine">We\'ll reach out via call &amp; WhatsApp. No spam, ever.</p>' +
          '</form>' +
        '</div>' +
        '<div class="audit-success" id="startSuccess" style="display:none">' +
          '<div class="audit-ok"><i data-lucide="check"></i></div>' +
          '<h3>Thank you! 🎉</h3>' +
          '<p>We\'ve received your request. Our team will contact you <b>shortly via call and WhatsApp</b>. Prefer to chat now?</p>' +
          '<a href="https://wa.me/919311221517" class="btn btn-secondary btn-block">Message us on WhatsApp</a>' +
        '</div>' +
      '</div>' +
    '</div>';

  // ── Top offer / urgency banner (content filled from /api/pricing offer) ──
  var TOPBAR =
    '<div class="ev-topbar" id="evTopbar" hidden><div class="ev-topbar-in" id="evTopbarIn">' +
      '<span>🚀 <b>Websites from ₹9,999</b> — free SEO audit with every build.</span>' +
      '<a href="' + P + 'contact.html" data-audit-open class="ev-tb-cta">Get a free quote →</a>' +
    '</div><button class="ev-tb-x" id="evTopbarX" aria-label="Dismiss">&times;</button></div>';

  // ── Sticky bottom CTA bar (desktop; phones use the m-cta bar instead) ──
  var STICKY_BAR =
    '<div class="ev-stickybar" id="evStickyBar">' +
      '<div class="ev-sb-in">' +
        '<div class="ev-sb-copy"><b>Launch a website from ₹9,999</b>' +
          '<span>Free quote + a website &amp; SEO plan within 24 hours.</span></div>' +
        '<div class="ev-sb-actions">' +
          '<a href="' + P + 'contact.html" data-audit-open class="btn btn-primary btn-sm">Get a free quote</a>' +
          '<a href="https://wa.me/919311221517" class="btn btn-ghost-light btn-sm"><i data-lucide="message-circle" class="ic"></i>WhatsApp</a>' +
          '<button class="ev-sb-x" id="evSbX" aria-label="Dismiss">&times;</button>' +
        '</div>' +
      '</div>' +
    '</div>';

  // ── Component styles (injected so we don't have to version-bump chrome.css) ──
  var LEADGEN_CSS =
    '.ev-topbar{position:relative;z-index:60;background:linear-gradient(90deg,#0A0E1C,#241b52);color:#fff;font-size:13.5px}' +
    '.ev-topbar-in{max-width:1200px;margin:0 auto;padding:9px 44px;display:flex;align-items:center;justify-content:center;gap:14px;text-align:center;flex-wrap:wrap}' +
    '.ev-topbar b{color:#F5B62B}.ev-topbar .ev-tb-cta{color:#fff;font-weight:700;text-decoration:underline;text-underline-offset:2px;white-space:nowrap}' +
    '.ev-topbar .ev-tb-x{position:absolute;right:12px;top:50%;transform:translateY(-50%);background:none;border:none;color:rgba(255,255,255,.6);cursor:pointer;font-size:19px;line-height:1;padding:4px}' +
    '.ev-topbar .ev-tb-x:hover{color:#fff}@media(max-width:600px){.ev-topbar{font-size:12px}}' +
    '.ev-stickybar{position:fixed;left:0;right:0;bottom:0;z-index:55;background:rgba(10,14,28,.97);border-top:1px solid rgba(255,255,255,.1);color:#fff;transform:translateY(115%);transition:transform .35s ease}' +
    '.ev-stickybar.show{transform:translateY(0)}' +
    '.ev-sb-in{max-width:1200px;margin:0 auto;padding:11px 20px;display:flex;align-items:center;justify-content:space-between;gap:18px}' +
    '.ev-sb-copy b{font-family:var(--font-headline);font-size:16px;letter-spacing:-.01em}' +
    '.ev-sb-copy span{display:block;font-size:13px;color:rgba(255,255,255,.7);margin-top:2px}' +
    '.ev-sb-actions{display:flex;align-items:center;gap:10px;flex:none}' +
    '.ev-sb-x{background:none;border:none;color:rgba(255,255,255,.55);cursor:pointer;font-size:22px;line-height:1;padding:2px 4px}.ev-sb-x:hover{color:#fff}' +
    '@media(max-width:720px){.ev-stickybar{display:none}}' +
    '.foot-news{border-top:1px solid rgba(255,255,255,.08);margin-top:10px;padding:24px 0 6px;display:flex;align-items:center;justify-content:space-between;gap:22px;flex-wrap:wrap}' +
    '.foot-news .fn-copy h4{color:#fff;font-size:17px;margin:0}.foot-news .fn-copy p{color:rgba(255,255,255,.6);font-size:13.5px;margin:4px 0 0}' +
    '.fn-form{display:flex;gap:8px;align-items:center;flex-wrap:wrap}' +
    '.fn-form input{padding:11px 14px;border-radius:10px;border:1px solid rgba(255,255,255,.15);background:rgba(255,255,255,.06);color:#fff;font-size:14px;min-width:240px}' +
    '.fn-form input::placeholder{color:rgba(255,255,255,.5)}.fn-form input:focus{outline:none;border-color:#6D5EFB}' +
    '.fn-form input.fn-bad{border-color:#ef4444}.fn-msg{font-size:12.5px;color:#F5B62B;flex-basis:100%}' +
    '.fn-fine{flex-basis:100%;font-size:11.5px;line-height:1.5;color:rgba(255,255,255,.45);margin:2px 0 0;max-width:420px}' +
    '.fn-fine a{color:rgba(255,255,255,.7);text-decoration:underline}';
  var st = document.createElement("style"); st.textContent = LEADGEN_CSS; document.head.appendChild(st);

  // ── inject ──
  document.body.insertAdjacentHTML("afterbegin", TOPBAR + HEADER + DRAWER);
  document.body.insertAdjacentHTML("beforeend", FOOTER + WIDGETS + M_CTA + STICKY_BAR + AUDIT_MODAL + START_MODAL);

  // Rewrite every internal .html link (injected chrome + page content) to its clean URL.
  // Run again on load to catch links injected by later scripts (e.g. the offer banner).
  cleanHrefs(document);
  window.addEventListener("load", function () { cleanHrefs(document); });

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
      pricing: "Our plans are tailored to your goals and scope, so we share a custom quote rather than fixed prices. Tell me a bit about your business and I'll have a strategist send pricing — or reach us on WhatsApp at +91 93112 21517.",
      ai: "We optimise across 4 layers — SEO, AEO, GEO &amp; LLMO — so you rank on Google AND get cited by ChatGPT, Gemini &amp; Perplexity. Shall I send our AI-search guide?",
      default: "Thanks! A strategist will reach out shortly. You can also reach us on WhatsApp at +91 93112 21517 for an instant reply. 🚀"
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

  // ── Auto lead popup: fire once per session, on scroll depth OR after dwell time ──
  (function () {
    var SEEN = "ev_lead_popup_seen";
    try { if (sessionStorage.getItem(SEEN)) return; } catch (e) {}
    var DWELL_MS = 22000;     // fire after ~22s on the page…
    var SCROLL_PCT = 0.35;    // …or once the visitor scrolls 35% down, whichever first
    var done = false, timer;
    function anyModalOpen() {
      return auditModal.classList.contains("open") || (startModal && startModal.classList.contains("open"));
    }
    function cleanup() {
      window.removeEventListener("scroll", onScroll);
      clearTimeout(timer);
    }
    function fire() {
      if (done) return;
      if (anyModalOpen()) return;   // don't interrupt an already-open form; try again on next scroll
      done = true;
      try { sessionStorage.setItem(SEEN, "1"); } catch (e) {}
      cleanup();
      openAudit();
    }
    function onScroll() {
      var top = window.scrollY || document.documentElement.scrollTop;
      var max = document.documentElement.scrollHeight - window.innerHeight;
      if (max > 0 && top / max >= SCROLL_PCT) fire();
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    timer = setTimeout(fire, DWELL_MS);
    // If the visitor opens/submits any lead form themselves, don't nag them later.
    document.addEventListener("submit", function (e) {
      if (e.target && (e.target.id === "auditForm" || e.target.id === "startForm")) {
        try { sessionStorage.setItem(SEEN, "1"); } catch (ex) {}
        done = true; cleanup();
      }
    }, true);
  })();

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
    var startConsent = document.getElementById("startConsent");
    if (startConsent && !startConsent.checked) {
      err.textContent = "Please authorize us to contact you so we can call you back."; return;
    }
    var payload = {
      type: "get-started", name: nameV, phone: phoneV, email: emailV,
      service: get("service").value, message: get("message").value.trim(),
      source: (location.pathname.split("/").pop() || "home") + " (get started)",
      consent: 1, marketing: 0
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
      consent: consent.checked ? 1 : 0, marketing: consent.checked ? 1 : 0
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

  // ── Top offer banner: show default now, upgrade to the admin offer if set ──
  (function () {
    var bar = document.getElementById("evTopbar"), x = document.getElementById("evTopbarX");
    if (!bar) return;
    try { if (localStorage.getItem("ev_topbar_dismiss")) { bar.remove(); return; } } catch (e) {}
    function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
    bar.hidden = false;  // show the evergreen message immediately
    fetch("/api/pricing").then(function (r) { return r.json(); }).then(function (d) {
      var o = d && d.offer;
      if (o && o.discount_pct > 0) {
        document.getElementById("evTopbarIn").innerHTML =
          '<span>🎉 <b>' + esc(o.name || "Limited-time offer") + ': save ' + o.discount_pct + '%</b>' +
          (o.note ? ' — ' + esc(o.note) : '') + '</span>' +
          '<a href="' + P + 'pricing.html" class="ev-tb-cta">Claim offer →</a>';
        cleanHrefs(bar);
      }
    }).catch(function () {});
    x.addEventListener("click", function () {
      bar.remove(); try { localStorage.setItem("ev_topbar_dismiss", "1"); } catch (e) {}
    });
  })();

  // ── Sticky bottom CTA bar (desktop): reveal after scrolling, dismissible ──
  (function () {
    var bar = document.getElementById("evStickyBar"), x = document.getElementById("evSbX");
    if (!bar) return;
    try { if (localStorage.getItem("ev_stickybar_dismiss")) return; } catch (e) {}
    function onScroll() { bar.classList.toggle("show", (window.scrollY || 0) > 640); }
    window.addEventListener("scroll", onScroll, { passive: true }); onScroll();
    x.addEventListener("click", function () {
      bar.classList.remove("show");
      window.removeEventListener("scroll", onScroll);
      try { localStorage.setItem("ev_stickybar_dismiss", "1"); } catch (e) {}
    });
  })();

  // ── Footer newsletter → /api/enquiry (type=newsletter) ──
  (function () {
    var f = document.getElementById("footNews"); if (!f) return;
    var input = f.querySelector('[name="email"]'), msg = document.getElementById("footNewsMsg");
    input.addEventListener("input", function () { input.classList.remove("fn-bad"); if (msg) msg.textContent = ""; });
    f.addEventListener("submit", function (e) {
      e.preventDefault();
      var email = input.value.trim();
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { input.classList.add("fn-bad"); if (msg) msg.textContent = "Please enter a valid email."; return; }
      var btn = f.querySelector("button[type=submit]"); btn.disabled = true; btn.textContent = "Subscribing…";
      var payload = { name: "Newsletter subscriber", email: email, type: "newsletter",
        source: (location.pathname.split("/").pop() || "home") + " (newsletter)", consent: 1, marketing: 1 };
      function done() { f.innerHTML = '<span class="fn-msg" style="color:#4ade80;font-size:14px">✓ You\'re subscribed — watch your inbox!</span>'; }
      fetch("/api/enquiry", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(done).catch(done);
    });
  })();

  // ── Exit-intent (desktop): one extra chance to capture, shares the popup flag ──
  (function () {
    if (window.matchMedia && window.matchMedia("(max-width: 720px)").matches) return;
    var SEEN = "ev_lead_popup_seen";
    function armed() { try { return !sessionStorage.getItem(SEEN); } catch (e) { return true; } }
    function onOut(e) {
      if (!armed()) { document.removeEventListener("mouseout", onOut); return; }
      if (e.clientY > 0 || e.relatedTarget) return;  // only fire when the cursor leaves via the top
      if (auditModal.classList.contains("open") || (startModal && startModal.classList.contains("open"))) return;
      try { sessionStorage.setItem(SEEN, "1"); } catch (ex) {}
      document.removeEventListener("mouseout", onOut);
      openAudit();
    }
    setTimeout(function () { document.addEventListener("mouseout", onOut); }, 5000);  // arm after 5s
  })();

  // reveal on scroll
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); } });
  }, { threshold: 0.12 });
  document.querySelectorAll(".reveal").forEach(function (el) { io.observe(el); });

  if (window.lucide) lucide.createIcons();
})();
