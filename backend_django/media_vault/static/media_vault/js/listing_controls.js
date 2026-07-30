(function () {
  "use strict";

  var LIMITS = [20, 50, 100, 200];
  var DEFAULT = 50;

  function getParam(name) {
    return new URLSearchParams(window.location.search).get(name);
  }

  function buildDropdown(id_suffix) {
    var current = parseInt(getParam("limit") || DEFAULT, 10);
    var wrap = document.createElement("div");
    wrap.className = "w-limit-control";
    wrap.style.cssText = "display:flex;align-items:center;gap:0.5rem;padding:0.4rem 1.5rem;";

    var label = document.createElement("label");
    label.textContent = "Per page:";
    label.htmlFor = "w-limit-select-" + id_suffix;
    label.style.cssText = "font-size:0.8125rem;white-space:nowrap;color:var(--w-color-text-label,#ccc);";

    var sel = document.createElement("select");
    sel.id = "w-limit-select-" + id_suffix;
    sel.style.cssText = [
      "background:var(--w-color-surface-menus,#1a1a2e)",
      "color:var(--w-color-text-label,#00ff41)",
      "border:1px solid currentColor",
      "border-radius:4px",
      "padding:2px 8px",
      "font-size:0.8125rem",
      "cursor:pointer",
    ].join(";");

    LIMITS.forEach(function (n) {
      var opt = document.createElement("option");
      opt.value = n;
      opt.textContent = n;
      if (n === current) opt.selected = true;
      sel.appendChild(opt);
    });

    sel.addEventListener("change", function () {
      var url = new URL(window.location.href);
      url.searchParams.set("limit", sel.value);
      url.searchParams.delete("p");
      window.location.href = url.toString();
    });

    wrap.appendChild(label);
    wrap.appendChild(sel);
    return wrap;
  }

  function injectControls() {
    document.querySelectorAll(".w-limit-control").forEach(function (el) { el.remove(); });

    var idx = 0;

    // Inject ABOVE the listing (image grid, table, or list)
    var listingTargets = [
      "ul.listing",       // image grid
      "table.listing",    // table listings
      "div.listing",      // generic listing
    ];
    listingTargets.forEach(function (sel) {
      document.querySelectorAll(sel).forEach(function (el) {
        var top = buildDropdown("top-" + idx++);
        el.parentNode.insertBefore(top, el);
      });
    });

    // Inject ABOVE and BELOW each pagination nav
    document.querySelectorAll("nav.pagination").forEach(function (nav) {
      // above
      var above = buildDropdown("above-" + idx++);
      nav.parentNode.insertBefore(above, nav);
      // below
      var below = buildDropdown("below-" + idx++);
      nav.parentNode.insertBefore(below, nav.nextSibling);
    });
  }

  document.addEventListener("DOMContentLoaded", injectControls);
  document.addEventListener("htmx:afterSwap", injectControls);
})();
