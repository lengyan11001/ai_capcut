# Doll Store — Next.js 独立站

成人娃娃/实体娃娃独立站示例：Next.js 14 (App Router) + TypeScript + Tailwind。支持首页、分类、商品详情、购物车、结账与订单提交，可部署到 Vercel。

## 功能

- 首页：Hero、分类入口、精选商品、信任条（隐私包装、安全支付、客服）
- 分类页 `/category/[slug]`、全部商品 `/products`
- 商品详情 `/product/[slug]`：图、规格、加入购物车
- 购物车 `/cart`：数量修改、小计、去结账
- 结账 `/checkout`：收货信息表单 + 订单摘要，提交后写入 Supabase（若已配置）
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

## 数据

- 商品与分类：`src/data/products.json`、`src/data/categories.json`。可替换为 CMS 或 API。
- 占位图使用 placehold.co；正式环境请替换为自有图床或 CDN。

## 部署（Vercel）

1. 将项目推送到 GitHub，在 Vercel 中 Import 该仓库，根目录设为 `doll-store-web`（或把本目录作为仓库根再导入）。
2. 在 Vercel 项目 Settings → Environment Variables 中配置 `NEXT_PUBLIC_SUPABASE_URL`、`SUPABASE_SERVICE_ROLE_KEY`。
3. Deploy。部署命令为 `npm run build`，输出目录由 Vercel 自动识别。

## 项目结构

- `src/app/` — 页面与 API 路由
- `src/components/` — Header、Footer、ProductCard
- `src/context/` — CartContext（购物车状态 + localStorage）
- `src/lib/data.ts` — 读取分类与商品
- `src/data/` — 静态 JSON 数据
