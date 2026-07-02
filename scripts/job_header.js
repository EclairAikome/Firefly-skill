(() => {
  // Return the LEADING header of the job detail pane ("<company><job title> <location> · ...").
  // Used by the browser-details fallback to detect when LinkedIn's SPA has finished swapping
  // in the requested job: the page is "settled" once this header is non-empty and identical
  // across two reads ~1s apart. Reading the body before that yields a neighbouring job (the
  // off-by-one crosstalk bug).
  // NOTE: file must START with "(" — a leading comment makes eval wrappers return null.
  const main = document.querySelector('main') || document.body;
  let txt = (main.innerText || '').replace(/\r/g, '');
  const h1 = (document.querySelector('h1')?.innerText || '').trim();
  const i = h1 ? txt.indexOf(h1) : -1;
  if (i > 0) txt = txt.slice(i);
  return txt.replace(/\s+/g, ' ').trim().slice(0, 200);
})()
