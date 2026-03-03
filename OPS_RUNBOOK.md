# AI Test Platform 运维手册

> 适用当前收敛基线：后端 `8000`（systemd），平台 MCP `8001`，users 网关 `18790`。

## 1. 服务健康与状态

```bash
curl -i --max-time 8 http://127.0.0.1:8000/health
```

```bash
sudo systemctl status ai-test-platform.service --no-pager -l
sudo systemctl status ai-test-platform-mcp.service --no-pager -l
systemctl --user status openclaw-gateway-users.service --no-pager -l
```

```bash
sudo ss -lntp | grep -E ':8000|:8001|:18790'
```

## 2. 实例池与绑定

### 查看实例池

```bash
curl -s "http://127.0.0.1:8000/auth/openclaw-instances" \
  -H "X-Admin-Token: 你的ADMIN_SECRET"
```

### 查看某用户绑定

```bash
USER_ID=1
curl -s "http://127.0.0.1:8000/auth/openclaw-bindings?user_id=${USER_ID}" \
  -H "X-Admin-Token: 你的ADMIN_SECRET"
```

### 为用户分配实例

```bash
USER_ID=1
curl -s -X POST "http://127.0.0.1:8000/auth/openclaw-bindings/assign/${USER_ID}" \
  -H "X-Admin-Token: 你的ADMIN_SECRET"
```

## 3. 能力目录（capabilities）

### 查看能力目录

```bash
curl -s "http://127.0.0.1:8000/capabilities/registry" \
  -H "X-Admin-Token: 你的ADMIN_SECRET"
```

### 更新 image.generate 扣费

```bash
curl -s -X PUT "http://127.0.0.1:8000/capabilities/registry/image.generate" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: 你的ADMIN_SECRET" \
  -d '{"unit_credits":15,"enabled":true}'
```

### 新增 model.search / model.guide（若缺失）

```bash
BASE_URL="http://127.0.0.1:8000"
ADMIN_TOKEN="你的ADMIN_SECRET"

curl -s -X POST "${BASE_URL}/capabilities/registry" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: ${ADMIN_TOKEN}" \
  -d '{
    "capability_id":"model.search",
    "description":"搜索可用模型（统一能力入口）",
    "upstream":"sutui",
    "upstream_tool":"search_models",
    "enabled":true,
    "unit_credits":0,
    "arg_schema":{"type":"object","properties":{"keyword":{"type":"string"}},"required":[]}
  }'

curl -s -X POST "${BASE_URL}/capabilities/registry" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: ${ADMIN_TOKEN}" \
  -d '{
    "capability_id":"model.guide",
    "description":"查询模型使用指南（统一能力入口）",
    "upstream":"sutui",
    "upstream_tool":"guide",
    "enabled":true,
    "unit_credits":0,
    "arg_schema":{"type":"object","properties":{"model":{"type":"string"}},"required":[]}
  }'
```

## 4. MCP allowlist 与重启

```bash
sudo sed -i 's|CAPABILITY_ALLOWLIST=.*|CAPABILITY_ALLOWLIST=image.generate,task.get_result,model.search,model.guide|g' \
/etc/systemd/system/ai-test-platform-mcp.service.d/override.conf

sudo systemctl daemon-reload
sudo systemctl restart ai-test-platform-mcp.service
```

### 验证 tools/list

```bash
curl -s "http://127.0.0.1:8001/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"t1","method":"tools/list","params":{}}'
```

## 5. 积分相关

### 给用户充值积分

```bash
curl -s -X POST "http://127.0.0.1:8000/auth/recharge" \
  -H "Content-Type: application/json" \
  -H "X-Recharge-Token: 你的RECHARGE_SECRET" \
  -d '{"email":"用户邮箱@example.com","amount":5000}'
```

### 查询用户积分（需用户 JWT）

```bash
JWT="用户JWT"
curl -s "http://127.0.0.1:8000/auth/me" \
  -H "Authorization: Bearer ${JWT}"
```

### 查询用户积分流水（需用户 JWT）

```bash
JWT="用户JWT"
curl -s "http://127.0.0.1:8000/auth/credit-flows?limit=20" \
  -H "Authorization: Bearer ${JWT}"
```

## 6. 调用审计

```bash
curl -s "http://127.0.0.1:8000/capabilities/call-logs?limit=20" \
  -H "X-Admin-Token: 你的ADMIN_SECRET"
```

## 7. 常见问题速查

- 前端报 `OpenClaw Gateway 401 Unauthorized`
  - 检查实例池 `gateway_token` 是否与 users 网关真实 token 一致。
- 前端看不到 `invoke_capability`
  - 检查 users 网关插件是否注册失败（`openclaw-mcp-adapter` 日志）。
- 生成图片提示模型不存在
  - 先调用 `model.search` 查可用模型，再调用 `image.generate`。
- 新用户注册后无法使用
  - 检查是否自动分配 binding：`/auth/openclaw-bindings?user_id=...`。

