# 稳定性与安全加固（MVP）

## 已落地项
- 缓存：`ContentService` 对首页、书籍、目录、章节使用 Spring Cache。
- 限流：`RateLimitInterceptor` 基于 IP 做分钟级限流。
- 可观测：启用 Spring Actuator（health/info/metrics/prometheus）。
- 日志链路：`TraceIdFilter` 注入并回传 `X-Trace-Id`。
- 异常处理：统一异常响应 `GlobalExceptionHandler`。
- 支付安全：回调签名校验 + 幂等入账（已支付直接返回成功）。

## 建议上线前补齐
- 将 `spring.cache.type` 切换为 Redis，并按业务设置 TTL。
- 将 JWT secret、支付 secret 放入安全配置中心或环境变量。
- 增加登录风控（设备指纹、IP 频控、验证码服务）。
- 对支付回调增加来源 IP 白名单与重放保护（nonce + timestamp）。

## 压测建议
- 工具：k6/JMeter。
- 场景：`/home/feed`、`/chapters/{id}/content`、`/pay/callback/{channel}`。
- 指标：P95、错误率、CPU/内存、Redis 命中率。
