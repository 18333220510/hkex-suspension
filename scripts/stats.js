/* 顶部统计只使用披露易公告日期，按香港时区判断“今日”。 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.SuspensionStats = api;
})(typeof self !== 'undefined' ? self : globalThis, function () {
  function hongKongDate(now) {
    const date = now || new Date();
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: 'Asia/Hong_Kong', year: 'numeric', month: '2-digit', day: '2-digit'
    }).formatToParts(date);
    const values = {};
    parts.forEach(part => { if (part.type !== 'literal') values[part.type] = part.value; });
    return values.year + '-' + values.month + '-' + values.day;
  }

  function countTodayNew(items, now) {
    const today = hongKongDate(now);
    return items.filter(item => item.group === '新增停牌' && item.date === today).length;
  }

  return { hongKongDate, countTodayNew };
});
