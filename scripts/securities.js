/* 将披露易按 " / " 分隔的主体与代码按原顺序配对，不猜测主体映射。 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.SecurityDisplay = api;
})(typeof self !== 'undefined' ? self : globalThis, function () {
  function split(value) {
    return String(value || '').split(' / ').map(s => s.trim()).filter(Boolean);
  }

  function entities(item) {
    const names = split(item && item.stockName);
    const codes = split(item && item.stockCode);
    const count = Math.max(names.length, codes.length);
    return Array.from({ length: count }, (_, index) => ({
      name: names[index] || '',
      code: codes[index] || ''
    }));
  }

  return { entities };
});
