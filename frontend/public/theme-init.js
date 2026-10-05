// Theme before first paint: saved choice, otherwise the system setting. A file, not inline: CSP allows 'self' only.
(function () {
  try {
    var saved = localStorage.getItem('fsp-theme');
    var dark = saved ? saved === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  } catch (e) { document.documentElement.setAttribute('data-theme', 'light'); }
})();
