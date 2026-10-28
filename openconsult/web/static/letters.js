// The referral letters (spec 15.12, ruling 2 and the detail The page): on
// the review page a note line beside an item's reason shows and hides the
// line's words, which the app put on the page; on the letter's page the
// copy control fetches the approved letter's text from the app and puts
// it on the clipboard. Nothing is built here.
(function () {
  document.querySelectorAll('button.note-cite').forEach(function (button) {
    button.addEventListener('click', function () {
      const span = document.getElementById(button.getAttribute('aria-controls'));
      if (!span) return;
      span.hidden = !span.hidden;
      button.setAttribute('aria-expanded', span.hidden ? 'false' : 'true');
    });
  });
  const page = document.getElementById('letter-page');
  const copy = document.getElementById('copy-letter');
  const result = document.getElementById('copy-letter-result');
  if (!page || !copy) return;
  const WORDS = JSON.parse(document.getElementById('words').textContent);
  copy.addEventListener('click', function () {
    fetch(page.dataset.path + '/letter.txt').then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.text();
    }).then(function (text) { return navigator.clipboard.writeText(text); })
      .then(function () { result.textContent = WORDS.COPIED; })
      .catch(function (error) { result.textContent = WORDS.COPY_FAILED.replace('{reason}', error && error.message ? error.message : String(error)); });
  });
})();
