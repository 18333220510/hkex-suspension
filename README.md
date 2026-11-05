# 港交所停牌公告查询

一个可搜索的单页静态网站：按关键词（公司名称 / 股票代码）和日期范围检索港交所停牌、暂停买卖公告，数据来自披露易（HKEXnews），每日自动更新。

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

- 数据源：披露易标题搜寻 `titleSearchServlet.do`，逐日检索标题含「停牌」「暫停買賣」的条目。
- 排除「債券及結構性產品」类（牛熊证 / 权证例行停牌），只保留股票公告。
- 可回填历史：`python3 scripts/fetch.py 20261020 20261031`。

## 数据字段

| 字段 | 含义 |
|---|---|
| id | 公告文件链接（去重键） |
| date / time | 公告日期 / 时间（香港时间） |
| stockName / stockCode | 公司名称 / 股票代码 |
| nature | 停牌性质（停牌 / 短暫停牌 / 暫停買賣） |
| title | 公告标题 |
| category | 披露易栏目分类 |
| url | 公告原文链接（披露易） |
