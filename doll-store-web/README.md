# Doll Store — Next.js 独立站

成人娃娃/实体娃娃独立站示例：Next.js 14 (App Router) + TypeScript + Tailwind。支持首页、分类、商品详情、购物车、结账与订单提交，可部署到 Vercel。

## 功能

- 首页：内容优先入口（Guides）、分类入口、精选商品、信任条
- 分类页 `/category/[slug]`、全部商品 `/products`
- 商品详情 `/product/[slug]`：图、规格、加入购物车
- 购物车 `/cart`：数量修改、小计、去结账
- 结账 `/checkout`：收货信息表单 + 订单摘要，提交后写入 Supabase（若已配置）
- 后台管理（MVP）：
  - `/admin/login` 管理员密码登录
  - `/admin/products` 商品列表、双币种价格与素材状态管理
  - `/admin/products/new` 新建商品，支持上传图片/视频到 Supabase Storage
- 订单管理：
  - `/admin/orders` 订单列表（支付方式、状态、物流号）
  - `/admin/orders/[id]` 订单详情编辑（状态、物流、tx hash、内部备注）
  - `/orders` 用户查单页（按下单邮箱查询订单状态与物流）
- 发货实拍中心：`/shipping-proof` 公开展示打包/交运证据
- 商品详情媒体区：缩略图切换 + 图片悬停放大预览（视频仅播放不放大）
- 多语言切换：右上角支持 `EN / 中文`（通过 `lang` URL 参数切换）
- 全局咨询入口：右下角浮动客服按钮（WhatsApp / Telegram / Email）
- 合规控制：18+ 年龄门槛、大陆访问 403（支持 access_key 白名单放行）
- 数据统计：GA4 + Clarity（经 Cookie 同意后加载）
- 静态页：About、Shipping & Delivery、Privacy Policy、Contact

支付：当前默认为「提交订单」后由站长联系客户完成支付，并支持可选「加密货币人工转账」入口（下单后在感谢页展示钱包信息）。真实自动收款可后续对接成人友好通道（如 CCBill、Epoch），参见仓库根目录下 `docs/doll-store/` 下的《Shopify从零到上线步骤》或《自建服务器独立站从零到上线》中的支付章节。

## 本地运行

```bash
cd doll-store-web
cp .env.example .env
# 编辑 .env，填入 Supabase 变量（可选，不填则订单不落库，仍可走完结账流程）
npm install
npm run dev
```

