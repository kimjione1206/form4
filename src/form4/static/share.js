// 링크 복사: 지금 페이지 주소를 클립보드에 넣는다. 클립보드를 못 쓰는 브라우저에서는 버튼을 숨긴 채 둔다.
(function () {
  var btn = document.querySelector("[data-copy-link]");
  if (!btn || !navigator.clipboard) return;
  var label = btn.textContent, timer;
  btn.hidden = false;
  function show(text) {
    btn.textContent = text;
    clearTimeout(timer);
    timer = setTimeout(function () { btn.textContent = label; }, 2000);
  }
  btn.addEventListener("click", function () {
    navigator.clipboard.writeText(location.href).then(function () {
      show("복사했어요");
    }).catch(function () {
      show("복사하지 못했어요");
    });
  });
})();
