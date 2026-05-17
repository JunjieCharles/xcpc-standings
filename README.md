# XCPC Standings

## 使用说明

本项目汇总 ICPC/CCPC 等 XCPC 赛事终榜，并生成统一 CSV/JSON 与个人、学校 Rating。`main.py` 是统一入口；年份支持完整写法和短写，例如 `2025`、`25`、`25-26`。半年度范围按比赛日期筛选，可写作 `25下半年-26上半年` 或 `25H2-26H1`。

```bash
# 更新比赛列表
python main.py update

# 批量合并榜单，输出到 data/merged/json 和 data/merged/csv
python main.py merge --batch --years 25下半年-26上半年

# 生成个人和学校 Rating，输出到 data/rating/csv 和 data/rating/xlsx
python main.py rating --type all --years 25下半年-26上半年

# 重新生成本说明和下方数据完整性表
python main.py readme
```

常用输出位置：

- 原始缓存：`data/raw/cache`
- 合并榜单：`data/merged/csv`、`data/merged/json`
- PDF 参赛手册：`data/raw/cache/pdf`（作为名单补充源）
- Rating CSV：`data/rating/csv`
- Rating XLSX：`data/rating/xlsx`

特别鸣谢：[xcpcio](https://github.com/xcpcio/xcpcio)、[RankLand](https://rl.algoux.org/collection/official)

## 数据完整性

|Series|Year|Ordinal|Category|Name|Date|XCPCIO|Rankland|PTA|Rank|School|Team|Solved|Penalty|Medal|Problems|Members|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|ICPC|2026|51|Invitational|江西邀请赛|2026/05/17|✅|||✅|✅|✅|✅|✅|✅|✅|✅|
|ICPC|2026|51|Invitational|武汉邀请赛|2026/05/17|✅|||✅|✅|✅|✅|✅|✅|✅|✅|
|ICPC|2026|51|Invitational|西安邀请赛|2026/05/02|✅|✅||✅|✅|✅|✅|✅|✅|✅|✅|
|CCPC|2025|11|Final|总决赛|2026/04/26||✅|✅|✅|✅|✅|✅|✅|✅|✅|✅|
|ICPC|2026|51|Invitational|深圳邀请赛|2026/04/11|✅|✅||✅|✅|✅|✅|✅|✅|✅|✅|
|ICPC|2025|50|Final|ECFinal|2026/02/02|✅|✅||✅|✅|✅|✅|✅|✅|✅|✅|
|ICPC|2025|50|Regional|香港|2025/11/30|✅|✅||✅|✅|✅|✅|✅|✅|✅|✅|
|CCPC|2025|11|Regional|重庆|2025/11/30|✅|✅||✅|✅|✅|✅|✅|✅|✅|✅|
|ICPC|2025|50|Regional|上海|2025/11/23|✅|✅||✅|✅|✅|✅|✅|✅|✅|✅|
|CCPC|2025|11|Regional|郑州|2025/11/23|✅|✅||✅|✅|✅|✅|✅|✅|✅|✅|
|ICPC|2025|50|Regional|沈阳|2025/11/16|✅|✅||✅|✅|✅|✅|✅|✅|✅|✅|
|CCPC|2025|11|Regional|济南|2025/11/16|✅|✅||✅|✅|✅|✅|✅|✅|✅|✅|
|ICPC|2025|50|Regional|南京|2025/11/09|✅|✅||✅|✅|✅|✅|✅|✅|✅|✅|
|CCPC|2025|11|Regional|哈尔滨|2025/11/09|✅|✅||✅|✅|✅|✅|✅|✅|✅|✅|
|ICPC|2025|50|Regional|武汉|2025/11/02|✅|✅||✅|✅|✅|✅|✅|✅|✅|✅|
|ICPC|2025|50|Regional|成都|2025/10/26|✅|✅||✅|✅|✅|✅|✅|✅|✅|✅|
|CCPC|2025|11|Girls|女生赛|2025/10/26||✅|✅|✅|✅|✅|✅|✅|✅|✅|✅|
|CCPC|2025|11|Vocational|高职赛|2025/10/26|||✅|✅|✅|✅|✅|✅|✅|✅|✅|
|ICPC|2025|50|Regional|西安|2025/10/19|✅|✅||✅|✅|✅|✅|✅|✅|✅|✅|
|CCPC|2025|11|Online|网络赛|2025/09/20|||✅|✅|✅|✅|✅|✅|✅|✅|✅|
|ICPC|2025|50|Online|网络赛2|2025/09/14|||✅|✅|✅|✅|✅|✅|✅|✅|✅|
|CCPC|2025|11|Invitational|南昌邀请赛|2025/09/13|✅|✅||✅|✅|✅|✅|✅|✅|✅|✅|
|ICPC|2025|50|Online|网络赛1|2025/09/07|||✅|✅|✅|✅|✅|✅|✅|✅|✅|
