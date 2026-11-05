# 港交所停牌复牌公告查询

一个可搜索的单页静态网站：按关键词（公司名称 / 股票代码）、日期范围、事件类型（停牌 / 复牌）检索港交所停牌、复牌公告，数据来自披露易（HKEXnews），每日自动更新。支持停牌 → 复牌全周期跟踪和 CSV 导出。

## 目录结构

```
index.html                  # 页面（数据与代码分离，日常更新无需改动）
data/announcements.json     # 公告数据（由抓取脚本维护）
scripts/fetch.py            # 披露易抓取脚本
```

## 本地预览

```bash
python3 -m http.server 8000
# 打开 http://localhost:8000
```

## 部署（GitHub Pages）

```bash
git init && git add -A && git commit -m "init"
git remote add origin git@github.com:<你的用户名>/hkex-suspension.git
git push -u origin main
# 仓库 Settings → Pages → Source 选 main 分支根目录
# 访问 https://<你的用户名>.github.io/hkex-suspension/
```

## 每日更新

```bash
python3 scripts/fetch.py            # 抓取今天并合并进 data/announcements.json
git add data/announcements.json && git commit -m "update $(date +%F)" && git push
```

页面加载 `data/announcements.json` 渲染，更新数据不需要改页面代码。

### 抓取脚本说明

- 数据源：披露易标题搜寻 `titleSearchServlet.do`，逐日检索标题含「停牌」「暫停買賣」「復牌」「恢復買賣」的条目。
- 排除「債券及結構性產品」类（牛熊证 / 权证例行停牌），只保留股票公告。
- 可回填历史：`python3 scripts/fetch.py 20261020 20261031`。
- 每条公告自动计算 `eventType`（停牌 / 复牌）和 `attention`（重点关注标签：收购合并、除牌风险、核数师辞任、股权变动），供页面高亮和每日推送使用。

## 页面功能

- 事件类型筛选：全部 / 停牌 / 复牌；关键词与日期范围过滤。
- 周期跟踪视图：同一公司按停牌日期 → 复牌日期配对，显示间隔时长；未复牌的显示已停牌天数。
- 重点关注高亮：涉收购合并、除牌风险、核数师辞任、股权变动的条目橙色标记。
- 导出 CSV：下载当前筛选结果，UTF-8 with BOM（Excel 直接打开），中文表头。

## 数据字段

| 字段 | 含义 |
|---|---|
| id | 公告文件链接（去重键） |
| date / time | 公告日期 / 时间（香港时间） |
| stockName / stockCode | 公司名称 / 股票代码（多只证券以 " / " 分隔） |
| eventType | 事件类型：停牌 / 復牌 |
| nature | 性质细分（停牌 / 短暫停牌 / 暫停買賣 / 復牌 / 恢復買賣） |
| attention | 重点关注标签列表（收购合并 / 除牌风险 / 核数师辞任 / 股权变动），可为空 |
| title | 公告标题 |
| category | 披露易栏目分类 |
| url | 公告原文链接（披露易） |
