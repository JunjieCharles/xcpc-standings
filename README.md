# ICPC/CCPC 区域赛终榜汇总

## 使用说明

本项目使用 `main.py` 作为统一入口，提供以下命令行功能：

- **更新比赛列表数据**
  ```bash
  python main.py update
  ```
- **合并比赛榜单并生成 CSV** (支持批量处理特定年份)
  ```bash
  python main.py merge --batch --years 2025
  # 处理多范围或全量： python main.py merge --batch --years 2021-2025 
  # （也可设为 all 获取全部年份）
  ```
- **生成/更迭 Rating 双榜单**
  ```bash
  python main.py rating --type all  # --type 选项：member, school, all
  ```
- **更新 README 状态**
  ```bash
  python main.py readme
  ```

- 原始文件在 `data/raw/cache` 文件夹下，解析并合并后的文件在 `data/merged/csv` 文件夹下
- 特别鸣谢：[xcpcio](https://github.com/xcpcio/xcpcio)、[RankLand](https://rl.algoux.org/collection/official)

## 数据完整性

|Series|Year|Ordinal|Category|Name|Date|XCPCIO|Rankland|PTA|Rank|School|Team|Solved|Penalty|Medal|Problems|Members|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|CCPC|2025|11|Final|总决赛|2026/04/26||✅|✅|✅|✅|✅|✅|✅|✅|✅|✅|
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
|ICPC|2025|50|Regional|西安|2025/10/19|✅|✅||✅|✅|✅|✅|✅|✅|✅|✅|
|CCPC|2025|11|Online|网络赛|2025/09/20|||✅|✅|✅|✅|✅|✅|✅|✅|✅|
|ICPC|2025|50|Online|online2|2025/09/14|||✅|✅|✅|✅|✅|✅|✅|✅|✅|
|ICPC|2025|50|Online|online1|2025/09/07|||✅|✅|✅|✅|✅|✅|✅|✅|✅|
