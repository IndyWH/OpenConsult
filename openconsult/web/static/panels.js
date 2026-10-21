// The live page's panels: a table of handlers, one for each panel, each
// rendering the state the app sends (spec 15.10, The live page; V1_LESSONS
// 5.4). No state is worked out here: what to show, which alarm is current,
// which is earlier, whether a list is kept from an earlier pass, all come
// from the app. Text goes in through textContent, never as HTML.
(function () {
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
  function list(title, items, words, keyOf) {
    const wrap = el('div');
    wrap.appendChild(el('h3', 'mark', title));
    const ul = el('ul', 'panel-list');
    if (!items.length) ul.appendChild(el('li', 'mark', '—'));
    items.forEach(function (item) { ul.appendChild(el('li', null, keyOf(item))); });
    wrap.appendChild(ul);
    return wrap;
  }

  const handlers = {
    transcript: function (state, words) {
      const node = document.getElementById('transcript');
      clear(node);
      const lines = state.transcript.lines;
      if (!lines.length && !state.transcript.partial) node.appendChild(el('p', 'mark', words.WAITING_FOR_WORDS));
      lines.forEach(function (line) {
        const p = el('p', 'line');
        const speaker = line.speaker ? fill(words.SPEAKER_WORD, {n: String(line.speaker).replace(/^S/, '')}) : '';
        p.appendChild(el('span', 'speaker', speaker));
        p.appendChild(document.createTextNode(line.text));
        node.appendChild(p);
      });
      if (state.transcript.partial) node.appendChild(el('p', 'partial', state.transcript.partial));
      node.scrollTop = node.scrollHeight;
    },
    assessment: function (state, words) {
      const node = document.getElementById('assessment');
      clear(node);
      const panel = state.passes.assessment;
      if (state.background) node.appendChild(el('p', 'mark background', words.EARLIER_NOTES_IN_USE));   // 8.5
      if (panel.failure) node.appendChild(el('p', 'failed', fill(words.PASS_FAILED, {reason: panel.failure})));
      if (panel.from_earlier) node.appendChild(el('p', 'mark', words.FROM_EARLIER_PASS));
      if (!panel.n && !panel.failure) { node.appendChild(el('p', 'mark', state.passes.running ? words.PASS_RUNNING : words.LISTENING)); return; }
      node.appendChild(list(words.DIFFERENTIALS, panel.differentials, words, function (d) {
        return d.condition + ' (' + d.likelihood + '): ' + d.rationale; }));
      markRed(node, panel, state.passes.alarm, words);
      node.appendChild(list(words.QUESTIONS, panel.questions, words, function (q) { return q; }));
      node.appendChild(list(words.SIGNS, panel.signs, words, function (s) { return s; }));
    },
    alarm: function (state, words) {
      const node = document.getElementById('alarm');
      clear(node);
      const alarm = state.passes.alarm;
      if (!alarm) { node.appendChild(el('p', 'mark', words.ALARM_NONE)); }
      else node.appendChild(alarmBlock(alarm, words, false));
      if (state.passes.earlier_alarms.length) {
        const earlier = el('div', 'earlier');
        earlier.appendChild(el('h3', 'mark', words.EARLIER_ALARMS));
        state.passes.earlier_alarms.forEach(function (a) { earlier.appendChild(alarmBlock(a, words, true)); });
        node.appendChild(earlier);
      }
      renderAcknowledge(state, words);
    },
    clock: function (state, words) {
      const node = document.getElementById('clock');
      node.dataset.usedAt = String(Date.now());
      node.dataset.used = String(state.used_s);
      tick(words);
    },
    speech: function (state, words) {
      const node = document.getElementById('speech-line');
      const speech = state.speech;
      if (speech.state === 'failed' || speech.failure) node.textContent = fill(words.SPEECH_STOPPED, {reason: speech.reason || speech.failure});
      else if (speech.state === 'starting') node.textContent = words.SPEECH_STARTING;
      else if (speech.state === 'open') node.textContent = words.LISTENING;
      else node.textContent = '';
    },
    spinner: function (state) {
      document.getElementById('spinner').hidden = !state.spinning;
    },
  };

  // The red mark (15.11 ruling 9): the names the app matched are marked and
  // become a press that shows the alarm's reasoning and actions.
  function markRed(node, panel, alarm, words) {
    const marked = panel.marked || [];
    if (!marked.length || !alarm) return;
    node.querySelectorAll('li').forEach(function (li) {
      const name = marked.find(function (m) { return li.textContent.indexOf(m + ' (') === 0; });
      if (!name) return;
      li.classList.add('red');
      const button = el('button', 'red-name', words.ALARM_NAMED);
      button.type = 'button';
      button.addEventListener('click', function () { if (window.alarmDialog) window.alarmDialog.show(alarm.reasoning, alarm.actions, words); });
      li.appendChild(button);
    });
  }

  function alarmBlock(alarm, words, earlier) {
    const block = el('div', earlier ? 'earlier-alarm' : 'current-alarm');
    if (alarm.state === 'fired') {
      block.appendChild(el('p', 'alarm-fired', words.ALARM_FIRED));
      const ul = el('ul', 'panel-list');
      alarm.actions.forEach(function (a) { ul.appendChild(el('li', null, a.action + ': ' + a.reason)); });
      block.appendChild(ul);
    } else if (alarm.state === 'no_action') {
      block.appendChild(el('p', 'alarm-no-action', words.ALARM_NO_ACTION));
    } else if (alarm.state === 'not_judged') {
      block.appendChild(el('p', 'alarm-not-judged', fill(words.ALARM_NOT_JUDGED, {reason: alarm.reason})));
    } else {
      block.appendChild(el('p', 'mark', alarm.arranged ? words.ALARM_ARRANGED : words.ALARM_NONE));
    }
    if (alarm.reasoning && alarm.state !== 'quiet') {
      const details = el('details');
      details.appendChild(el('summary', null, words.SHOW_REASONING));
      details.appendChild(el('p', null, alarm.reasoning));
      block.appendChild(details);
    }
    if (alarm.key && alarm.acknowledged) block.appendChild(el('p', 'acknowledged', words.ACKNOWLEDGED));
    return block;
  }

  function renderAcknowledge(state, words) {
    // The acknowledgement lives in the fixed zone, beside Stop (R15; R29).
    const zone = document.getElementById('acknowledge');
    clear(zone);
    const alarm = state.passes.alarm;
    if (!alarm || !alarm.key || alarm.acknowledged) return;
    const button = el('button', null, words.ACKNOWLEDGE);
    button.type = 'button';
    button.id = 'acknowledge-alarm';
    button.addEventListener('click', function () { if (window.liveSend) window.liveSend({type: 'acknowledge', key: alarm.key}); });
    zone.appendChild(button);
  }

  function tick(words) {
    const node = document.getElementById('clock');
    if (!node || !node.dataset.usedAt) return;
    const used = Number(node.dataset.used) + (Date.now() - Number(node.dataset.usedAt)) / 1000;
    const intended = Number(node.dataset.intended) * 60;
    const over = used >= intended;          // the one compare the page makes (ruling 10)
    node.className = 'clock' + (over ? ' over' : '');
    node.textContent = fill(words.CLOCK_USED, {used: plain(used), intended: plain(intended)}) + (over ? ' ' + words.CLOCK_OVER : '');
  }
  function plain(seconds) {
    const m = Math.floor(seconds / 60), s = Math.floor(seconds % 60);
    return m + ':' + (s < 10 ? '0' : '') + s;
  }

  let clockWords = null;
  setInterval(function () { if (clockWords) tick(clockWords); }, 1000);

  window.panels = {
    render: function (state, words) {
      clockWords = words;
      Object.keys(handlers).forEach(function (name) { handlers[name](state, words); });
    },
  };
})();
