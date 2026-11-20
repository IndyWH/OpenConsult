// The Patients page opens at its top, with New patient in the window, and
// the search box has the keyboard, so a doctor can type a name at once
// (the owner's ruling of 20 Nov 2026). At his look of that day the page
// came up moved down to the search box: the box took the keyboard by the
// browser's own attribute, and a browser brings such a field into the
// window when it stands under it. Here the field marked data-keyboard is
// given the keyboard without the page moving. The page staying where it is
// comes first: a browser that moves it all the same is put back. Where
// this script has not run the page stays at its top and the box takes the
// keyboard at a press.
(function () {
  const box = document.querySelector('[data-keyboard]');
  if (!box) return;
  const x = window.scrollX, y = window.scrollY;
  box.focus({preventScroll: true});
  if (window.scrollX !== x || window.scrollY !== y) window.scrollTo(x, y);
})();
