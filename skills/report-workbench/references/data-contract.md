# 项目台账约定

`report-project.json` 是便于AI和脚本复用的中间格式。业务输入可继续是Excel、CSV、照片、Word或口述；由AI建立映射并维护，不要求用户改用JSON。

## 最小字段

| 类别 | 字段 | 用途 |
|---|---|---|
| 项目 | name、kind、periods、purpose、audience | 明确报告范围；periods可为空，例如非周期技术方案 |
| 模板 | path、sha256、role | 锁定参考版本；role说明版式、结构或方法参考 |
| 来源 sources | id、path、status、note | 原始资料或明确的用户决定；口述决定可记在note并标明决定时间，不伪造文件 |
| 事实 facts | id、key、value、unit、period、source_ids、status | 定量或定性事实的当前值与出处；0和空值不同 |
| 单元 units | id、display_no、period、question、result、result_status、evidence_status、source_ids、asset_ids、target_confirmed | 可对应点位、事件、样品、专题；内部id稳定，显示编号可以变化 |
| 素材 assets | id、path、kind、period、unit_id、capture_date、review_status、target_description | 图片、图表和数据等；unit_id空值代表公共素材 |
| 章节 sections | id、title、period、unit_ids、source_ids、asset_ids、fact_ids、depends_on | 建立修改依赖；depends_on可用all_units、all_assets、all_facts、template |
| 约束 rules | expected_asset_kinds、require_target_confirmation | 按项目启用；不让所有报告都必须有图片或坐标 |

来源、事实和素材的status/review_status可使用confirmed、pending、conflict；单元evidence_status使用verified、pending、insufficient。这些状态必须按证据填写，不因脚本运行自动升级。

`path` 相对项目JSON所在目录解析，也可为本机绝对路径。URL可以登记，但脚本不联网下载；纯口述来源可不设path。单元引用来源不等于来源已经证明全部结论，仍需审查具体内容。

## 依赖示例

```json
{
  "id": "abstract",
  "title": "摘要",
  "period": "2026-01",
  "depends_on": ["all_units", "all_facts"]
}
```

1月单元增删或事实更改会提示复核该摘要；2月单元变化不应触发1月摘要。模板变化会提示检查文档布局。新增或修改图片会触发相连案例与文字复核，即使图像文件名没变。

## 用于非影像报告的示例

技术方案可把units作为备选技术路线、assets作为流程图与试验表，facts保存处理规模、指标与单位，sections保存比较和实施章节；无需启用影像配对和目标圈注。

监测报告可把units作为监测断面或样点，facts保存观测值、统计口径与检测日期，assets保存趋势图或结果表；测量数据不能由照片颜色推断。

## 脚本输出的含义

`check` 的errors表示关联或已声明约束存在结构性问题；warnings表示缺口、待核对或检查边界。即使两者均空，也只表示已登记台账通过这些检查，不能表示来源内容真实、业务结论成立或Word排版已经合格。

`snapshot` 保存台账和已登记本地文件的SHA-256指纹；`plan` 比较新旧快照后列出改动的对象与受影响的章节。没有登记到台账中的素材无法自动追踪。
