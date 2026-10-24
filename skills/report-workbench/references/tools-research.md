# 工具调研与选择

核对日期：2026-10-23。以下为官方资料所述能力及本项目的选择判断，不表示已经安装或完成性能对比。没有编造效率提升比例。

| 项目 | 官方能力及来源 | 本工作台的使用判断 |
|---|---|---|
| python-docx | 创建和更新DOCX，支持段落、表格、图片、样式及节。[官方文档](https://python-docx.readthedocs.io/en/latest/) | 继续用于现有Word模板定点修改。复杂字段、未公开XML行为及保真必须另检；不把库输出当作已渲染验收。 |
| docxtpl | 在Word模板中使用Jinja标签、循环、条件和内嵌图片；标签受Word run及段落结构限制。[官方文档](https://docxtpl.readthedocs.io/en/stable/) | 对长期固定版式值得作为后续适配器；比硬编码段落索引便于维护。需要先把模板适当标记并试验，不能承诺自动解决目录和分节页码。当前未安装、未接入。 |
| Quarto | 从文稿生成Word，支持目录、章节编号及其他输出格式。[Word输出文档](https://quarto.org/docs/output-formats/ms-word.html) | 适合未来以数据分析和图表为主、允许统一版式的新报告。对本次复杂现成模板，优先现有Word修改路线。 |
| Pandoc | 支持多种文本/文档转换；reference-docx使用其样式和文档属性，忽略参考文件正文。[用户手册](https://pandoc.org/MANUAL.html#option--reference-doc) | 可作转换工具，不能把它当成完整复制既有Word封面、表格及正文结构的方案。 |
| Docling | 将PDF、DOCX等解析到统一结构，可导出Markdown或JSON等。[支持格式](https://docling-project.github.io/docling/usage/supported_formats/) | 大量异构资料或扫描件时再考虑；解析结果仍要核对。当前资料规模不需要为此引入模型、下载权重或服务。 |

## 当前实现的组合

通用skill负责任务要求、证据、章节与修改依赖；项目规则负责业务词表、判读口径与呈现要求；标准库脚本负责关联和变更检查；文档、PDF、表格技能负责相应文件制作与渲染。

先稳定数据和证据映射，再完善可重复的Word组件；有多份真实任务证明固定槽位值得维护后，才选择docxtpl等模板适配器。调研本身不启动安装、联网服务、上传资料或采购。
