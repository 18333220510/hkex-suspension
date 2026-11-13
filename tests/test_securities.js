const test = require('node:test');
const assert = require('node:assert/strict');
const { entities } = require('../scripts/securities.js');

test('新世界发展多证券：首个主体为主，其余仅作为相关证券', () => {
  const rows = entities({
    stockName: '新世界發展 / NWD (MTN) N2905 / NWD (MTN) N2802',
    stockCode: '00017 / 04526 / 05149'
  });
  assert.deepEqual(rows[0], { name: '新世界發展', code: '00017' });
  assert.equal(rows.length, 3);
  assert.equal(rows.slice(1).length, 2);
  assert.deepEqual(rows[1], { name: 'NWD (MTN) N2905', code: '04526' });
});

test('普通单主体不产生相关证券，也不增加公告计数', () => {
  const rows = entities({ stockName: '茶百道', stockCode: '02555' });
  assert.deepEqual(rows, [{ name: '茶百道', code: '02555' }]);
  assert.equal(rows.slice(1).length, 0);
});

test('数量不一致时保留原始顺序，不发明名称或代码映射', () => {
  const rows = entities({ stockName: '甲公司 / 乙票据', stockCode: '00001' });
  assert.deepEqual(rows, [
    { name: '甲公司', code: '00001' },
    { name: '乙票据', code: '' }
  ]);
});

test('空主体安全返回空数组', () => {
  assert.deepEqual(entities({}), []);
});
