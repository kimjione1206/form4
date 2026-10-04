(function () {
  var el = document.querySelector("[data-typing]");
  if (!el || !window.matchMedia || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  var nodes = [];
  var walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) nodes.push({ node: walker.currentNode, text: walker.currentNode.nodeValue });
  var btn = document.querySelector("[data-replay]");
  var status = document.querySelector("[data-typing-status]");
  var timer;
  function play() {
    clearInterval(timer);
    nodes.forEach(function (n) { n.node.nodeValue = ""; });
    el.classList.add("is-typing");
    if (btn) btn.hidden = true;
    if (status) status.textContent = "정리 중…";
    var i = 0, j = 0;
    timer = setInterval(function () {
      while (i < nodes.length && j >= nodes[i].text.length) { i++; j = 0; }
      if (i >= nodes.length) {
        clearInterval(timer);
        el.classList.remove("is-typing");
        if (btn) btn.hidden = false;
        if (status) status.textContent = "자동 정리";
        return;
      }
      j++;
      nodes[i].node.nodeValue = nodes[i].text.slice(0, j);
    }, 24);
  }
  if (btn) btn.addEventListener("click", play);
  play();
})();
