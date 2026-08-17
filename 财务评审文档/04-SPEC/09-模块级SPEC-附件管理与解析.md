# 附件管理与解析模块——模块级 SPEC

> 状态：已生成，待用户审核
>
> 范围：附件上传、预览、下载、删除、格式/大小校验、病毒扫描、FileStorage、解析/OCR 和证据定位。
>
> 【重点审核】存储实现、文件安全策略、附件删除边界、解析状态和证据绑定。

## 1. 模块目标与边界

本模块负责附件元数据和解析流水线，不负责风险规则判定、审批决定和报告内容。业务模块只依赖 `FileStorage` 接口；开发环境使用本地文件存储，生产环境使用 MinIO。数据库只保存 `object_key` 和必要的脱敏 metadata，不保存文件绝对路径或存储 SDK 对象。

包含：

- 上传、列表、下载、预览和删除附件；
- 文件类型、大小、扩展名和内容探测；
- 病毒扫描、哈希去重和对象存储元数据；
- PDF/图片/OFD 等附件解析、OCR、字段抽取和证据位置；
- 解析任务状态、重试、失败和人工接管；
- 按用户数据权限控制附件访问。

不包含：确定性风险规则、综合风险等级、审批状态变更和最终报告固化。

## 2. 数据结构

复用 `document_attachments`、`attachment_parse_results`、`invoice_records`、`analysis_tasks`：

| 对象 | 状态/关键字段 | 约束 |
|---|---|---|
| 附件 | `document_version_id`、`object_key`、`metadata_json`、`file_hash`、`storage_status`、`parse_status` | 必须绑定不可变版本；对象键不暴露真实路径，metadata 不保存敏感原文 |
| 解析结果 | `attachment_id`、`raw_text`、`structured_json`、`evidence_json`、`parser_version` | 结果不可覆盖历史版本 |
| 解析任务 | `stage`、`task_status`、`retry_count`、`idempotency_key`、`error_code` | 按阶段重试、可恢复 |
| 发票记录 | 发票号码、金额、日期、税额、字段证据 | 绑定版本和附件 |

状态全部使用小写：

- `storage_status`：`uploading`、`stored`、`failed`、`deleted`；
- `parse_status`：`pending`、`parsing`、`succeeded`、`failed`、`manual_review`；
- 任务状态：`queued`、`running`、`succeeded`、`failed`、`cancelled`。

## 3. FileStorage 接口

```python
class FileStorage(Protocol):
    async def put(self, stream: BinaryIO, key: str, content_type: str) -> StoredObject: ...
    async def get(self, key: str) -> AsyncIterator[bytes]: ...
    async def delete(self, key: str) -> None: ...
    async def exists(self, key: str) -> bool: ...
    async def presign_get(self, key: str, expires_seconds: int) -> str: ...
```

实现：

- `LocalFileStorage`：开发/测试使用 `var/uploads`，只允许应用生成的对象键；
- `MinioFileStorage`：生产使用 MinIO Bucket、服务端加密和短期预签名 URL；
- 业务代码不得直接调用本地文件 API 或 MinIO SDK；HTTP 外部依赖统一通过 `httpx` Provider/适配器访问。

## 4. 业务流程

1. 申请人上传文件，接口校验登录、版本权限、扩展名、MIME、大小和文件名。
2. 文件流写入临时对象，计算 SHA-256，执行内容探测和病毒扫描。
3. 扫描通过后转为正式对象，写入附件元数据，状态为 `stored`、解析状态为 `pending`。
4. 同版本相同哈希附件返回已有附件，不重复存储或解析。
5. Celery 依次执行解析、OCR、字段抽取和证据定位；任务只传 `attachment_id`、`document_version_id` 和 `idempotency_key`，每一步记录阶段状态、重试次数和错误。
6. 解析结果绑定 `attachment_id` 和 `document_version_id`；页码、坐标、原文片段和置信度写入证据结构。
7. 解析不可恢复失败时进入 `manual_review`，不自动生成确定性风险结论。
8. 下载和预览生成短期授权 URL，服务端先执行数据权限校验。
9. 已进入不可变版本的附件默认不可删除；草稿或退回版本允许申请人删除并记录审计。

