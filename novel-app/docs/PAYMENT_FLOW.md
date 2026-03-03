# 充值支付实现说明（MVP）

## 已落地代码
- 订单创建：`novel-app/backend/src/main/java/com/novel/app/service/PayService.java`
- 支付回调：`novel-app/backend/src/main/java/com/novel/app/web/PayController.java`
- 钱包入账：`novel-app/backend/src/main/java/com/novel/app/service/WalletService.java`
- 钱包流水：`wallet_flow` 表与 `WalletFlowRepository`
- 补单任务：`PayService.reconcileCreatedOrders()`

## 流程
1. 客户端调用 `POST /pay/create` 创建订单。
2. 后端返回 `orderNo` 与 `mockCallbackSign`（用于联调）。
3. 支付成功后回调 `POST /pay/callback/{channel}`。
4. 后端验签通过后将订单置为 `PAID`，并给钱包加币。
5. 定时任务关闭超时未支付订单（`CREATED -> CLOSED`）。

## 验签规则
- `sign = hex(hash(orderNo + "|" + callbackSecret))`
- `callbackSecret` 来自配置 `novel.payment.callback-secret`

## 联调示例
1. 登录获取 token。
2. 调 `POST /pay/create`，得到 `orderNo` 和 `mockCallbackSign`。
3. 调 `POST /pay/callback/mockpay`：
   - `{"orderNo":"...","sign":"..."}`
4. 调 `GET /wallet/balance` 与 `GET /wallet/flows` 验证到账。
