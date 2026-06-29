// Extract job cards from a LinkedIn job-search results page.
// Robust to class-name churn: keys off /jobs/view/<id> hrefs, then reads nearby text.
// Returns a JSON string array of {id, title, company, loc}.
(() => {
  const out = [], seen = new Set();
  document.querySelectorAll('a[href*="/jobs/view/"]').forEach(a => {
    const m = a.href.match(/\/jobs\/view\/(\d+)/);
    if (!m) return;
    const id = m[1];
    if (seen.has(id)) return;
    seen.add(id);
    const card = a.closest('li') || a.closest('div');
    let title = ((a.getAttribute('aria-label') || a.innerText || '').trim().split('\n')[0]) || '';
    let company = '', loc = '';
    if (card) {
      const sub = card.querySelector('.artdeco-entity-lockup__subtitle, .job-card-container__primary-description');
      if (sub) company = sub.innerText.trim();
      const cap = card.querySelector('.artdeco-entity-lockup__caption, .job-card-container__metadata-wrapper, ul.job-card-container__metadata-wrapper');
      if (cap) loc = cap.innerText.trim();
    }
    out.push({ id, title, company, loc });
  });
  return JSON.stringify(out);
})()
