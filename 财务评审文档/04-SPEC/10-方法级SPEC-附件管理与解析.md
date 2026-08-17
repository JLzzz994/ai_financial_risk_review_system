# 附件管理与解析模块——方法级 SPEC

> 状态：已生成，待用户审核
>
> 【重点审核】上传安全校验、对象键、病毒扫描、解析重试、证据结构和删除边界。

## 1. 方法清单

| 方法 | 文件 | 职责 |
|---|---|---|
| `upload_attachment` | `app/services/attachment_service.py` | 校验并保存附件 |
| `validate_file` | `engines/security/file_validator.py` | 类型、大小、文件头和文件名校验 |
| `scan_virus` | `engines/security/virus_scanner.py` | 病毒扫描 |
| `build_storage_key` | `engines/storage/file_storage.py` | 生成安全对象键 |
| `download_attachment` / `preview_attachment` | `app/services/attachment_service.py` | 权限校验并生成短期 URL |
| `delete_attachment` | `app/services/attachment_service.py` | 校验版本状态后删除 |
| `parse_attachment_task` | `workers/attachment_tasks.py` | 解析、OCR、字段抽取和证据定位 |
| `retry_parse` | `app/services/attachment_service.py` | 幂等重试失败解析 |

## 2. `upload_attachment`

1. 校验当前用户对目标单据版本拥有编辑权限；
2. 校验版本处于 `draft`、`withdrawn` 或 `returned`，已提交版本禁止新增附件；
3. 校验文件大小、扩展名、MIME、文件头和附件矩阵；
4. 写入临时对象并计算 SHA-256；
5. 病毒扫描通过后原子转正对象；失败或超时删除临时对象并返回错误；
6. 相同 `document_version_id + file_hash` 返回已有附件；
7. 写入 `document_attachments`，状态 `stored/pending`，投递 Celery 解析任务；任务只传 `attachment_id`、`document_version_id` 和 `idempotency_key`；
8. 返回附件 ID、状态和解析任务 ID。

## 3. 对象键与访问

对象键格式建议：

```text
documents/{document_id}/versions/{document_version_id}/attachments/{attachment_id}/{safe_filename}
```

真实对象键只保存在数据库和存储服务内部；接口只返回附件 ID 或短期预签名 URL。预签名 URL 建议有效期 5 分钟，下载前后均记录审计。

## 4. `parse_attachment_task`

```text
queued → running
  ├─ parse text/layout
  ├─ OCR if needed
  ├─ extract structured fields
  └─ locate evidence
→ succeeded / failed / manual_review
```

每个阶段使用 `attachment_id + parser_version + idempotency_key` 幂等。Celery 任务只传 ID 和幂等键，由任务运行时通过 `FileStorage` 读取对象；结果必须包含：

```json
{
  "page": 1,
  "bbox": [10, 20, 300, 80],
  "raw_snippet": "报销金额：1,200.00",
  "field_path": "expense_items[0].amount",
  "confidence": 0.96
}
```

解析结果写入新记录或新版本，不覆盖历史结果；置信度不足或证据定位失败进入 `manual_review`。

## 5. `delete_attachment`

- 只允许申请人删除 `draft`、`withdrawn` 或 `returned` 版本附件；
- 已提交版本附件不可删除，只能通过新版本替换；
- 删除先写 `deleted` 状态和审计，再异步删除对象；
- 对象删除失败保留元数据和错误，支持后台重试；
- 重复删除幂等成功，不删除历史版本附件。

## 6. 测试用例

- 扩展名、MIME、文件头不一致时拒绝。
- 超过 20 MB 单文件或 200 MB 版本总量时拒绝。
- 病毒扫描命中、失败和超时均不能进入解析。
- 本地存储和 MinIO 存储通过同一契约测试。
- 相同版本相同哈希上传不重复创建附件或任务。
- 非编辑状态不能上传/删除附件，越权下载返回 403。
- 解析、OCR、病毒扫描按阶段记录状态、重试和错误；失败按重试策略恢复，超过上限进入 `manual_review`。
- 证据包含页码、坐标、原文、字段路径和置信度。
- 删除对象失败可重试，历史版本附件仍可读取。
