// Footer year
const yearEl = document.getElementById("year");
if (yearEl) yearEl.textContent = new Date().getFullYear();

// One orchestrated reveal on load for the hero only — deliberately not
// applied to every section. Uses a CSS class rather than inline styles so
// content is never dependent on JS to become visible.
document.addEventListener("DOMContentLoaded", () => {
  const hero = document.querySelector(".hero");
  if (hero) hero.classList.add("hero--visible");
});

// Privacy-friendly analytics for checkout clicks (only if analytics is configured;
// sends the button's location, never anything about the visitor).
document.addEventListener("click", (e) => {
  const a = e.target.closest && e.target.closest("a[data-checkout]");
  if (a && typeof window.plausible === "function") {
    try { window.plausible("Checkout Click", { props: { location: a.getAttribute("data-checkout") } }); } catch (err) { /* ignore */ }
  }
});
