---
name: decision-inbox-join
description: 用户要把这个 Codex 会话接入或退出 decision-inbox 协作组时使用（例如「接入协作组」「加入 decision-inbox」「退出协作组」）。
---

# 接入或退出 decision-inbox 协作组（Codex）

命令入口是 `~/.decision-inbox/bin/decision-inbox`（决策收件箱接入时写好）。不存在就请用户先让决策收件箱完成接入。

## 先看是否已接入

运行 `~/.decision-inbox/bin/decision-inbox whoami`：
- 打印出 JSON：本目录已经接入，告诉用户协作组、邮箱名、角色；
- 退出码 4：还没接入；退出码 5：对上了多个协作组，把 stderr 原样告诉用户。

## 接入

1. 向用户问清：协作组名、角色（dev／owner／coordinator）、本会话在 agent-relay 的邮箱名、线名、所属的线；开发线和跨线协调还要问有没有审查者、审哪几类节点（spec、plan、interface、final）。不要自己猜。
   再告诉用户「检查点答复即授权」默认打开：决策收件箱转来的、带用户原话的检查点答复（Spec 批准、Plan 批准、接口提案、最终验收），就是用户对这个检查点范围内必要操作（按 Spec、Plan 改文件、构建、测试、本地提交，以及安装 Plan 列出的依赖、只走官方源）的授权，也适用于 Codex 的自动批准；Plan 没列的新依赖（问一次）、密钥外传、工作区外删除、推送合并发布、改全局配置不在其内。用户明确不要，就加 `--no-checkpoint-authority`。
2. 预览：运行 `~/.decision-inbox/bin/decision-inbox onboard join <协作组> --role <角色> --relay-name <邮箱名> --short-name <线名> --host codex-desktop --project "$PWD"`，每条线加一个 `--line <线名>`，有审查者时加 `--reviewer <审查者邮箱名> --nodes <节点>`，用户不要授权时加 `--no-checkpoint-authority`。Codex 会话不填 `--desktop-session`。把输出给用户看；输出开头有 `⚠` 的行要先单独告诉用户，尤其是「Codex 会话要开在写协作规则段的那个仓库里」这一条：会话开在仓库外，协作规则段和授权都不会被 Codex 加载。
3. 用户确认后，同一条命令加 `--confirm` 再运行。
4. 用 agent-relay 的 `bridge_register` 登记邮箱名。
5. 提醒用户在 Codex 里信任一次 decision-inbox 插件自带的停止钩子。

## 退出

1. 预览：运行 `~/.decision-inbox/bin/decision-inbox onboard leave <协作组> --relay-name <邮箱名>`，把输出给用户看。
2. 用户确认后加 `--confirm` 再运行。名册和状态目录保留。
