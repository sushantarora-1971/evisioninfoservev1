/* ============================================================
   EVISION INFOSERVE — Page interactions
   FAQ accordions · form validation · counters · pricing toggle · TOC
   ============================================================ */
(function () {
  // ── FAQ accordions ──
  document.querySelectorAll(".faq-q").forEach(function (q) {
    q.addEventListener("click", function () {
      var item = q.closest(".faq-item");
      var a = item.querySelector(".faq-a");
      var open = item.classList.contains("open");
      // close siblings in same .faq group
      var group = item.closest(".faq");
      if (group) group.querySelectorAll(".faq-item.open").forEach(function (o) {
        if (o !== item) { o.classList.remove("open"); o.querySelector(".faq-a").style.maxHeight = null; }
      });
      item.classList.toggle("open", !open);
      a.style.maxHeight = open ? null : a.scrollHeight + "px";
    });
  });

  // ── animated counters ──
  function animateCount(el) {
    var raw = el.dataset.count;
    var target = parseFloat(raw);
    var suffix = el.dataset.suffix || "";
    var prefix = el.dataset.prefix || "";
    var dec = (raw.split(".")[1] || "").length;
    var start = 0, dur = 1400, t0 = null;
    function step(t) {
      if (!t0) t0 = t;
      var p = Math.min((t - t0) / dur, 1);
      var e = 1 - Math.pow(1 - p, 3);
      var val = (start + (target - start) * e);
      el.textContent = prefix + (dec ? val.toFixed(dec) : Math.round(val).toLocaleString("en-IN")) + suffix;
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }
  var cio = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) { if (en.isIntersecting) { animateCount(en.target); cio.unobserve(en.target); } });
  }, { threshold: 0.5 });
  document.querySelectorAll("[data-count]").forEach(function (el) { cio.observe(el); });

  // ── pricing billing toggle ──
  var billToggle = document.getElementById("billToggle");
  if (billToggle) {
    billToggle.addEventListener("change", function () {
      var annual = billToggle.checked;
      document.querySelectorAll("[data-monthly]").forEach(function (el) {
        el.textContent = annual ? el.dataset.annual : el.dataset.monthly;
      });
      document.querySelectorAll(".bill-period").forEach(function (el) { el.textContent = annual ? "/mo billed yearly" : "/month"; });
      var sav = document.getElementById("billSave"); if (sav) sav.style.opacity = annual ? "1" : "0";
    });
  }

  // ── generic form validation (RFQ / contact) ──
  document.querySelectorAll("form[data-validate]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var ok = true;
      form.querySelectorAll("[required]").forEach(function (inp) {
        var field = inp.closest(".field");
        var valid = inp.type === "email" ? /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(inp.value) :
          inp.type === "tel" ? inp.value.replace(/\D/g, "").length >= 8 : inp.value.trim() !== "";
        if (field) field.classList.toggle("error", !valid);
        if (!valid) ok = false;
      });
      if (!ok) { var first = form.querySelector(".field.error input, .field.error select, .field.error textarea"); if (first) first.focus(); return; }
      var success = form.querySelector("[data-success]") || document.getElementById(form.dataset.success);
      function showSuccess() { form.style.display = "none"; if (success) success.style.display = ""; }

      // If the form targets an API endpoint, persist the enquiry first.
      var endpoint = form.getAttribute("data-api");
      if (endpoint) {
        var payload = {};
        form.querySelectorAll("[name]").forEach(function (inp) {
          payload[inp.name] = inp.type === "checkbox" ? (inp.checked ? 1 : 0) : inp.value;
        });
        payload.source = location.pathname.split("/").pop() || "contact";
        var btn = form.querySelector("button[type=submit]");
        if (btn) btn.disabled = true;
        fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        }).then(function () { showSuccess(); })
          .catch(function () { showSuccess(); }); // never block the visitor on a network hiccup
        return;
      }
      showSuccess();
    });
    form.querySelectorAll("input,select,textarea").forEach(function (inp) {
      inp.addEventListener("input", function () { var f = inp.closest(".field"); if (f) f.classList.remove("error"); });
    });
  });

  // ── TOC scrollspy (blog/service) ──
  var tocLinks = document.querySelectorAll("[data-toc] a");
  if (tocLinks.length) {
    var sections = [].map.call(tocLinks, function (a) { return document.querySelector(a.getAttribute("href")); });
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          var id = "#" + en.target.id;
          tocLinks.forEach(function (a) { a.classList.toggle("active", a.getAttribute("href") === id); });
        }
      });
    }, { rootMargin: "-30% 0px -60% 0px" });
    sections.forEach(function (s) { if (s) spy.observe(s); });
  }

  // ── service tabs (optional) ──
  document.querySelectorAll("[data-tabs]").forEach(function (wrap) {
    var btns = wrap.querySelectorAll("[data-tab]");
    btns.forEach(function (b) {
      b.addEventListener("click", function () {
        btns.forEach(function (x) { x.classList.remove("active"); });
        b.classList.add("active");
        var id = b.dataset.tab;
        wrap.querySelectorAll("[data-panel]").forEach(function (p) { p.style.display = p.dataset.panel === id ? "" : "none"; });
      });
    });
  });
})();
