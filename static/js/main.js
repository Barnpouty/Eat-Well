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
