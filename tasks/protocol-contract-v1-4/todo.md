# Todo: protocol-contract-v1-4

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：换 v1.4 样例、调计数、变异检查
  - 验收：Spec 验收 1、2、3
  - 验证：`python3 -m unittest discover -s tests -p test_contract.py -v`
  - 文件：`tests/fixtures/session-protocol/`、`tests/test_contract.py`
  - 记录（2026-10-18）：先改测试（版本 v1.4、来源 e33c077、解析 52、生成 6），在 v1.3 副本上 1 失败 7 报错；从契约 e33c077 `git archive` 取出 v1.4 样例替换后 `shasum -c` 通过、一致性测试 6 个全过。变异检查：去掉 `_review` 的半角转全角，只有 `wait-user/review-advice-halfwidth` 失败；去掉字段冒号后的 `\s*`，只有 `user-reply/original-whitespace` 失败；还原后产品代码无改动。Ran 568 tests, OK

- [ ] Task 2：能力图、README、版本 0.0.11、通知契约负责人
  - 验收：Spec 验收 4、5
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`spec/CAPABILITY-MAP.md`、`README.md`、两份 `plugin.json`、`tests/test_packaging.py`

- [ ] Checkpoint（gate）：模块最终验收，等用户确认
