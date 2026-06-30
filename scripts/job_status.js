// S2 liveness probe: cheaply report whether a LinkedIn job detail page is still live.
// Returns 'removed' (404 / taken down), 'closed' (no longer accepting applications), or 'open'.
// No see-more click, no full read — just inspect the rendered apply area, so it is fast enough
// to re-ping the whole shortlist right before building the workbook.
(() => {
  const main = document.querySelector('main') || document.body;
  const t = (main.innerText || '');
  if (/job posting (?:may not be valid|has been removed|is no longer available)|unable to load the page/i.test(t)) return 'removed';
  if (/no longer accepting applications/i.test(t)) return 'closed';
  return 'open';
})()
