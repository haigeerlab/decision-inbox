---
name: decision-inbox-join
description: 用户要把这个 Codex 会话接入或退出 decision-inbox 协作组时使用（例如「接入协作组」「加入 decision-inbox」「退出协作组」）。
---

# 接入或退出 decision-inbox 协作组（Codex）

命令入口是 `~/.decision-inbox/bin/decision-inbox`（收件枢纽接入时写好）。不存在就请用户先让收件枢纽完成接入。

## 先看是否已接入

运行 `~/.decision-inbox/bin/decision-inbox whoami`：
- 打印出 JSON：本目录已经接入，告诉用户协作组、身份名、角色；
- 退出码 4：还没接入；退出码 5：对上了多个协作组，把 stderr 原样告诉用户。

## 接入

1. 向用户问清：协作组名、角色（dev／owner／coordinator）、本会话在 agent-relay 的身份名、短名、所属的线；开发线和总协调还要问有没有审查者、审哪几类节点（spec、plan、interface、final）。不要自己猜。
2. 预览：运行 `~/.decision-inbox/bin/decision-inbox onboard join <协作组> --role <角色> --relay-name <身份名> --short-name <短名> --host codex-desktop --project "$PWD"`，每条线加一个 `--line <线名>`，有审查者时加 `--reviewer <负责人身份名> --nodes <节点>`。Codex 会话不填 `--desktop-session`。把输出给用户看。
3. 用户确认后，同一条命令加 `--confirm` 再运行。
4. 用 agent-relay 的 `bridge_register` 登记身份名。
5. 提醒用户在 Codex 里信任一次 decision-inbox 插件自带的停止钩子。

## 退出

1. 预览：运行 `~/.decision-inbox/bin/decision-inbox onboard leave <协作组> --relay-name <身份名>`，把输出给用户看。
2. 用户确认后加 `--confirm` 再运行。名册和状态目录保留。