打开 [http://localhost:3000](http://localhost:3000)。

## 环境变量

见 `.env.example`。若未配置 Supabase，`POST /api/orders` 仍返回成功并生成一个临时 orderId，便于测试；订单不会持久化，可在后续接入 Resend/SendGrid 将订单内容发到站长邮箱。

### 后台管理相关变量

- `ADMIN_PANEL_PASSWORD`：后台登录密码（必填）
- `SUPABASE_ASSET_BUCKET`：后台上传素材的 Storage bucket（默认 `product-media`）

### 加密支付入口（人工确认）变量

- `CRYPTO_PAY_COIN`：币种（默认 `USDT`）
- `CRYPTO_PAY_NETWORK`：网络（默认 `TRON (TRC20)`）
- `CRYPTO_PAY_ADDRESS`：收款地址（未配置时感谢页会提示联系客服）

### 全局客服入口变量

- `NEXT_PUBLIC_SUPPORT_WHATSAPP`：支持手机号（可填纯数字或完整 `https://wa.me/...`）
- `NEXT_PUBLIC_SUPPORT_TELEGRAM`：支持 `@handle` 或完整 `https://t.me/...`
- `NEXT_PUBLIC_SUPPORT_INSTAGRAM`：支持 `@handle` 或完整 `https://instagram.com/...`
- `NEXT_PUBLIC_SUPPORT_EMAIL`：客服邮箱（会渲染为 `mailto:`）

### 统计与同意弹窗

- `NEXT_PUBLIC_GA4_ID`：Google Analytics 4 Measurement ID（如 `G-XXXX`）
- `NEXT_PUBLIC_CLARITY_ID`：Microsoft Clarity 项目 ID
- 页面底部同意弹窗选择“同意”后才会加载统计脚本

### 区域访问与年龄限制

- `BLOCK_MAINLAND_CN=true`：启用中国大陆 IP 拦截（403）
- `ACCESS_BYPASS_KEY=...`：你本人放行密钥（URL `?access_key=...`）
- `NEXT_PUBLIC_ENABLE_AGE_GATE=true`：启用 18+ 年龄确认弹窗

### 供应商优先展示（新供应商优先）

- `NEXT_PUBLIC_CORE_SUPPLIERS=mxj`：前台仅展示核心供应商（可多值逗号分隔）
- `NEXT_PUBLIC_ENABLE_CORE_SUPPLIER_FILTER=true`：开启核心供应商过滤

### Supabase 订单表

在 Supabase SQL Editor 中执行以下建表语句后，订单会写入 `orders` 表：

```sql
create table if not exists orders (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  shipping_name text not null,
  shipping_address text not null,
  shipping_phone text,
  items jsonb not null,
  total numeric not null,
  currency text default 'USD',
  status text default 'pending',
  created_at timestamptz default now()
);

-- 允许匿名插入（或使用 service_role key 跳过 RLS）
alter table orders enable row level security;
create policy "Allow insert" on orders for insert with check (true);
create policy "Allow select by service" on orders for select using (true);
```

### Supabase 商品表（后台销售价/运费策略）

执行 `docs/sql/products_admin_schema.sql`。

执行后可用以下命令把当前 JSON 商品导入到 Supabase（`cost_price` 初始化为成本价，`sale_price` 默认与成本价一致，后续可在后台改）：

```bash
npm run import:products
```

导入供应商“美国本土库存 > 0”商品（编码如 `US-70CM-w-247` 将直接作为后台可见编号）：

```bash
# 默认读取固定供应商文件路径
npm run import:us-stock

# 仅预览将导入多少条（不写库）
npm run import:us-stock -- --dry-run

# 指定其他供应商文件（为后续多供应商扩展保留）
npm run import:us-stock -- --file="/absolute/path/to/inventory_raw.json"
```

将已导入的美国仓商品文案统一转为英文（清洗中文字段）：

```bash
npm run normalize:us-copy
```

如需将供应商外链素材（如 `47.107.244.246`）迁移到你自己的 Supabase Storage，并自动回写商品图片/视频 URL：

```bash
# 先演练，不写库
npm run migrate:supplier-assets -- --dry-run

# 正式执行
npm run migrate:supplier-assets
```

### 素材状态流（无水印版）

- `raw`：原始素材，仅后台可见，不在前台展示
- `processed`：已处理待发布，仅后台可见，不在前台展示
- `published`：可公开展示，前台可见

前台商品列表与详情默认只显示 `asset_status = published` 的商品。

## 数据与素材

- 商品与分类：`src/data/products.json`、`src/data/categories.json`。可替换为 CMS 或 API。
- **图片与视频（占位）**：当前演示使用 Unsplash 占位图、首页 Hero 使用 Unsplash 图、商品可选 `videoUrl` 占位视频。**上线前请全部替换为自有或供应商授权的图片/视频**，勿直接使用竞品站素材。可改：
  - 首页 Hero：`src/app/page.tsx` 中的 `HERO_IMAGE`，或改为 `public/hero.jpg` 等本地路径。
  - 商品图/视频：`src/data/products.json` 的 `images`、`videoUrl`，或改为从 CMS/API 拉取。

## 部署（Vercel）

1. 将项目推送到 GitHub，在 Vercel 中 Import 该仓库，根目录设为 `doll-store-web`（或把本目录作为仓库根再导入）。
2. 在 Vercel 项目 Settings → Environment Variables 中配置 `NEXT_PUBLIC_SUPABASE_URL`、`SUPABASE_SERVICE_ROLE_KEY`。
3. Deploy。部署命令为 `npm run build`，输出目录由 Vercel 自动识别。

## 后台入库与调价流程（推荐）

1. 在 Supabase 执行 `docs/sql/products_admin_schema.sql`
2. 在 Supabase Storage 创建 bucket：`product-media`（或你自定义名字并填到 `.env`）
3. 本地执行 `npm run import:products` 初始化商品
4. 打开 `/admin/login` 登录后台
5. 在 `/admin/products` 设置 `cost_price/cost_currency`、`sale_price/sale_currency`、素材状态、海外仓包邮开关和素材

## 本周支付流程（已上线）

1. 结账页选择支付方式：
   - `Manual contact payment`（人工联系支付，默认）
   - `Crypto (manual transfer)`（加密货币人工转账）
2. 订单提交后进入感谢页：
   - 人工支付：提示等待客服联系
   - 加密支付：展示币种、网络、钱包地址和转账备注（订单号）
3. 客服人工确认到账后安排后续发货流程

## 订单与发货管理（已上线）

1. 后台打开 `/admin/orders` 查看全部订单，支持查看：
   - 支付方式（人工/加密）
   - 当前状态（`pending`/`pending_crypto`/`paid`/`shipped` 等）
   - 物流单号
2. 进入 `/admin/orders/[id]` 可编辑：
   - 状态
   - 物流公司、物流号、物流链接
   - 加密支付 tx hash、到账金额
   - 内部备注
3. 前台用户可在 `/orders` 输入下单邮箱（可选订单号）查询订单状态与物流信息
4. 后台订单支持维护“打包实拍图片 URL / 仓库视频 URL”，前台查单页会同步展示

## 项目结构

- `src/app/` — 页面与 API 路由
- `src/components/` — Header、Footer、ProductCard
- `src/context/` — CartContext（购物车状态 + localStorage）
- `src/lib/data.ts` — 读取分类与商品
- `src/data/` — 静态 JSON 数据
