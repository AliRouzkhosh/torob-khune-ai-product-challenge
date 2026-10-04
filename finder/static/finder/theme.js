// Runs before the stylesheet: explicit choice wins; absent choice follows system.
(() => {
  let choice;
  try { choice = localStorage.getItem('khane-theme'); } catch (_) {}
  document.documentElement.dataset.theme = ['light', 'dark'].includes(choice) ? choice : (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
})();
