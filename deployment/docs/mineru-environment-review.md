# MinerU 环境与高精度 Markdown 转换路径

调查日期：2026-11-02。范围：本机、`research-cluster-xh5`、`papers-research` 的有限只读探测，以及 MinerU 官方仓库、文档和其注册模型文件元数据。未安装依赖、未下载模型、未向外部上传书籍、未发起解析或 Slurm 作业。密钥仅核对非空状态，保留原位。

阶段说明：以上是最初只读调查的范围。用户后续授权既有云解析后，已完成六页小样、三书1,042页与11项用途资料的实际转换；当前结果与文件见 [最终数据交付](../reports/mineru-full-library-delivery.md)。本调查中的自托管资源提议仍是未执行方案，不应当作当前云运行记录。

## 结论

现有生产环境的 MinerU **云配置与分书解析代码可复用**，但本轮没有成功调用证据。当前没有在本机默认 Python、已列 Conda 环境、集群 PATH 和已探测环境中发现可直接调用的本地 MinerU。集群已有 Debian 12 / Apptainer 与 Python 3.12，可作为自托管基础；需新建隔离的 MinerU 环境，不应直接升级 openPASO 的共享环境。

官方当前 PyPI 和仓库主线均为 **4.1.3**。新版本选择 `flash/basic/standard/advanced` 质量层，并用 `mineru-kit parse` 做完整转换；现有 DeepTutor 本地适配器仍执行旧版 `mineru -p ... -o ...`，不能安装 4.1.3 后直接沿用。云端 `/api/v4` 与自托管 4.1 的 `/v1/tasks` 也是两套独立契约。[版本源文件](https://github.com/opendatalab/MinerU/blob/0ef2c20c4a56e68f81a66647f819d924ef2d89ce/mineru/version.py)、[PyPI 元数据](https://pypi.org/pypi/mineru/json)、[迁移指南](https://opendatalab.github.io/MinerU/reference/migration_4/)。

推荐先完成三本书共 6 页的 Standard 试跑与原页对照，再决定全书及 Advanced 的必要性。“高精度”需要通过字体乱码、阅读顺序、表格和练习结构的实际比较确认，不能由解析器名称或成功退出推定。

## 实测环境

| 位置 | 本轮观察 | 可用性边界 |
| --- | --- | --- |
| Windows | PATH 中有 uv、Python、Conda，无 `mineru` / `magic-pdf`；默认 Python 3.14.0；PyMuPDF 1.27.2.2、pypdf 6.10.0 | 默认 Python 未装 MinerU、Torch、Transformers、vLLM、Docling；Anaconda base 与 puma 的包元信息也未发现 MinerU。没有穷举整机所有虚拟环境 |
| 集群登录 | `login04`、用户 `cluster_user`、home `/work/home/cluster_user`；裸机 glibc 2.17 | 不宜在裸机安装当前推理栈；本轮登录节点只运行身份、元信息和调度查询 |
| 集群容器 | `/work/home/cluster_user/opensource/openpaso/containers/python-runtime` 是 Debian 12；现有 `bin/torch-python` 实测 Python 3.12.15、glibc 2.36 | 可复用容器运行基础和 Apptainer 1.3.4；不向已有容器根写安装内容 |
| 集群已有 env | `envs/torch` 的 Torch 2.14.1+cu126、torchvision 0.29.1+cu126；paso/fenics/torch 与系统 anaconda 的包元信息未发现 MinerU | 当前 Torch 数字满足 MinerU 自身 `torch>=2.7,<3`，但未验证 vLLM、驱动、wheel 和实际 GPU 的组合；系统 Transformers 4.32.1 低于 4.1.3 的 Torch extra 要求 `>=5.10.1,<6` |
| 集群缓存/空间 | `~/.cache/huggingface`、`~/.cache/modelscope`、`~/.mineru`、`~/mineru.json`、openpaso/models 均不存在；`/work` 显示剩余约 159G | 仅限列明路径；不把未探测的全盘缓存称为不存在，159G 也不是 MinerU 专属配额 |
| papers-research | Ubuntu 服务机总 RAM 3.6GiB、available 约 1.3GiB；未发现 host MinerU 命令；deeptutor 容器包元信息无 MinerU/Torch | 适合作为已有云调用控制面；不建议承载 Standard/Advanced 本地推理 |

集群当前可见分区：`xhhgnormal` 为 RTX3080（4 GPU/节点），`xhhgnormal01` 为 RTX3090（8 GPU/节点），`xhacnormalb` 为 CPU。账户 `cluster_user`，QOS `user_cluster_user`；本轮 `squeue -u cluster_user` 为空。这些是调度快照，不能证明指定 GPU 当前空闲或所有资源均可分配。3090 显存的实际值及驱动必须在获调度的试跑节点以 `nvidia-smi` 核对。

MinerU 4.1.3 要求 Python `>=3.11,<3.15`，官方建议新环境用 3.12。Standard/Advanced 需要 VLM；Basic 无本地 VLM 要求。官方给高吞吐系统内存规划起点 16GB、NVIDIA 显存起点 8GB，并明确这不是每种输入的保证。上述 32GB/单卡试跑预算是本报告建议，不是已测峰值。[安装说明](https://opendatalab.github.io/MinerU/quick_start/)、[质量层与运行时](https://opendatalab.github.io/MinerU/usage/tiers/)、[依赖原文](https://github.com/opendatalab/MinerU/blob/0ef2c20c4a56e68f81a66647f819d924ef2d89ce/pyproject.toml)。

## 生产云配置和现有适配器

只读位置：`papers-research` → `deeptutor` 容器 → `/app/data/user/settings/document_parsing.json`。

| 字段 | 观察值 |
| --- | --- |
| engines.mineru.mode / api_base_url | `cloud` / `https://mineru.net` |
| api_token | 非空；未输出、未复制 |
| model_version / language | `vlm` / `en` |
| enable_formula / enable_table / is_ocr | 均为 true |
| max_pages_per_part | 180 |
| normalize_tiny_scans | false |
| allow_local_model_download | false |
| local_cli_path | 空 |

`/app/deeptutor/services/parsing/engines/mineru/cloud.py` 的代码已经包含：180 页上限拆分、完成部分的 ZIP checkpoint 复用、图片增加 part 前缀及 Markdown/JSON 路径重写、`content_list` 中嵌套 `page_idx` 加分片起始偏移。剩余 middle/model/layout 等文件以 part 前缀保留，**其内部仍是分片页码**，消费者需要分片 manifest，不能将它们误认成整书统一 JSON。上述是代码阅读结果，未以真实云响应验证。

`local.py` 用 `mineru --version` 探测，并在第 220 行构造 `mineru -p SOURCE -o OUTPUT`；`rag/pipelines/lightrag` 和 `textbook_struct/chapter_rebuild.py` 仍含旧 `content_list` / `pdf_info` 消费逻辑。自托管 4.x 需要新增版本识别及输出适配，或走独立转换后导入，不应将全新共享文档模型直接塞入旧解析器。

## 书籍规模与可追溯输出

来源路径沿用 `quality-knowledge/source-registry.json`，本轮仅打开 PDF 读取页面数、加密状态和文件大小，没有声称完成全书内容审查。

| source_id | 页数 | 字节数 | 180 页云分片 |
| --- | ---: | ---: | --- |
| book.srw2 | 385 | 13,087,836 | 1–180、181–360、361–385 |
| book.awg3 | 430 | 12,545,108 | 1–180、181–360、361–430 |
| book.corpora2 | 227 | 27,277,745 | 1–180、181–227 |
| 合计 | 1,042 | 52,910,689 | 8 片 |

三本均未加密。旧 SRW2 文本有字体字形恢复问题；应重点比较 MinerU 视觉/OCR 输出，不可将现有文本层当正确答案。

4.1 当前输出推荐保存完整 ZIP 或 SDK `ParseResult.save()` 结果：Markdown、Middle JSON、Structured Content 与 images。页索引为零基原 PDF 页码；CLI 选页为一基。Markdown 本身不足以承载全部页码、块和几何信息。知识库交付应同时保留原 PDF、未改写的 MinerU 原始产物、解析版本/质量层/选择页/分片起点，以及从结构化块生成的页码 sidecar；检索块指向 `source_id + pdf_page + block_index`。如果需要页标记，可另生成带 `<!-- source:...; pdf_page:... -->` 的导入 Markdown，不覆盖原产物。[输出契约](https://opendatalab.github.io/MinerU/reference/output_files/)。

## 自托管准备量与 6 页试跑

模型体积来自官方注册表指定仓库的 Hugging Face 文件列表元数据；没有下载权重。仓库主线定位为 `0ef2c20c4a56e68f81a66647f819d924ef2d89ce`。

| 路线 | 新模型下载量（十进制） | 判断 |
| --- | ---: | --- |
| ONNX + llama.cpp Q8 | ONNX 全包 858,220,651 B + 注册的 Q8 GGUF/mmproj 1,240,476,096 B = **2.099GB** | 依赖较少，CPU 可跑；GPU加速和速度仍须在目标节点验证 |
| Torch + vLLM | Torch 全包 894,882,845 B + 原始 VLM 仓库 2,328,028,751 B = **3.223GB** | 更适合高吞吐，但额外 vLLM/CUDA wheel 兼容成本更高 |

这里是整个小模型仓库与选定 VLM 文件的保守规划量；按 tier 实际下载可能只取所需文件。MinerU 自身 wheel 约 3.83MB，但依赖、wheel 缓存和临时文件另计。建议预留 **10–20GB** 作为初始环境空间预算；它是工程预留，不是下载实测。Advanced 复用 Standard 权重，计算量增加，不另下载一套 Advanced 模型。[官方模型注册表](https://github.com/opendatalab/MinerU/blob/0ef2c20c4a56e68f81a66647f819d924ef2d89ce/mineru/model/registry.py)、[模型配置](https://opendatalab.github.io/MinerU/usage/model_source/)、[ONNX 文件元数据](https://huggingface.co/api/models/opendatalab/MinerU-4_models_onnx/tree/main?recursive=true&limit=1000)、[Torch 文件元数据](https://huggingface.co/api/models/opendatalab/MinerU-4_models_torch/tree/main?recursive=true&limit=1000)、[原始 VLM 元数据](https://huggingface.co/api/models/opendatalab/MinerU2.5-Pro-2605-1.2B/tree/main?recursive=true&limit=1000)、[GGUF 元数据](https://huggingface.co/api/models/jinzhenj/MinerU2.5-Pro-2605-1.2B-GGUF/tree/main?recursive=true&limit=1000)。

最短自托管修复是：复用 Debian 容器及 Python 3.12，在主控确定的远端任务根创建独立环境、固定 `mineru==4.1.3`，准备 Standard 模型，执行 `models verify`，然后在 Slurm 内做真实解析。先选 ONNX + llama.cpp 可减少对现有 Torch 的干扰；若 CPU/llama.cpp速度不能接受，再独立评估 vLLM。不要修改 openPASO 的既有 Torch 环境。

建议试页：SRW2 原 PDF 213–214；AWG3 原 PDF 171–172；Corpora2 原 PDF 92–93（每本2页，共6页）。这是基于已有关注页提出的候选，主控可依版式复核调整。使用原 PDF 的 `--pages` 选择可保留源页索引；如仅向集群传6页摘录，必须同时生成 `excerpt_page → original_pdf_page` 映射。

建议第一次试跑申请 `xhhgnormal01`、1 GPU、8 CPU、32GB RAM、30 分钟硬上限，Standard 一次、Advanced 按必要性最多一次；这是 **0.5 GPU·小时** 与 **4 CPU·小时** 的单作业资源上限，非预测用时。模型下载和安装应独立准备，不能消耗试跑时长等待首次大下载。实际费率、排队和 GPU显存尚未核实，不能给人民币成本。当前父任务正在确认自托管或指定云 API 的范围，本报告未启动准备。

完成环境准备后的命令草案（本轮未执行；`$MINERU_HOME`、输入/输出绝对路径由主控任务根替换）：

```bash
export MINERU_MODEL_SMALL_BACKEND=onnx
export MINERU_MODEL_VLM_ENGINE=llama-cpp
export MINERU_MODEL_SOURCE=local
mineru version --json
mineru-kit models verify --tier standard --small-backend onnx --vlm-engine llama-cpp
mineru-kit parse /ABS/srw2.pdf --pages 213-214 --tier standard --format zip -o /ABS/srw2-sample.zip
mineru-kit parse /ABS/awg3.pdf --pages 171-172 --tier standard --format zip -o /ABS/awg3-sample.zip
mineru-kit parse /ABS/corpora2.pdf --pages 92-93 --tier standard --format zip -o /ABS/corpora2-sample.zip
```

安装/下载阶段可用官方 `models download --tier standard --small-backend onnx --vlm-engine llama-cpp --source modelscope`；仅在主控授权准备阶段执行。运行时 `source=local` 用于防止试跑隐式下载。正式命令以所固定版本的 `--help` 校对。[模型命令](https://opendatalab.github.io/MinerU/usage/model_source/)、[解析命令实现](https://github.com/opendatalab/MinerU/blob/0ef2c20c4a56e68f81a66647f819d924ef2d89ce/mineru/kit/commands/parse.py)。

6页验收只需围绕用途检查：每个目标页都有原页映射；字体乱码是否消失；段落、清单、练习题和表格阅读顺序是否保留；图片相对链接是否可打开；关键例句和术语与原页一致；空白页/漏页能解释。Standard 失败的同页再比较 Advanced 或调整 OCR 模式，不盲目把整书全部重跑。

## 全书执行条件与成本口径

自托管在6页验证后，分书执行并保留每书状态、日志、版本、ZIP和页码映射。首书设有限作业预算；以实测的预热时间与有效秒/页外推 `T_full ≈ T_warmup + 1042 × t_page`，另留人工复核和失败页重试时间。当前无吞吐数据，不能承诺“几分钟完成”。跨页表格或章节层级需整书信息时，再明确是否启用后处理；不默认开启外部 LLM。

若用户选择官方云 API，可复用现有180页拆分的8片链路；官方当前单文件限制200MB/200页，账号每天1000页最高优先级，超过后降低优先级。1042页超过该优先级额度42页，并非硬性禁止。API页码语法和4.x本地页码语法不可混用。云配额、token有效性、当次费用、响应归档契约仍待实际调用确认；书籍仅在父任务明确允许的范围上传。[官方云接口](https://mineru.net/apiManage/docs)。

对于未来非PDF文件，4.1支持Office/EPUB/HTML等原生文档路线，这些走Flash/整文档。统一知识库可统一为 Markdown + JSON + assets + provenance 包，但不应强制把本来结构完整的DOCX/HTML先打印PDF再OCR。[原生格式说明](https://opendatalab.github.io/MinerU/usage/quick_usage/)、[SDK](https://opendatalab.github.io/MinerU/usage/sdk_api/)。

## 实际调查命令与未证实项

实际使用过的轻量命令（同一类包元信息探测做过多个环境；敏感配置仅通过字段白名单输出）：

```powershell
Get-Command mineru,magic-pdf,uv,python,conda -ErrorAction SilentlyContinue
conda env list
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 research-cluster-xh5 'hostname; id -un; pwd'
ssh research-cluster-xh5 'module -t avail 2>&1; /public/software/apps/anaconda3/2023.09/bin/conda env list'
ssh research-cluster-xh5 'sinfo -h -o "%P|%a|%l|%D|%c|%m|%G"'
ssh research-cluster-xh5 'sacctmgr -n -P show assoc where user=cluster_user format=Account,Partition,QOS'
ssh research-cluster-xh5 'squeue -u cluster_user -h -o "%i|%j|%T|%P|%b"'
ssh research-cluster-xh5 'getconf GNU_LIBC_VERSION; df -h /work/home/cluster_user'
ssh research-cluster-xh5 '~/opensource/openpaso/bin/torch-python -c "import sys,platform; print(sys.version); print(platform.libc_ver())"'
ssh papers-research 'docker ps --format "{{.Names}}|{{.Image}}"'
ssh papers-research 'free -h'
```

另用 Python stdlib 读取指定环境的 `.dist-info/METADATA`，用 PyMuPDF 读取三本书页数；通过 `docker exec -i deeptutor python -u -` 只读配置白名单和指定解析器源码；HTTP GET 读取 GitHub commit/tree、PyPI 与 Hugging Face 文件元数据。一次过宽的虚拟环境递归枚举在没有结果时中止，随后改为定向目录查询；没有据此做全盘不存在判断。未创建远端目录或持久服务。

尚待证实：MinerU在现有容器中的依赖解析、实际GPU驱动/显存/推理兼容；模型下载网络及速度；6页真实精度和峰值内存；当前云token可用性、费用与额度；4.x原始输出对现有知识库消费者的适配。以上都不影响本轮已确认的环境、配置、旧接口兼容风险和可执行试跑设计。
