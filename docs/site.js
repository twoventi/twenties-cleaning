/* Nessun cookie, nessun localStorage, nessun servizio esterno.
   La lingua si sceglie con ?lang=it|en nell'indirizzo (altrimenti segue il browser). */
(function () {
  var d = document, h = d.documentElement, SUP = ["it", "en"];
  var q = new URLSearchParams(location.search).get("lang");
  var lang = SUP.indexOf(q) > -1 ? q : ((navigator.language || "it").slice(0, 2).toLowerCase() === "en" ? "en" : "it");
  function apply(l, push) {
    lang = l; h.lang = l;
    d.querySelectorAll(".lang button").forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.l === l ? "true" : "false"); });
    d.querySelectorAll('a[href]:not([href^="http"]):not([href^="#"]):not([href^="mailto:"])').forEach(function (a) {
      var u = a.getAttribute("href").split("?")[0]; var hash = a.getAttribute("href").split("#")[1];
      a.setAttribute("href", u.split("#")[0] + "?lang=" + l + (hash ? "#" + hash : ""));
    });
    var t = d.querySelector("title[data-" + l + "]"); if (t) d.title = t.getAttribute("data-" + l);
    var m = d.querySelector('meta[name="description"]'); if (m && m.dataset[l]) m.content = m.dataset[l];
    if (push) { var u = new URL(location.href); u.searchParams.set("lang", l); history.replaceState(null, "", u); }
  }
  d.querySelectorAll(".lang button").forEach(function (b) { b.addEventListener("click", function () { apply(b.dataset.l, true); }); });
  apply(lang, false);
  /* comparsa graduale, solo se il movimento non è ridotto */
  if (!matchMedia("(prefers-reduced-motion: reduce)").matches && "IntersectionObserver" in window) {
    h.classList.add("js");
    var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }); }, { threshold: .12 });
    d.querySelectorAll(".rv").forEach(function (el) { io.observe(el); });
  }
})();
