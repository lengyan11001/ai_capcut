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
  - `/admin/products` 商品列表与销售价管理
  - `/admin/products/new` 新建商品，支持上传图片/视频到 Supabase Storage
- 静态页：About、Shipping & Delivery、Privacy Policy、Contact

支付：当前为「提交订单」后由站长联系客户完成支付。真实收款需自行对接成人友好通道（如 CCBill、Epoch），参见仓库根目录下 `docs/doll-store/` 下的《Shopify从零到上线步骤》或《自建服务器独立站从零到上线》中的支付章节。

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
5. 在 `/admin/products` 设置 `sale_price`、海外仓包邮开关和素材

## 项目结构

- `src/app/` — 页面与 API 路由
- `src/components/` — Header、Footer、ProductCard
- `src/context/` — CartContext（购物车状态 + localStorage）
- `src/lib/data.ts` — 读取分类与商品
- `src/data/` — 静态 JSON 数据
