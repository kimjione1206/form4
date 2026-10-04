(function () {
  var el = document.querySelector("[data-typing]");
  if (!el || !window.matchMedia || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  var nodes = [];
  var walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) nodes.push({ node: walker.currentNode, text: walker.currentNode.nodeValue });
  var btn = document.querySelector("[data-replay]");
  var status = document.querySelector("[data-typing-status]");
  var timer;
  // 길이와 상관없이 약 1.2초(1200ms) 안에 끝나도록, 긴 문장은 한 번에 여러 글자씩 쓴다
  var TICK = 24;
  var total = nodes.reduce(function (s, n) { return s + n.text.length; }, 0);
  var step = Math.max(1, Math.ceil(total / (1200 / TICK)));
  function play() {
    clearInterval(timer);
    el.style.minHeight = el.offsetHeight + "px";  // 지우기 전에 지금 높이를 고정해서 상자가 접히지 않게
    nodes.forEach(function (n) { n.node.nodeValue = ""; });
    el.classList.add("is-typing");
    if (btn) btn.hidden = true;
    if (status) status.textContent = "정리 중…";
    var i = 0, j = 0;
    timer = setInterval(function () {
      for (var k = 0; k < step; k++) {
        while (i < nodes.length && j >= nodes[i].text.length) { i++; j = 0; }
        if (i >= nodes.length) break;
        j++;
        nodes[i].node.nodeValue = nodes[i].text.slice(0, j);
      }
      if (i >= nodes.length) {
        clearInterval(timer);
        el.classList.remove("is-typing");
        el.style.minHeight = "";
        if (btn) btn.hidden = false;
        if (status) status.textContent = "자동 정리";
      }
    }, TICK);
  }
  if (btn) btn.addEventListener("click", play);
  play();
})();
