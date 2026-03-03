# 第三方内容 API 适配说明

## 1. 目标
- 通过后端代理统一对接第三方正版内容 API，前端不直连第三方。
- 降低上游变更影响，便于缓存、鉴权、限流与审计。

## 2. 当前实现位置
- 适配器：`novel-app/backend/src/main/java/com/novel/app/service/ContentProviderClient.java`
- 业务封装：`novel-app/backend/src/main/java/com/novel/app/service/ContentService.java`

## 3. 对接协议（可按供应商调整）
- `GET /home/feed`
- `GET /books/{bookId}`
- `GET /books/{bookId}/chapters`
- `GET /chapters/{chapterId}/content`
- `GET /search/suggest?keyword=...`
- `GET /search/result?keyword=...`

请求头建议：
- `X-App-Key: <content.app-key>`
- 可选：`X-Sign`, `X-Timestamp`, `X-Nonce`

## 4. 配置项
来自 `application.yml` 的 `novel.content`：
- `base-url`
- `app-key`
- `app-secret`
- `timeout-millis`

## 5. 缓存策略（MVP）
- 首页 feed：短缓存（可设 30-120 秒）
- 书籍详情：中缓存（可设 5-30 分钟）
- 目录：中缓存（可设 5-30 分钟）
- 章节内容：长缓存（可设 1-24 小时，按版权协议）

当前使用 Spring Cache 注解，默认 simple cache；生产建议切 Redis 并设置 TTL。

## 6. 降级策略
- 调用第三方失败时，返回 mock/fallback 数据，确保前端流程可继续联调。
- 上线前请将 fallback 限制在灰度/测试环境，并开启告警。
