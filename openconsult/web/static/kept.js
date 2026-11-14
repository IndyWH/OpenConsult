// Words typed into the row of a doubted drug name and not yet ticked (spec
// 15.10 rulings 26 and 28; the plan review of 6d, point 5). Each row is a
// form of its own, so a press on one row's tick loads the page again and
// the words typed into another row would be gone, a corrected drug name
// lost without a word. At a press on a tick the words standing typed in
// the other rows are kept in the browser's own store for this page: never
// in the record, never sent. When the page returns they are put back into
// their fields, each shown open as a box, so that it is seen to be not yet
// ticked. They are dropped when their row is ticked, when the page is
// approved and when the tab closes. With no script the words are lost and
// the row stays not ticked. The app says on the page what the store may do
// (data-kept: open, wait while a check of who spoke runs, drop once the
// page is read-only for good); the two rules below decide the rest.
(function (root) {
  // The state logic, pure: no page and no store is touched in these two.
  // fields: [{mark, value, standing, editable}], as the page holds them.
  function toKeep(fields, pressed) {
    const kept = {};
    fields.forEach(function (f) {
      const typed = String(f.value).trim();
      if (f.editable && String(f.mark) !== String(pressed) && typed !== '' && typed !== f.standing) kept[f.mark] = typed;
    });
    return kept;
  }
  function toPutBack(kept, fields, state) {
    if (state === 'wait') return kept;            // the page is waiting for a check: nothing is put back and nothing dropped
    const back = {};
    if (state !== 'open') return back;            // read-only for good: everything is dropped
    fields.forEach(function (f) {
      if (f.editable && Object.prototype.hasOwnProperty.call(kept, f.mark) && kept[f.mark] !== f.standing) back[f.mark] = kept[f.mark];
    });
    return back;
  }
  root.keptWords = {toKeep: toKeep, toPutBack: toPutBack};

  if (typeof document === 'undefined') return;
  const page = document.getElementById('review');
  if (!page || !page.dataset.kept) return;
  let store;
  try { store = window.sessionStorage; store.getItem('x'); } catch (error) { return; }     // no store: as with no script
  const KEY = 'openconsult.kept-words:' + page.dataset.path;
  function fields() {
    return Array.from(document.querySelectorAll('input.doubted-field')).map(function (node) {
      return {mark: node.dataset.mark, value: node.value, standing: node.defaultValue, editable: !node.readOnly, node: node};
    });
  }
  let kept = {};
  try { kept = JSON.parse(store.getItem(KEY) || '{}') || {}; } catch (error) { kept = {}; }
  const now = fields();
  const back = toPutBack(kept, now, page.dataset.kept);
  if (page.dataset.kept === 'open') {
    now.forEach(function (f) {
      if (Object.prototype.hasOwnProperty.call(back, f.mark)) { f.node.value = back[f.mark]; f.node.classList.add('kept'); }
    });
  }
  if (Object.keys(back).length) store.setItem(KEY, JSON.stringify(back)); else store.removeItem(KEY);
  document.querySelectorAll('form.drug-row-form').forEach(function (form) {
    form.addEventListener('submit', function () {
      const own = form.querySelector('button.tick');
      const pressed = own ? own.id.replace('tick-', '') : '';
      const keep = toKeep(fields(), pressed);
      if (Object.keys(keep).length) store.setItem(KEY, JSON.stringify(keep)); else store.removeItem(KEY);
    });
  });
})(typeof window !== 'undefined' ? window : globalThis);
