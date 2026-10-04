(function () {
  // 첫 화면 목록 정렬: 사람 수(기본, 처음 순서) / 최근 거래 / 금액. 고른 것은 어디에도 저장하지 않는다.
  var bar = document.querySelector("[data-sort-bar]");
  if (!bar) return;
  var items = Array.prototype.slice.call(document.querySelectorAll(".item[data-rank]"));
  var parent = items.length ? items[0].parentNode : null;
  if (!parent) return;
  var buttons = Array.prototype.slice.call(bar.querySelectorAll("[data-sort]"));
  function num(el, key) { return parseFloat(el.getAttribute(key)); }
  var compare = {
    people: function (a, b) { return num(a, "data-rank") - num(b, "data-rank"); },
    last: function (a, b) {
      var x = a.getAttribute("data-last"), y = b.getAttribute("data-last");
      return x < y ? 1 : x > y ? -1 : compare.people(a, b);
    },
    total: function (a, b) { return (num(b, "data-total") - num(a, "data-total")) || compare.people(a, b); }
  };
  function apply(key) {
    items.slice().sort(compare[key]).forEach(function (el, i) {
      parent.appendChild(el);
      var n = el.querySelector(".num");
      if (n) n.textContent = (i < 9 ? "0" : "") + (i + 1);
    });
    buttons.forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-sort") === key)); });
  }
  buttons.forEach(function (b) {
    b.addEventListener("click", function () { apply(b.getAttribute("data-sort")); });
  });
  Array.prototype.forEach.call(document.querySelectorAll("[data-sort-label]"), function (el) { el.hidden = true; });
  bar.hidden = false;
})();
