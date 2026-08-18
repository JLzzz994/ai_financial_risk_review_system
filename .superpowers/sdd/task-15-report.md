# Task 15：前端静态检查门禁清理报告

## 状态

已完成。

## 改动文件

- `front/src/components/AmountText.vue`：为可选 `value` 增加 `null` 默认值，保持金额格式化行为不变。
- `front/src/components/MetricCard.vue`：为可选 `hint` 增加空字符串默认值，无提示时继续保持空白展示。
- `front/src/components/PaginationBar.vue`：将带 `withDefaults` 的分页参数声明为可选，保留 `page=1`、`pageSize=50`、`total=0` 默认值。

## 验证

- `npm run lint`：通过，0 errors、0 warnings。
- `npm run type-check`：通过，`vue-tsc --noEmit -p tsconfig.json` 成功。
- `npm run build`：通过，Vite 生产构建完成（157 modules transformed）。

## 提交

- 提交信息：`前端：清理静态检查默认值警告`
- 提交哈希：`7355711`（报告随提交后更新；最终提交哈希以 `git log` 为准）

## 疑虑

无。未修改 `docker-compose.yml`；构建生成的 `front/dist` 未纳入提交。
