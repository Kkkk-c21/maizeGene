# 玉米文献项目文件与审计记录

日期：2026-10-28

## 当前文件

目录：`D:\cyq\maizeGene\maize_literature`

当前共有 18 个文件，无子目录：

- 原始数据与状态：`maize_papers.csv`、`maize_checkpoint.json`
- 采集和审计脚本：`collect_maize.py`、`audit_csv.py`、`audit_duplicates.py`、`classify_duplicates.py`、`inspect_record_id_duplicate.py`、`audit_source_record_id.py`
- 抽样脚本：`make_screening_sample.py`、`prelabel_screening_sample.py`
- CSV 抽样输出：`screening_sample_500.csv`、`screening_sample_500_prelabelled.csv`、`screening_review_first30.csv`
- Excel 复核输出：`玉米文献30篇_联网核查版.xlsx`、`玉米文献30篇_学校全文复核版.xlsx`、`玉米文献6篇_功能实验优先候选.xlsx`、`玉米文献36篇_复核汇总与证据示范.xlsx`、`玉米文献36篇_S0450-v5映射版.xlsx`

目录中没有 `.log` 或其他采集日志文件。`maize_checkpoint.json` 只保存查询、游标和 `complete: true`，不能证明每页下载日志。先前提到的 228,695 个 database matches 目前只能追溯到聊天总结，无法由本地日志复核。

## 脚本路径状态

- `collect_maize.py`、`make_screening_sample.py`、`prelabel_screening_sample.py` 指向当前项目目录或脚本所在目录。
- 5 个早期审计脚本仍硬编码旧路径 `D:\cyq\maize_literature\maize_papers.csv`：`audit_csv.py`、`audit_duplicates.py`、`classify_duplicates.py`、`inspect_record_id_duplicate.py`、`audit_source_record_id.py`。它们不能原样用于当前目录。

## 原始 CSV 复核

- 文件：`maize_papers.csv`
- 大小：355,575,451 字节
- SHA-256：`a2ffcc8bf2f575fb369d6fdd4f47adac2fbbcaa31d6e70de8ef47a0a639303aa`
- 字段：`doi,title,abstract,pmid,year,source,record_id,retrieved_at`
- 数据记录：225,007
- 字段错位、额外字段或解析损坏：0
- 采集日期：2026-10-27 为 220,698 条；2026-10-26 为 4,309 条
- 缺 DOI：21,975；缺标题：792；缺摘要：15,985；缺 PMID：35,261；缺年份：255
- 年份范围：1781–2027；2027 年 17 条；非空非法年份 0
- 来源：MED 189,746；AGR 20,760；PAT 4,738；PPR 4,206；PMC 2,981；CBA 2,127；ETH 436；CTX 13
- DOI 标准化后重复：0；PMID 重复：0
- `(source, record_id)` 重复：0
- 单独 `record_id` 有 1 个冲突：`599095`，分别来自 CBA 和 MED
- 标准化标题候选重复：1,661 组，涉及 2,416 条候选多余记录；不能据此自动删除
- 编码替代字符：2 条摘要、共 3 个字符

### HTML 与尖括号计数说明

- 标题中严格格式标签（`i/b/em/italic/sub/sup`）：6,467 条。
- 标题中宽松 `<...>` 模式：6,468 条；多出的 1 条是 `<-->`。
- 摘要中严格格式标签：3 条。
- 摘要中宽松 `<...>` 模式：16 条，其中多条是跨越统计学比较符号的误匹配。
- 摘要中任意 `<` 或 `>`：16,384 条，主要是 `p < 0.05` 等正常比较符号。
- 因此，先前“摘要 1,184 条含 HTML 标签”的口头数字不能由当前文件和现有脚本复现，v1 清洗只移除严格识别的格式标签。

## 抽样与复核证据

### 500 条抽样

`make_screening_sample.py` 使用随机种子 `20261027`，先统计分层规模，再按层规模平方根倒数加权抽取 500 条。

- 来源：MED 289、AGR 94、PAT 36、PMC 28、CBA 23、PPR 19、ETH 11
- 年代：2020+ 138、2010–2019 108、2000–2009 107、1990–1999 75、1990 前 69、年份未知 3
- 有摘要 420、无摘要 80
- 500 条 `sample_id` 和 `source_record_key` 均无重复
- 人工标注字段在 `screening_sample_500.csv` 和 `screening_sample_500_prelabelled.csv` 中均为空

电脑预标分布：U 366、A 53、X 43、B 25、C 8、E 3、R 1、D 1。该分布不是人工真值。

### 首轮 30 条与定向 6 条

- `screening_review_first30.csv` 有 30 条，人工字段为空；电脑建议为 U 8、X 5、C 4、B 4、A 4、E 3、R 1、D 1。
- Excel 中的 30 条复核结果为 X 20、C 3、U 3、E 2、R 1、D 1。
- 另从剩余 470 条中定向选 6 条功能实验候选，人工标签为 A 5、B 1。该批不是随机样本。
- 36 条汇总人工标签为 X 20、A 5、C 3、U 3、E 2、R 1、D 1、B 1。
- 工作簿明确写明：30 条是校准样本，6 条是定向候选；均不能用于估计全库相关率或模型准确率，U 也不能当负例。

### S0450

- 一篇论文拆为 3 条证据，均标为“AI据正文提取，待复核”。
- 候选 B73 v5 基因模型为 `Zm00001eb220940`，来自共线性关联，仍为候选。
- 补充图未独立核图，3 条证据不能作为已完成的人工真值。

## 清洗边界

本次只执行保守、结构性清洗，不删除记录，不做相关性筛选，不自动去重。详细规则见 `cleaning_rules_v1.md`。

