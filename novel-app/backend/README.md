# Novel App Backend

## 启动方式
```bash
cd novel-app/backend
mvn spring-boot:run
```

默认端口：`8088`

## 核心 API（MVP）
- `POST /auth/sms-login`
- `POST /auth/refresh`
- `GET /auth/profile`
- `GET /home/feed`
- `GET /books/{id}`
- `GET /books/{id}/chapters`
- `GET /chapters/{id}/content`
- `GET /search/suggest?keyword=...`
- `GET /search/result?keyword=...`
- `GET /shelf/list`
- `POST /shelf/add`
- `POST /shelf/remove`
- `POST /reading/progress/save`
- `GET /reading/progress/get?bookId=...`
- `GET /wallet/balance`
- `GET /wallet/flows`
- `POST /pay/create`
- `POST /pay/callback/{channel}`
- `GET /pay/orders`
- `GET /ops/banners`
- `GET /ops/channels`

## 支付回调签名（示例）
- 计算方式：`hex(hash(orderNo + "|" + callbackSecret))`
- `callbackSecret` 读取 `novel.payment.callback-secret`
