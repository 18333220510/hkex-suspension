const test = require('node:test');
const assert = require('node:assert/strict');
const { hongKongDate, countTodayNew } = require('../scripts/stats.js');

const items = [
  { group: '新增停牌', date: '2026-11-13' },
  { group: '新增停牌', date: '2026-11-13' },
  { group: '新增停牌', date: '2026-11-14' },
  { group: '长期停牌公司进展', date: '2026-11-13' },
  { group: '新增停牌', date: '2026-10-01' }
];

test('香港 23:59:59 仍统计 13 日的两条新增，排除长期进展和历史', () => {
  const now = new Date('2026-11-13T15:59:59Z');
  assert.equal(hongKongDate(now), '2026-11-13');
  assert.equal(countTodayNew(items, now), 2);
});

test('跨过香港午夜后立即重算为 14 日的一条新增', () => {
  const now = new Date('2026-11-13T16:00:00Z');
  assert.equal(hongKongDate(now), '2026-11-14');
  assert.equal(countTodayNew(items, now), 1);
});

test('当日没有新增停牌时显示 0', () => {
  const now = new Date('2026-11-14T16:00:00Z');
  assert.equal(hongKongDate(now), '2026-11-15');
  assert.equal(countTodayNew(items, now), 0);
});

test('空数据安全返回 0', () => {
  assert.equal(countTodayNew([], new Date('2026-11-13T16:00:00Z')), 0);
});
