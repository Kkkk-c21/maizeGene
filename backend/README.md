# MaizeGene 基因详情查询

在项目根目录 `D:\cyq\maizeGene` 启动：

```powershell
cd D:\cyq\maizeGene
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

已有服务运行时直接打开 <http://127.0.0.1:8000/docs>，无需重复启动。
展开 `GET /genes/{gene_id}` → Try it out → 输入 `Zm00001eb081920` → Execute。

直接请求：

```http
GET http://127.0.0.1:8000/genes/Zm00001eb081920
```

响应包含 `gene`、`go`、`protein_domains`、`transcripts` 和 `counts`。
关联项保留数据库节点属性，以及 `relationship.type` 和 `relationship.properties` 中的来源属性。
数组按关联 ID 排序；完全相同的节点和关系属性组合去重，具有不同来源属性的关联保留。
`counts` 是三个返回数组的长度。未找到基因返回 404；非法 ID 返回 422；数据库连接或凭据异常返回 503。
已存在的基因如果没有相应关联，返回 200 和空数组。

健康检查：<http://127.0.0.1:8000/health>，成功返回 `{"status":"ok","neo4j":"connected"}`。
原有 `GET /` 和 `POST /search` 路径保留。详情查询不调用 Embedding 服务、不加载向量文件。
`/search` 仍需要本地向量文件和 Embedding 服务，本次未验收语义搜索。

## 连接配置

后端自动读取项目根目录 `.env`，不覆盖已经设置的进程环境变量。
使用现有 `NEO4J_AUTH=用户名/密码`，无需重新输入或修改密码。

| 配置 | 默认值 / 用途 |
| --- | --- |
| `NEO4J_URI` | `bolt://127.0.0.1:7688` |
| `NEO4J_DATABASE` | `neo4j` |
| `NEO4J_AUTH` | 项目现有本地凭据，无默认密码 |
| `NEO4J_USER` / `NEO4J_PASSWORD` | 可分别覆盖用户名和密码 |

Neo4j Browser：<http://127.0.0.1:7475/browser/>。
本次 API 通过 Bolt 7688 执行参数化只读查询；没有导入、更新或删除图数据。

## 环境恢复

当前项目环境使用 Python 3.12.7，由 `D:\anaconda\python.exe` 创建，并复用其现有依赖；Neo4j 驱动安装在项目 `.venv` 内。
环境已配置完成，正常启动不需要重复安装。
如需重建：

```powershell
cd D:\cyq\maizeGene
& D:\anaconda\python.exe -m venv --system-site-packages .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

新机器可用 Python 3.12 创建普通虚拟环境后安装相同依赖。
当前查询语法面向项目实际使用的 Neo4j 5.26。

## 演示边界

当前只验收基因 ID 详情 API。前端搜索框接入与展示仍待同学对接，本次未切换分支或修改前端。
返回的 GO/结构域是现有数据库注释；关系中的 `evidence_id` 仅为原始引用字段，本次没有查询 Evidence 节点或文献，也未核实实验依据。
