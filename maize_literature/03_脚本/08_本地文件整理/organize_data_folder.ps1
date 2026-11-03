param([Parameter(Mandatory=$true)][string]$TargetDirectory)
$ErrorActionPreference = 'Stop'
$targetRoot = [System.IO.Path]::GetFullPath($TargetDirectory).TrimEnd('\')
$rootResolved = (Resolve-Path -LiteralPath $targetRoot).Path.TrimEnd('\')
if ($rootResolved -ne $targetRoot) { throw '目标根目录解析结果不一致，停止移动。' }
function Assert-InRoot([string]$path) {
    $full = [System.IO.Path]::GetFullPath($path)
    if (-not $full.StartsWith($targetRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) { throw "路径超出整理范围：$full" }
    return $full
}
$plan = @(
    @{ From='玉米文献_完整标题摘要_分类前清洗_v1'; To='01_文献清洗与原始材料\玉米文献_完整标题摘要_分类前清洗_v1' },
    @{ From='MaizeGene_Task1_2_无API版'; To='02_规则初筛与文献分类\01_初版无API\MaizeGene_Task1_2_无API版' },
    @{ From='MaizeGene_V1.3_规则复扫与人工核查包'; To='02_规则初筛与文献分类\02_v1.3规则复扫\MaizeGene_V1.3_规则复扫与人工核查包' },
    @{ From='MaizeGene_任务1至3_无API规则初筛_v1.4'; To='02_规则初筛与文献分类\03_v1.4固定主表与初始候选\MaizeGene_任务1至3_无API规则初筛_v1.4' },
    @{ From='MaizeGene_人工复核工作表.xlsx'; To='03_人工复核与批次记录\00_通用复核工作表\MaizeGene_人工复核工作表.xlsx' },
    @{ From='Task3-重点人工核查清单.xlsx'; To='03_人工复核与批次记录\01_Task3重点核查\Task3-重点人工核查清单.xlsx' },
    @{ From='Task3_高风险优先核查_第2批'; To='03_人工复核与批次记录\02_第二批高风险与第二轮60条\Task3_高风险优先核查_第2批' },
    @{ From='MaizeGene_第二轮60条复核表_中译版.xlsx'; To='03_人工复核与批次记录\02_第二批高风险与第二轮60条\MaizeGene_第二轮60条复核表_中译版.xlsx' },
    @{ From='gene_trait_evidence_candidates_v1_1_reviewed.csv'; To='03_人工复核与批次记录\03_已合并人工复核结果\v1.1\gene_trait_evidence_candidates_v1_1_reviewed.csv' },
    @{ From='gene_trait_evidence_candidates_v1_2_reviewed.csv'; To='03_人工复核与批次记录\03_已合并人工复核结果\v1.2\gene_trait_evidence_candidates_v1_2_reviewed.csv' },
    @{ From='独立复测30条_全文核查建议_规则V1.2'; To='03_人工复核与批次记录\04_独立复测30条\独立复测30条_全文核查建议_规则V1.2' },
    @{ From='MaizeGene_候选证据优化_v1.3'; To='04_候选证据优化\v1.3\MaizeGene_候选证据优化_v1.3' },
    @{ From='neo4j_query_table_data_2026-11-2(1).csv'; To='05_参考基因与ID映射来源\Neo4j_2026-11-02_5000基因子集\neo4j_query_table_data_2026-11-2(1).csv' },
    @{ From='delivery_v1_0'; To='06_增量补查与映射标签基线\2026-11-03_v1.0\delivery_v1_0' }
)
$metadataNames = @('00_整理说明.md','00_文件路径对照.csv','00_整理执行记录.json')
foreach ($name in $metadataNames) { if (Test-Path -LiteralPath (Join-Path $targetRoot $name)) { throw "整理说明文件已存在，避免覆盖：$name" } }
# 所有源和目标在任何移动前一次性检查；目录移动只在明确根目录内执行。
$inventory = [System.Collections.Generic.List[object]]::new()
foreach ($item in $plan) {
    $item.Source = Assert-InRoot (Join-Path $targetRoot $item.From)
    $item.Destination = Assert-InRoot (Join-Path $targetRoot $item.To)
    if (-not (Test-Path -LiteralPath $item.Source)) { throw "缺少源项：$($item.Source)" }
    if (Test-Path -LiteralPath $item.Destination) { throw "目标已存在，禁止覆盖：$($item.Destination)" }
    $entry = Get-Item -LiteralPath $item.Source -Force
    $all = @($entry)
    if ($entry.PSIsContainer) { $all += @(Get-ChildItem -LiteralPath $item.Source -Recurse -Force) }
    if (@($all | Where-Object { $_.Attributes -band [System.IO.FileAttributes]::ReparsePoint }).Count -gt 0) { throw "发现链接/重解析点，停止：$($item.Source)" }
    foreach ($file in @($all | Where-Object { -not $_.PSIsContainer })) {
        $destination = if ($entry.PSIsContainer) { $item.Destination + $file.FullName.Substring($item.Source.Length) } else { $item.Destination }
        $destination = Assert-InRoot $destination
        $inventory.Add([PSCustomObject]@{ OriginalPath=$file.FullName; NewPath=$destination; Bytes=$file.Length; SHA256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash })
    }
}
$completed = [System.Collections.Generic.List[object]]::new()
foreach ($item in $plan) {
    $parent = Split-Path -Parent $item.Destination
    $null = Assert-InRoot $parent
    if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent | Out-Null }
    Move-Item -LiteralPath $item.Source -Destination $item.Destination
    $completed.Add([PSCustomObject]@{From=$item.Source;To=$item.Destination})
    Write-Output "已归档：$($item.From)"
}
$verified = 0
foreach ($file in $inventory) {
    $actual = Get-Item -LiteralPath $file.NewPath
    if ($actual.Length -ne $file.Bytes -or (Get-FileHash -LiteralPath $file.NewPath -Algorithm SHA256).Hash -ne $file.SHA256) { throw "移动后文件校验失败：$($file.NewPath)" }
    if (Test-Path -LiteralPath $file.OriginalPath) { throw "原路径仍存在：$($file.OriginalPath)" }
    $verified++
}
$inventory | Export-Csv -LiteralPath (Join-Path $targetRoot '00_文件路径对照.csv') -NoTypeInformation -Encoding UTF8
$notes = @'
# MAIZEGENE 文件归档说明

整理日期：2026-11-03。按处理内容、版本和批次归档，所有原文件名、内容及已有成果文件夹内部结构保留。没有删除或合并重复文件。

| 分类 | 内容 |
|---|---|
| 01_文献清洗与原始材料 | 分类前清洗v1、原始材料、主要数据及复现材料 |
| 02_规则初筛与文献分类 | 初版无API、v1.3规则复扫、v1.4固定主表与初始候选 |
| 03_人工复核与批次记录 | 通用工作表、Task3重点核查、第二批/第二轮60条、v1.1与v1.2人工合并结果、独立复测30条 |
| 04_候选证据优化 | 候选证据优化v1.3，含329条优先候选及分组结果 |
| 05_参考基因与ID映射来源 | 2026-11-02 Neo4j导出；仅5000基因子集 |
| 06_增量补查与映射标签基线 | 2026-11-03接续交付delivery_v1_0；含七主文件、脚本、报告及原缓存 |

## 使用提示

- 最新接续成果入口：`06_增量补查与映射标签基线/2026-11-03_v1.0/delivery_v1_0/quality_report.md`。
- 固定主表和分类来源在02类的v1.4批次；人工合并源表在03类的v1.2目录。
- 两个同名“MaizeGene_人工复核工作表.xlsx”分别作为原批次材料和根目录通用工作表保留，未推定相同或去重。
- 无扩展名的“Task3_高风险优先核查_第2批”原样保留；内容为制表符分隔的人工核查记录。没有修改格式或补扩展名。
- 第二批高风险和第二轮60条按原名称放入同一批次类别，不推定两者逐行对应。
- 历史配置、报告及脚本中的旧绝对路径属于原始运行记录，不做内容替换。后续复现请依据`00_文件路径对照.csv`定位新路径；调用脚本时传入新的输入路径。
- 原pipeline的--source自动定位依赖旧的平铺目录布局，整理后不能直接把本根目录作为--source重跑；应先依据路径对照准备所需输入目录，或另行适配路径配置。此次只整理文件，没有重跑分析。
- `00_文件路径对照.csv`逐文件列出原路径、新路径、字节数和SHA256；`00_整理执行记录.json`记录顶层移动和校验结果，可用于反向恢复路径。
'@
$notes | Set-Content -LiteralPath (Join-Path $targetRoot '00_整理说明.md') -Encoding UTF8
$record = [PSCustomObject]@{ Root=$targetRoot; Date='2026-11-03'; MovedTopLevelItems=$completed.Count; VerifiedFiles=$verified; TotalBytes=($inventory | Measure-Object Bytes -Sum).Sum; SHA256Verification='all_passed'; Moves=$completed }
$record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $targetRoot '00_整理执行记录.json') -Encoding UTF8
$record | Select-Object Root,MovedTopLevelItems,VerifiedFiles,TotalBytes,SHA256Verification | ConvertTo-Json
