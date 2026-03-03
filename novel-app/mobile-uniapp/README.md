# Novel App Mobile (UniApp)

## 已实现（MVP 骨架）
- 登录页（短信登录，测试码 123456）
- 书城页（推荐 + 搜索）
- 书架页（添加/移除）
- 阅读器页（章节内容 + 保存进度）
- 我的页（余额）
- 充值页（创建订单）

## 状态管理（Pinia）
- `stores/auth.js`
- `stores/content.js`
- `stores/shelf.js`
- `stores/reader.js`
- `stores/wallet.js`

## 后端地址
- 默认 `http://localhost:8088`，可修改 `utils/request.js` 的 `BASE_URL`。
