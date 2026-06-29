// Scroll the LinkedIn results list to trigger lazy-loading of more job cards.
// Finds the scrollable ancestor of a job card rather than relying on a fixed selector.
(() => {
  const li = document.querySelector('li[data-occludable-job-id], a[href*="/jobs/view/"]');
  let el = li;
  while (el) {
    const s = getComputedStyle(el);
    if (/(auto|scroll)/.test(s.overflowY) && el.scrollHeight > el.clientHeight) {
      el.scrollBy(0, 2500);
      return 'scrolled';
    }
    el = el.parentElement;
  }
  window.scrollBy(0, 2500);
  return 'window';
})()
