(() => {
  // Expand the collapsed job description on a LinkedIn detail page BEFORE reading it.
  // LinkedIn hides the JD overflow behind a "… more" / "see more" toggle, and the hidden
  // text is NOT in `main.innerText` until the toggle is clicked. Without this the JD and
  // Key Requirements come out truncated (ending in "… more"). Click, then read on the
  // next eval (after a wait) so React has re-rendered the expanded text.
  // NOTE: file must START with "(" — a leading comment makes eval wrappers return null.
  let n = 0;
  document.querySelectorAll(
    'button.jobs-description__footer-button, button[aria-label*="see more description" i], ' +
    'button[aria-label*="see more" i], .show-more-less-html__button'
  ).forEach(b => { try { b.click(); n++; } catch (e) {} });
  document.querySelectorAll('button, a').forEach(b => {
    const t = (b.innerText || '').trim().toLowerCase();
    if (t === 'see more' || t === '…more' || t === '… more' || t === 'show more' || t === 'click to see more') {
      try { b.click(); n++; } catch (e) {}
    }
  });
  return 'clicked=' + n;
})()
