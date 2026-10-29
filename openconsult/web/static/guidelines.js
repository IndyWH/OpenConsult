// The guideline panel of the live page (spec 15.12, ruling 6): renders the
// state the app sends, one of its named states, and nothing is worked out
// here. Each valid [n] mark is a press that opens the passage with its
// source's title and publisher; a mark the app marked invalid stays plain
// text. Text goes in through textContent, never as HTML.
(function () {
  if (!window.panels) return;
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }
  function fill(template, values) {
    return template.replace(/\{(\w+)\}/g, function (_, key) { return values[key] === undefined ? '' : values[key]; });
  }
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

  function showPassage(passage, words) {
    const dialog = document.getElementById('passage-dialog');
    if (!dialog) return;
    clear(dialog);
    dialog.appendChild(el('h3', null, fill(words.GUIDELINE_PASSAGE_TITLE, {n: passage.n})));
    const source = fill(words.GUIDELINE_SOURCE_LINE, {title: passage.title, publisher: passage.publisher});
    dialog.appendChild(el('p', 'source', passage.trail ? source + ' › ' + passage.trail : source));
    dialog.appendChild(el('p', 'passage', passage.text));
    const close = el('button', null, words.CLOSE);
    close.type = 'button';
    close.addEventListener('click', function () { dialog.close(); });
    dialog.appendChild(close);
    if (dialog.showModal) dialog.showModal(); else dialog.setAttribute('open', '');
  }

  function summaryNode(result, words) {
    const p = el('p', 'guideline-summary');
    const byNumber = {};
    (result.passages || []).forEach(function (passage) { byNumber[passage.n] = passage; });
    String(result.summary || '').split(/(\[\d+\])/).forEach(function (piece) {
      const mark = piece.match(/^\[(\d+)\]$/);
      if (!mark) { p.appendChild(document.createTextNode(piece)); return; }
      const n = Number(mark[1]);
      if (result.cited.indexOf(n) === -1 || !byNumber[n]) { p.appendChild(el('span', 'mark-invalid', piece)); return; }
      const button = el('button', 'cite', piece);
      button.type = 'button';
      button.setAttribute('aria-label', fill(words.GUIDELINE_PASSAGE_TITLE, {n: n}));
      button.addEventListener('click', function () { showPassage(byNumber[n], words); });
      p.appendChild(button);
    });
    return p;
  }

  function citedSources(result, words) {
    const seen = {};
    const ul = el('ul', 'cited-sources');
    (result.passages || []).forEach(function (passage) {
      if (!passage.cited) return;
      const line = fill(words.GUIDELINE_SOURCE_LINE, {title: passage.title, publisher: passage.publisher});
      if (seen[line]) return;
      seen[line] = true;
      ul.appendChild(el('li', null, line));
    });
    return ul;
  }

  function render(state, words) {
    const node = document.getElementById('guidelines');
    if (!node) return;
    clear(node);
    const g = state.guidelines;
    if (!g) return;
    if (g.state === 'no_corpus') { node.appendChild(el('p', 'mark', words.GUIDELINE_NO_CORPUS)); return; }
    if (g.state === 'not_installed') { node.appendChild(el('p', 'mark', words.GUIDELINE_NOT_INSTALLED)); return; }
    if (g.state === 'worker_failed') { node.appendChild(el('p', 'failed', fill(words.GUIDELINE_WORKER_FAILED, {reason: g.reason}))); return; }
    if (g.state === 'waiting') { node.appendChild(el('p', 'mark', words.GUIDELINE_WAITING)); }
    if (g.searching) node.appendChild(el('p', 'mark', fill(words.GUIDELINE_SEARCHING, {names: g.searching_text})));
    const result = g.result;
    if (result) {
      if (g.searching) node.appendChild(el('p', 'mark', words.GUIDELINE_FROM_EARLIER));
      node.appendChild(el('p', 'mark', fill(words.GUIDELINE_FOR, {names: result.names_text})));
      if (result.state === 'covered') {
        node.appendChild(summaryNode(result, words));
        node.appendChild(el('h3', 'mark', words.GUIDELINE_CITED));
        node.appendChild(citedSources(result, words));
      } else if (result.state === 'not_covered') {
        node.appendChild(el('p', null, fill(words.GUIDELINE_NOT_COVERED, {names: result.names_text})));
        if (result.model_sentence) node.appendChild(el('p', 'mark', fill(words.GUIDELINE_MODEL_SAID, {sentence: result.model_sentence})));
      } else if (result.state === 'index_model') {
        node.appendChild(el('p', 'failed', words.GUIDELINE_INDEX_MODEL));
      } else {
        node.appendChild(el('p', 'failed', fill(words.GUIDELINE_FAILED, {reason: result.failure})));
      }
    }
    const p = g.provenance || {};
    node.appendChild(el('p', 'mark', fill(words.GUIDELINE_PROVENANCE, {sources: p.sources, passages: p.passages, date: p.date})));
  }

  const base = window.panels.render;
  window.panels.render = function (state, words) { base(state, words); render(state, words); };
})();
