// The alarm's pop-up (spec 15.11 ruling 9): one dialog on the page, filled
// with the reasoning and the actions the app gives. Text goes in through
// textContent, never as HTML. Shared by the live page and the review page.
(function () {
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }
  window.alarmDialog = {
    show: function (reasoning, actions, words) {
      const dialog = document.getElementById('alarm-dialog');
      if (!dialog) return;
      while (dialog.firstChild) dialog.removeChild(dialog.firstChild);
      dialog.appendChild(el('p', 'alarm-fired', words.ALARM_FIRED));
      const ul = el('ul', 'panel-list');
      (actions || []).forEach(function (a) { ul.appendChild(el('li', null, a.action + ': ' + a.reason)); });
      dialog.appendChild(ul);
      if (reasoning) dialog.appendChild(el('p', null, reasoning));
      const close = el('button', null, words.CLOSE);
      close.type = 'button';
      close.addEventListener('click', function () { dialog.close(); });
      dialog.appendChild(close);
      if (dialog.showModal) dialog.showModal(); else dialog.setAttribute('open', '');
    },
  };
})();
