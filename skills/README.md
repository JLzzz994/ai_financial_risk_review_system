# 通用 Python 技能与财务项目技能

本目录分为两层：`python-*` 是可复用的通用 Python 技能，`financial-*` 是当前财务单据智能风险审核系统的项目约束层。两层均依据 `E:\260302ai\agents\skill\zhangchen\.agents\skills` 中的 Java 技能迁移。

推荐使用顺序：

1. `financial-data-object-skill`：先按当前项目表名和规则确定对象。
2. `financial-spec-skill`：依据数据对象和概要设计生成当前项目模块 SPEC。
3. `diagram-builder`：将模块边界、核心流程、状态机和数据关系转成图，并渲染检查。
4. `writing-plans`：把已审核的 SPEC 拆成可执行、可验证的实现计划。

通用技能：`python-coding-skill`、`python-data-object-skill`、`python-outline-design-skill`、`python-spec-skill`。
项目技能：对应的 `financial-coding-skill`、`financial-data-object-skill`、`financial-outline-design-skill`、`financial-spec-skill`。
