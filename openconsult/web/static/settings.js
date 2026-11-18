// A tick or a choice saves by itself (spec 15.13, ruling 47). The owner's
// idea, from the room check of 17 Nov 2026: a doctor ticks, forgets Save,
// and wonders in a consultation why the setting was not applied. A form
// marked data-saves is sent, as it stands and to its own address, when a
// choice or a tick in it changes: an ordinary load, so the app decides
// everything and the page is the same with and without this script.
// A choice that needs a cloud statement comes back with the statement and
// is not saved; the statement's own tick then saves both. So a changed
// choice is never sent with the fields of the statement that stood on the
// page, which belong to another choice, and the statement's tick is sent
// only when it is set. Where this script runs it takes away the Save
// controls of those forms and the line that says it did not run.
(function () {
  const forms = document.querySelectorAll('form[data-saves]');
  forms.forEach(function (form) {
    form.addEventListener('change', function (event) {
      const control = event.target;
      if (!control.matches('input[type=radio], input[type=checkbox]')) return;
      if (control.closest('[data-statement]')) {
        if (!control.checked) return;
      } else {
        form.querySelectorAll('[data-statement] input').forEach(function (field) { field.disabled = true; });
      }
      form.requestSubmit();
    });
    form.querySelectorAll('[data-save]').forEach(function (button) { button.hidden = true; });
  });
  document.querySelectorAll('[data-no-script]').forEach(function (line) { line.remove(); });
})();
