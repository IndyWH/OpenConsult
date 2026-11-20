// The page keeps its place (spec 15.10 ruling 34; the details of the mend
// run of step 6d, The page keeps its place). In the room run of 15 Nov 2026
// a press on a row loaded the page again with that row at the top of the
// window, which carried the eye past the next row. A press on a form marked
// data-stay (a row, Save and Undo on a line, Swap, Undo all, Save on a note
// entry) still loads the page; this script notes, for that one load, the
// control that was used and how far it stood from the top of the window,
// and after the load moves the window so that it stands there again, with
// the keyboard on it. Where the control is gone, as Undo is once pressed,
// the nearest part of the page around it stands in. A row's form then asks
// the app to send it to no anchor. What is noted is a place and the names
// of controls, never a word of the consultation. Since run 9c the settings
// page keeps its place the same way, over the load that a save makes
// (15.13, ruling 47): any page marked data-keeps-place.
(function () {
  const page = document.getElementById('review') || document.querySelector('[data-keeps-place]');
  if (!page) return;
  let store;
  try { store = window.sessionStorage; store.getItem('x'); } catch (error) { return; }     // no store: the page comes back as with no script
  const KEY = 'openconsult.place:' + page.dataset.path;
  const FRESH_MS = 15000;      // a note older than this belongs to a load that never came

  // Pure: the first of the noted names that still stands on the page, as its place in the list; -1 when none does.
  function standing(names, there) { return names.findIndex(function (name) { return there(name); }); }

  let noted = null;
  try { noted = JSON.parse(store.getItem(KEY)); } catch (error) { noted = null; }
  store.removeItem(KEY);
  if (noted && Date.now() - noted.at < FRESH_MS) {
    const k = standing(noted.names, function (name) { return document.getElementById(name); });
    if (k >= 0) {
      const found = document.getElementById(noted.names[k]);
      window.scrollBy(0, found.getBoundingClientRect().top - noted.tops[k]);
      if (k > 0) found.setAttribute('tabindex', '-1');      // not the control itself: its place takes the keyboard, so Tab goes on from there
      found.focus({preventScroll: true});
    }
    // The line that says the save was made stands in the window (15.13, ruling 47; mail 6 of run 9c). After the tick
    // of a long statement the form is short again, and with its top where it was the line stood above the window:
    // the choice was saved and the doctor did not see it said. Only then the window moves, and the least that shows
    // the form that was used and the line.
    const said = page.querySelector('.notice[role=status], .where-lines[role=status]');
    if (said && !inWindow(said.getBoundingClientRect(), barBottom(), window.innerHeight)) {
      if (k === 0) document.getElementById(noted.names[0]).scrollIntoView({block: 'nearest'});
      said.scrollIntoView({block: 'nearest'});
    }
  }
  // Pure: whether a box stands whole in the window, under the app's bar.
  function inWindow(box, under, height) { return box.top >= under && box.bottom <= height; }
  function barBottom() { const bar = document.querySelector('header.app'); return bar ? bar.getBoundingClientRect().bottom : 0; }
  page.addEventListener('submit', function (event) {
    const form = event.target;
    if (!form.hasAttribute('data-stay')) return;
    const names = [], tops = [];
    for (let node = event.submitter || form; node && node !== page; node = node.parentElement) {
      if (node.id) { names.push(node.id); tops.push(Math.round(node.getBoundingClientRect().top)); }
    }
    store.setItem(KEY, JSON.stringify({at: Date.now(), names: names, tops: tops}));
    if (!form.querySelector('input[name=place]')) {
      const ask = document.createElement('input');
      ask.type = 'hidden'; ask.name = 'place'; ask.value = 'keep';
      form.appendChild(ask);
    }
  });
})();
