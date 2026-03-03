# 小说 App（对标七猫）MVP 代码

## 目录
- `backend`：Spring Boot 后端（鉴权、内容、书架、阅读、支付、钱包、运营位）
- `mobile-uniapp`：UniApp 移动端（书城/书架/阅读/我的/充值）
- `admin-web`：Vue3 管理后台（运营位、订单、用户查询）
- `docs`：PRD、内容 API 适配、支付、稳定性、安全、上线方案

## 快速开始

### 1) 启动后端
```bash
cd novel-app/backend
# 需要本地有 Maven
mvn spring-boot:run
```
后端默认地址：`http://localhost:8088`

### 2) 启动管理后台
```bash
cd novel-app/admin-web
npm install
npm run dev
```

### 3) 启动 UniApp（按你本地工具链）
```bash
cd novel-app/mobile-uniapp
npm install
# 使用 HBuilderX 或 uni-cli 运行
```

## 接口联调顺序建议
1. `POST /auth/sms-login`（验证码 `123456`）
2. `GET /home/feed`
3. `POST /shelf/add` + `GET /shelf/list`
4. `GET /books/{id}/chapters` + `GET /chapters/{id}/content`
5. `POST /pay/create` -> `POST /pay/callback/mockpay` -> `GET /wallet/balance`
