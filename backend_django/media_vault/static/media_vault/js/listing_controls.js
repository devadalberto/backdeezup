(function () {
  "use strict";

  var LIMITS = [20, 50, 100, 200];
  var DEFAULT = 50;

  function getParam(name) {
    return new URLSearchParams(window.location.search).get(name);
  }

  function buildDropdown(position) {
    var current = parseInt(getParam("limit") || DEFAULT, 10);
    var wrap = document.createElement("div");
    wrap.className = "w-limit-control w-limit-control--" + position;
    wrap.style.cssText = "display:flex;align-items:center;gap:0.5rem;padding:0.5rem 1.5rem;";

    var label = document.createElement("label");
    label.textContent = "Per page:";
    label.htmlFor = "w-limit-select-" + position;
    label.style.cssText = "font-size:0.8125rem;white-space:nowrap;color:var(--w-color-text-label,#ccc);";

    var sel = document.createElement("select");
    sel.id = "w-limit-select-" + position;
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
    // Avoid double-injection on HTMX partial swaps
    document.querySelectorAll(".w-limit-control").forEach(function (el) { el.remove(); });

    document.querySelectorAll("nav.pagination").forEach(function (nav) {
      var top = buildDropdown("top");
      var bottom = buildDropdown("bottom");
      nav.parentNode.insertBefore(top, nav);
      nav.parentNode.insertBefore(bottom, nav.nextSibling);
    });
  }

  // Initial load
  document.addEventListener("DOMContentLoaded", injectControls);

  // HTMX partial swap (Wagtail uses HTMX for search/filter results)
  document.addEventListener("htmx:afterSwap", injectControls);
})();
