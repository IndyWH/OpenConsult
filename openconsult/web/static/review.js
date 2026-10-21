// The review page's two presses (spec 15.10, rulings 4 and 11): a line
// number beside an entry scrolls to that line of the transcript and marks
// it; the copy control fetches the note's plain text from the app and puts
// it on the clipboard. The text is the app's: nothing is built here.
(function () {
  const page = document.getElementById('review');
  if (!page) return;
  const WORDS = JSON.parse(document.getElementById('words').textContent);
  function show(n) {
    document.querySelectorAll('.line.marked').forEach(function (line) { line.classList.remove('marked'); });
    const line = document.getElementById('line-' + n);
    if (!line) return;
    line.classList.add('marked');
    line.scrollIntoView({block: 'center'});
  }
  document.querySelectorAll('button.cite').forEach(function (button) {
    button.addEventListener('click', function () { show(button.dataset.line); });
  });
  // The red mark beside the assessment (15.11 ruling 9): a press shows the alarm the app matched.
  const marksNode = document.getElementById('marks');
  const marks = marksNode ? JSON.parse(marksNode.textContent) : {};
  document.querySelectorAll('button.red-name').forEach(function (button) {
    button.addEventListener('click', function () {
      const alarm = marks[button.dataset.name];
      if (alarm && window.alarmDialog) window.alarmDialog.show(alarm.reasoning, alarm.actions, WORDS);
    });
  });
  const copy = document.getElementById('copy-note');
  const result = document.getElementById('copy-note-result');
  if (copy) copy.addEventListener('click', function () {
    fetch(page.dataset.path + '/note.txt').then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.text();
    }).then(function (text) { return navigator.clipboard.writeText(text); })
      .then(function () { result.textContent = WORDS.COPIED; })
      .catch(function (error) { result.textContent = WORDS.COPY_FAILED.replace('{reason}', error && error.message ? error.message : String(error)); });
  });
})();
