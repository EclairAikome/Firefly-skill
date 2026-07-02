(() => {
  // Extract a LinkedIn job detail page (standalone /jobs/view/<id>/ layout).
  // The standalone page uses unstable class names, so we grab `main` innerText and let
  // the Python parser pull location / posted-date / experience / JD heuristically.
  // Returns JSON {title, status, txt}.
  // NOTE: file must START with "(" — a leading comment makes eval wrappers return null.
  const title = (document.querySelector('h1')?.innerText || '').trim() || document.title;
  const main = document.querySelector('main') || document.body;
  let txt = (main.innerText || '').replace(/\r/g, '');
  const idx = txt.indexOf(title);          // trim leading nav noise
  if (idx > 0) txt = txt.slice(idx);
  // Cap high enough to hold a fully-expanded JD (the "see more" toggle must be clicked first,
  // see click_seemore.js). 7000 was too tight and clipped long descriptions.
  txt = txt.replace(/[ \t]+/g, ' ').slice(0, 16000);
  // Listing liveness (S1): record whether the posting is removed/closed so the parser can drop
  // dead/ghost listings. Read from the rendered apply area; the parser also re-derives this from txt.
  let status = 'open';
  if (/job posting (?:may not be valid|has been removed|is no longer available)|unable to load the page/i.test(txt)) status = 'removed';
  else if (/no longer accepting applications/i.test(txt)) status = 'closed';
  return JSON.stringify({ title, status, txt });
})()
