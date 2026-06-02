/* ============================================================
   EVISION — public pricing renderer
   • site-wide festival offer banner
   • per-page price strips  (elements with [data-price-slug])
   • full pricing grid       (element with [data-pricing-grid])
   Data source: GET /api/pricing  (prices/discounts set in the admin panel)
   ============================================================ */
(function () {
  var CACHE = null;
  function inr(n) { return "₹" + Number(n).toLocaleString("en-IN"); }

  function fetchPricing() {
    if (CACHE) return Promise.resolve(CACHE);
    return fetch("/api/pricing").then(function (r) { return r.json(); })
      .then(function (d) { CACHE = d; return d; });
  }

  function unitLabel(s) {
    if (!s.unit) return "";
    return s.unit === "one-time" ? " one-time" : s.unit;
  }

  // ── per-page price strip ──
  function priceStripHTML(s) {
    var disc = s.effective_discount;
    var amount = disc
      ? '<span class="ps-old">' + inr(s.price) + '</span> <b>' + inr(s.final_price) + '</b>'
      : '<b>' + inr(s.price) + '</b>';
    var badge = disc ? '<span class="ps-badge">' + disc + '% OFF</span>' : '';
    return '<div class="container"><div class="price-strip-inner">' +
        '<div>' +
          '<span class="ps-label">' + (s.starting ? "Starting at" : "Price") + '</span>' +
          '<div class="ps-amount">' + amount +
            '<span class="ps-unit">' + unitLabel(s) + '</span> ' + badge + '</div>' +
        '</div>' +
        '<a href="contact.html" data-audit-open class="btn btn-primary btn-lg">Get Started</a>' +
      '</div></div>';
  }

  function renderStrips(data) {
    var map = {};
    data.services.forEach(function (s) { map[s.slug] = s; });
    document.querySelectorAll("[data-price-slug]").forEach(function (el) {
      var s = map[el.getAttribute("data-price-slug")];
      if (s) el.innerHTML = priceStripHTML(s);
      else el.style.display = "none";
    });
  }

  // ── site-wide offer banner ──
  function renderBanner(offer) {
    if (!offer || document.querySelector(".offer-banner")) return;
    var bar = document.createElement("div");
    bar.className = "offer-banner";
    bar.innerHTML = '<div class="container">🎉 <b>' + offer.name + '</b> — ' +
      offer.discount_pct + '% OFF all services' +
      (offer.note ? ' · ' + offer.note : '') +
      ' <a href="pricing.html">View pricing →</a></div>';
    document.body.insertBefore(bar, document.body.firstChild);
  }

  // ── full pricing grid (pricing page) ──
  function renderGrid(data) {
    var grid = document.querySelector("[data-pricing-grid]");
    if (!grid) return;
    var order = ["SEO", "Content Marketing", "Other Services"];
    var byCat = {};
    data.services.forEach(function (s) { (byCat[s.category] = byCat[s.category] || []).push(s); });
    var cats = order.filter(function (c) { return byCat[c]; })
      .concat(Object.keys(byCat).filter(function (c) { return order.indexOf(c) < 0; }));
    var html = "";
    cats.forEach(function (cat) {
      html += '<h3 class="pg-cat">' + cat + '</h3><div class="pg-rows">';
      byCat[cat].forEach(function (s) {
        var disc = s.effective_discount;
        var price = disc
          ? '<span class="pg-old">' + inr(s.price) + '</span> <b>' + inr(s.final_price) + '</b>'
          : '<b>' + inr(s.price) + '</b>';
        html += '<a class="pg-row" href="' + s.slug + '.html">' +
          '<div class="pg-name"><span class="pg-title">' + s.name +
            (disc ? ' <span class="ps-badge">' + disc + '% OFF</span>' : '') + '</span>' +
            '<span class="pg-desc">' + (s.description || "") + '</span></div>' +
          '<div class="pg-price">' + (s.starting ? '<span class="pg-from">from</span> ' : '') +
            price + '<span class="pg-unit">' + unitLabel(s) + '</span></div>' +
          '</a>';
      });
      html += '</div>';
    });
    grid.innerHTML = html;
  }

  function run() {
    fetchPricing().then(function (data) {
      renderBanner(data.offer);
      renderStrips(data);
      renderGrid(data);
    }).catch(function () { /* keep the page usable if the API is down */ });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run);
  else run();
})();
