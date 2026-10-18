---
description: 本会话退出协作组：删掉规则文件里的 decision-inbox 约定块
argument-hint: <协作组> <身份名>
allowed-tools: Bash
---

参数：$ARGUMENTS（缺了就先运行 `"${CLAUDE_PLUGIN_ROOT}/bin/decision-inbox" whoami` 取得）。只删约定块，名册和状态目录保留。

1. 预览：运行 `"${CLAUDE_PLUGIN_ROOT}/bin/decision-inbox" onboard leave <协作组> --relay-name <身份名>`，把输出给用户看。用 `onboard enroll` 只登记、没写约定块的会话也用这条命令，它不会改任何文件，只是让收件枢纽不再给它发消息。
2. 等用户确认后，同一条命令加 `--confirm` 再运行。用户没确认就停在这里。
