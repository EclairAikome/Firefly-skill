// Extract a LinkedIn job detail page (standalone /jobs/view/<id>/ layout).
// The standalone page uses unstable class names, so we grab `main` innerText and let
// the Python parser pull location / posted-date / experience / JD heuristically.
// Returns JSON {title, txt}.
(() => {
  const title = (document.querySelector('h1')?.innerText || '').trim() || document.title;
  const main = document.querySelector('main') || document.body;
  let txt = (main.innerText || '').replace(/\r/g, '');
  const idx = txt.indexOf(title);          // trim leading nav noise
  if (idx > 0) txt = txt.slice(idx);
  // Cap high enough to hold a fully-expanded JD (the "see more" toggle must be clicked first,
  // see click_seemore.js). 7000 was too tight and clipped long descriptions.
  txt = txt.replace(/[ \t]+/g, ' ').slice(0, 16000);
  return JSON.stringify({ title, txt });
})()
