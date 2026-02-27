# 测试平台 MCP 工具清单与成本核算

## 一、MCP 工具清单（与现有 API 对应）

以下工具对应后端已实现或计划实现的能力，调用时按「积分」扣费，积分不足返回 402。

| 工具名 | 说明 | 对应 API | 积分/次 | 备注 |
|--------|------|----------|--------|------|
| `run_api_test` | 执行单次 HTTP 接口测试 | `POST /api-test` | 1 | 按请求一次扣 1 积分 |
| `generate_and_run_from_doc` | 从 Swagger/OpenAPI 文档生成用例并执行 | `POST /api-test/from-doc` | 仅执行时：1/条 | only_generate=true 不扣费 |
| `generate_cases_from_doc` | 仅从文档生成用例（不执行） | 同上，only_generate=true | 0 | 当前策略不扣费 |
| `get_me` | 查询当前用户信息与剩余积分 | 计划 `GET /me` | 0 | 只读 |
| `list_tools` | 列出可用能力及单价 | 计划 `GET /pricing` 或写死 | 0 | 只读 |

### 1. run_api_test

- **入参**：`url`, `method`(GET/POST/PUT/DELETE), `headers`(可选), `query`(可选), `body`(可选), `expect_status`(默认 200), `timeout_seconds`(默认 10)
- **返回**：`passed`, `status_code`, `expect_status`, `duration_ms`, `response_headers`, `response_snippet`, `error`
- **扣费**：1 积分/次

### 2. generate_and_run_from_doc

- **入参**：`schema_url`(必填), `base_url`(可选), `max_cases_per_api`(默认 1), `only_generate`(默认 false)；可选 `extra_headers`、`extra_query`、`auth`（先登录取 token 再注入）
- **文档**：支持 Swagger/OpenAPI 的 JSON 或 YAML 地址，含 **Apifox 分享链接**（如 `https://s.apifox.cn/xxx`）
- **认证**：可配置 `auth.login_url` + 账号/密码，或 `auth.body` + `token_response_path`（如 `data.token`），执行前先请求登录接口，将返回的 token 写入后续请求的 `Authorization`；也可仅用 `extra_headers` 填写固定 Token 或 API-Key
- **返回**：`total_apis`, `total_cases`, `executed`, `cases[]`, `results[]`(执行时)
- **扣费**：仅当 `only_generate=false` 时，按执行用例条数 × 1 积分

### 3. generate_cases_from_doc

- 即上述 `only_generate=true`，只返回生成的用例列表，不执行。
- **扣费**：0（当前策略）

---

## 二、套餐与定价建议（面向 C 端/小团队）

| 套餐 | 价格 | 赠送积分 | 约等于可测次数 | 目标用户 |
|------|------|----------|----------------|----------|
| 免费 | 0 | 100/月 | 100 次单接口 或 若干次文档批量 | 体验 |
| 基础 | ¥29/月 | 1,000 | 1,000 次单接口 | 个人/小项目 |
| 专业 | ¥99/月 | 5,000 | 5,000 次 | 小团队 |
| 企业 | ¥299/月 | 20,000 或无限 | 按需 | 企业 + 私有化可选 |

- 单次接口测试：1 积分/次。
- 从文档执行：1 积分/条用例（仅执行扣费，只生成不执行 0）。

---

## 三、成本核算

### 3.1 固定成本（月）

| 项目 | 金额（元/月） | 说明 |
|------|----------------|------|
| 云服务器 ECS（2核4G） | 80～120 | 阿里云/腾讯云按量或包月 |
| 数据库 RDS（可选） | 0～100 | 初期可用 SQLite/单机，省掉 |
| Redis（可选） | 0～80 | 初期可省 |
| 域名 + SSL | 约 8 | 均摊到月 |
| **固定合计** | **约 90～310** | 最小化约 90 |

### 3.2 单次调用成本（当前无 AI 时）

- **单接口测试**：仅本机 HTTP 请求 + 数据库扣积分，成本可忽略（< 0.001 元/次）。
- **从文档生成+执行**：拉取文档 1 次 HTTP + N 次被测接口请求 + DB，单条仍可忽略。

即：**当前阶段无大模型、无第三方按量 API 时，单次变动成本 ≈ 0**，主要成本是服务器固定成本。

### 3.3 若接入大模型（后续）

- 从文档「生成用例」若改为调用 Claude/GPT：约 0.01～0.05 元/次（按 token 计）。
- 若按 0.02 元/次、且对用户收 1 积分/条（或 0.05 元/条），则单条仍有毛利；批量生成时需按「生成次数」或「条数」设积分单价，避免亏损。

### 3.4 盈亏平衡（仅固定成本）

- 固定成本按 **100 元/月** 计。
- 若全部为付费用户、按 **¥29/月** 计：
  - 需 **约 4 个付费用户** 即可覆盖 100 元（29×4=116）。
- 若 50% 为 ¥29、50% 为 ¥99：
  - 约 2 个 ¥99 + 1 个 ¥29 ≈ 227，已覆盖 100 元固定成本并有盈余。

### 3.5 成本小结

| 维度 | 数值 |
|------|------|
| 月固定成本（最小化） | 约 90～100 元 |
| 单次接口测试变动成本 | ≈ 0（无 AI） |
| 单次「从文档执行」变动成本 | ≈ 0（无 AI） |
| 接入大模型后单次生成成本 | 约 0.01～0.05 元，需用积分/定价覆盖 |
| 盈亏平衡（100 元/月） | 约 4 个 ¥29 套餐 或 2 个 ¥99 |

---

## 四、MCP Server 实现要点（后续）

1. **鉴权**：MCP 调用时带用户 token 或 API Key，后端校验后扣该用户积分。
2. **工具与 API 一一对应**：`run_api_test` → `POST /api-test`，`generate_and_run_from_doc` → `POST /api-test/from-doc`。
3. **扣费**：与现有 `api_test`、`api_test/from-doc` 逻辑一致，使用 `core/credits.py` 中单价。
4. **限流**：按用户/API Key 限流，防止恶意刷量。

当前后端已具备：用户、积分、单接口测试、从文档生成并执行及扣费。MCP Server 只需封装 HTTP 调用并透传鉴权与参数即可。
