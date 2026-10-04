// 종목 검색: /search.json 을 한 번 받아 브라우저 안에서만 찾는다. 검색어는 어디로도 보내지 않는다.
(function () {
  var NONE = "찾는 회사가 이 사이트에 없어요. 최근 60일 안에 임원·이사 거래 신고가 있는 회사만 있어서, 거래가 없었거나 이름이 다를 수 있어요. 미국 종목 코드(예: AAPL)로도 찾아보세요.";
  var list;
  function load() {
    if (!list) {
      list = fetch("/search.json").then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      });
      list.catch(function () { list = null; });
    }
    return list;
  }
  // 종목 코드가 딱 맞으면 그것만. 아니면 종목 코드 앞부분이 맞는 회사(GOOG → GOOGL) 먼저, 이름에 든 회사를 뒤에, 겹치지 않게.
  function find(entries, q) {
    var hits = entries.filter(function (e) { return e.t.toUpperCase() === q; });
    if (hits.length) return hits;
    var prefix = entries.filter(function (e) { return e.t.toUpperCase().indexOf(q) === 0; });
    var named = entries.filter(function (e) {
      return prefix.indexOf(e) === -1 &&
        (e.n.toUpperCase().indexOf(q) !== -1 || (e.k || "").toUpperCase().indexOf(q) !== -1);
    });
    return prefix.concat(named);
  }
  function message(out, text) {
    var p = document.createElement("p");
    p.textContent = text;
    out.appendChild(p);
  }
  document.querySelectorAll("form[data-search]").forEach(function (form) {
    var input = form.querySelector("input");
    var out = form.querySelector("[data-search-out]");
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var q = input.value.trim().toUpperCase();
      if (!q) return;
      load().then(function (entries) {
        var hits = find(entries, q);
        if (hits.length === 1) {
          location.href = "/c/" + hits[0].s + "/";
          return;
        }
        out.textContent = "";
        out.hidden = false;
        if (!hits.length) return message(out, NONE);
        hits.slice(0, 10).forEach(function (e) {
          var a = document.createElement("a");
          a.href = "/c/" + e.s + "/";
          a.textContent = (e.k ? e.k + " " : "") + e.n + " ";
          var t = document.createElement("span");
          t.className = "mono small dim";
          t.textContent = e.t + (e.q ? " · 조건 충족" : "");
          a.appendChild(t);
          out.appendChild(a);
        });
      }, function () {
        out.textContent = "";
        out.hidden = false;
        message(out, "검색 목록을 불러오지 못했어요. 잠시 뒤 다시 찾아 주세요.");
      });
    });
  });
})();
