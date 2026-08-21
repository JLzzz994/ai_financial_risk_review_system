# 文件存储模块

业务代码只依赖 `engines.common.storage.FileStorage` 契约，不依赖具体对象存储 SDK。

## 适配器

- `LocalFileStorage`：本地开发和单元测试，根目录由 `LOCAL_STORAGE_PATH` 配置，数据库只保存 `object_key`。
- `MinioFileStorage`：生产环境适配 MinIO，负责上传、读取、删除和最长 300 秒预签名地址。
- `build_object_key`：按 `document_id/version_id/attachment_id/file_name` 生成版本化对象键。

## 安全约束

- 拒绝绝对路径和 `..` 目录穿越。
- 不把本地绝对路径写入 PostgreSQL。
- 真实附件不得放入本交付目录；演示只使用内存字节或脱敏样本。

## 运行示例

在项目根目录执行：

```bash
uv run python 交付物/文件存储/存储示例.py
```

示例会在 `交付物/运行日志/storage-demo/` 写入一个临时对象，读取、删除后清理，并验证目录穿越会被拒绝。
