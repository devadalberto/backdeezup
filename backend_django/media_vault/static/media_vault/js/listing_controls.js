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
    wrap.style.cssText = "display:inline-flex;align-items:center;gap:0.5rem;padding:0.4rem 1.5rem;";

    var label = document.createElement("label");
    label.textContent = "Per page:";
    label.htmlFor = "w-limit-" + id_suffix;
    label.style.cssText = "font-size:0.8125rem;white-space:nowrap;color:var(--w-color-text-label,#ccc);";

    var sel = document.createElement("select");
    sel.id = "w-limit-" + id_suffix;
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
    // Remove any previously injected controls (handles HTMX swaps)
    document.querySelectorAll(".w-limit-control, .w-pagination-top").forEach(function (el) { el.remove(); });

    // Find the listing container (image grid, table, or generic list)
    var listing = document.querySelector("ul.listing, table.listing, div.listing");
    // Find the bottom pagination nav
    var nav = document.querySelector("nav.pagination");

    if (!listing && !nav) return;

    // -- TOP: dropdown + cloned pagination above the listing --
    var anchor = listing || nav;
    var topRow = document.createElement("div");
    topRow.className = "w-pagination-top";
    topRow.style.cssText = "display:flex;align-items:center;flex-wrap:wrap;gap:0.5rem;padding:0.25rem 0;";
    topRow.appendChild(buildDropdown("top"));

    if (nav) {
      var navClone = nav.cloneNode(true);
      navClone.style.flex = "1";
      // fix cloned links -- they already have correct hrefs, just strip aria-current duplication
      navClone.querySelectorAll("[aria-current]").forEach(function (el) {
        el.removeAttribute("aria-current");
      });
      topRow.appendChild(navClone);
    }

    anchor.parentNode.insertBefore(topRow, anchor);

    // -- BOTTOM: dropdown below the pagination nav --
    if (nav) {
      nav.parentNode.insertBefore(buildDropdown("bottom"), nav.nextSibling);
    }
  }

  document.addEventListener("DOMContentLoaded", injectControls);
  document.addEventListener("htmx:afterSwap", injectControls);
})();