## 5. 文件安全策略

- 允许类型由单据类型、金额区间和费用类别匹配的附件矩阵配置；没有更具体规则时使用单据类型默认规则；扩展名、MIME 和文件头必须同时匹配；
- 默认单文件最大 20 MB，单版本附件总量最大 200 MB；
- 文件名只作为展示字段，存储键由系统生成并进行路径穿越防护；
- 上传后必须病毒扫描，扫描失败或超时进入 `failed`，不得进入解析；
- 下载使用一次性或短期预签名 URL，不返回永久对象地址；
- 日志不记录完整路径、对象键原文、附件内容或敏感字段。

## 6. 核心代码文件

```text
app/
├── routers/attachments.py
├── schemas/attachments.py
├── services/attachment_service.py
└── exceptions/attachment.py
engines/
├── storage/file_storage.py
├── storage/local_file_storage.py
├── storage/minio_file_storage.py
├── parsing/parser_router.py
├── parsing/ocr_adapter.py
├── parsing/evidence_locator.py
└── security/virus_scanner.py
workers/
└── attachment_tasks.py
front/src/
├── components/attachment-uploader.vue
├── components/attachment-preview.vue
└── api/attachments.ts
test/
├── app/attachments/test_attachment_router.py
├── engines/storage/test_file_storage.py
└── workers/test_attachment_tasks.py
```

## 7. 接口范围

| 方法 | 路径 | 权限 | 用途 |
|---|---|---|---|
| `GET` | `/api/v1/documents/{document_id}/attachments` | 数据范围 | 查询附件列表 |
| `POST` | `/api/v1/documents/{document_id}/attachments` | 申请人/授权编辑人 | 上传附件 |
| `GET` | `/api/v1/attachments/{attachment_id}/download` | 数据范围 | 下载附件 |
| `GET` | `/api/v1/attachments/{attachment_id}/preview` | 数据范围 | 预览附件 |
| `DELETE` | `/api/v1/attachments/{attachment_id}` | 申请人/授权编辑人 | 删除草稿或退回版本附件 |
| `POST` | `/api/v1/attachments/{attachment_id}/parse` | 数据范围 | 重试或人工触发解析 |
| `GET` | `/api/v1/attachments/{attachment_id}/parse-status` | 数据范围 | 查询解析状态和错误 |

为兼容《财务风险评审项目说明.md》的资源嵌套路由，以下路径作为同一 Service 的兼容入口：`POST /api/v1/documents/{document_id}/attachments/{attachment_id}/parse`、`GET /api/v1/documents/{document_id}/attachments/{attachment_id}`、`DELETE /api/v1/documents/{document_id}/attachments/{attachment_id}`。两套路径不得产生不同业务逻辑。

## 8. 验收标准

- [ ] 本地 FileStorage 和 MinIO 实现遵循同一接口。
- [ ] 非法扩展名、MIME、文件头、超大文件和病毒文件被拒绝。
- [ ] 附件按版本绑定，草稿删除不影响历史版本。
- [ ] 下载、预览和解析接口执行数据权限校验。
- [ ] 相同版本相同哈希不重复存储或解析。
- [ ] OCR/解析任务按阶段记录状态、重试次数和错误，支持恢复和人工接管；Celery 任务不携带文件内容或 ORM 对象。
- [ ] 解析结果包含页码/坐标、原文片段、字段路径和置信度。
- [ ] 历史解析结果不可被新解析覆盖。

## 9. 【重点审核】

1. 文件大小、类型和附件总量限制。
2. 病毒扫描失败/超时的处理方式。
3. 草稿、退回和已提交版本的删除边界。
4. MinIO 预签名 URL 有效期和访问方式。
