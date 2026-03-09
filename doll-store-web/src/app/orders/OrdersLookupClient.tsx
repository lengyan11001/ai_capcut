"use client";

import { useMemo, useState } from "react";
import { t, type Lang } from "@/lib/i18n";
import { formatMoney } from "@/lib/money";

type LookupOrder = {
  id: string;
  total: number;
  currency: "CNY" | "USD" | "EUR";
  status: string;
  createdAt: string;
  paymentMethod: "manual_contact" | "crypto_manual";
  trackingNumber: string | null;
  trackingUrl: string | null;
  shippingCarrier: string | null;
  proofImages: string[];
  proofVideos: string[];
  shippedAt: string | null;
  deliveredAt: string | null;
};

export default function OrdersLookupClient({ lang }: { lang: Lang }) {
  const [email, setEmail] = useState("");
  const [orderId, setOrderId] = useState("");
  const [orders, setOrders] = useState<LookupOrder[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasResult = useMemo(() => orders.length > 0, [orders]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/orders/lookup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          orderId: orderId.trim() || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? t(lang, "Lookup failed", "查询失败"));
      setOrders(data.orders ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : t(lang, "Lookup failed", "查询失败"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-2xl font-bold text-gray-900">{t(lang, "Order tracking", "订单查询")}</h1>
      <p className="mt-2 text-sm text-gray-600">
        {t(
          lang,
          "Use your order email (and optional order ID) to check payment and shipping status.",
          "输入下单邮箱（可选填写订单号）查看支付与发货状态。"
        )}
      </p>

      <form onSubmit={onSubmit} className="mt-6 space-y-4 rounded border border-gray-200 bg-white p-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">{t(lang, "Order email", "下单邮箱")} *</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
            placeholder="you@email.com"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">
            {t(lang, "Order ID (optional)", "订单号（可选）")}
          </label>
          <input
            value={orderId}
            onChange={(e) => setOrderId(e.target.value)}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
            placeholder="uuid"
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="rounded bg-gray-900 px-4 py-2 text-sm text-white hover:bg-gray-800 disabled:opacity-70"
        >
          {loading ? t(lang, "Searching...", "查询中...") : t(lang, "Check orders", "查询订单")}
        </button>
      </form>

      {error ? <p className="mt-4 rounded bg-red-50 p-3 text-sm text-red-700">{error}</p> : null}

      <div className="mt-6 space-y-3">
        {hasResult ? (
          orders.map((order) => (
            <div key={order.id} className="rounded border border-gray-200 bg-gray-50 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-mono text-xs text-gray-700">{order.id}</p>
                <span className="rounded bg-white px-2 py-1 text-xs text-gray-700">{order.status}</span>
              </div>
              <p className="mt-2 text-sm text-gray-800">
                {t(lang, "Amount:", "金额:")} {formatMoney(order.total, order.currency ?? "CNY")}
              </p>
              <p className="text-sm text-gray-700">
                {t(lang, "Payment:", "支付方式:")}{" "}
                {order.paymentMethod === "crypto_manual"
                  ? t(lang, "Crypto transfer", "加密货币转账")
                  : t(lang, "Manual contact", "人工联系")}
              </p>
              <p className="text-sm text-gray-700">
                {t(lang, "Created:", "下单时间:")} {new Date(order.createdAt).toLocaleString()}
              </p>
              <p className="mt-1 text-sm text-gray-700">
                {t(lang, "Tracking:", "物流单号:")} {order.trackingNumber ?? t(lang, "Not shipped yet", "暂未发货")}
              </p>
              {order.shippedAt ? (
                <p className="text-sm text-gray-700">
                  {t(lang, "Shipped at:", "发货时间:")} {new Date(order.shippedAt).toLocaleString()}
                </p>
              ) : null}
              {order.trackingUrl ? (
                <a
                  href={order.trackingUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 inline-block text-sm text-gray-700 underline"
                >
                  {t(lang, "Open tracking link", "打开物流链接")}
                </a>
              ) : null}
              {order.proofImages?.length ? (
                <div className="mt-3 grid grid-cols-3 gap-2">
                  {order.proofImages.slice(0, 6).map((url) => (
                    <a
                      key={url}
                      href={url}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded border border-gray-200 bg-white p-1 text-[11px] text-gray-600 hover:bg-gray-50"
                    >
                      {t(lang, "Packing photo", "打包实拍")}
                    </a>
                  ))}
                </div>
              ) : null}
              {order.proofVideos?.length ? (
                <div className="mt-2 space-y-1">
                  {order.proofVideos.slice(0, 3).map((url) => (
                    <a
                      key={url}
                      href={url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-block text-sm text-gray-700 underline"
                    >
                      {t(lang, "View warehouse video", "查看仓库视频")}
                    </a>
                  ))}
                </div>
              ) : null}
            </div>
          ))
        ) : (
          <p className="text-sm text-gray-500">{t(lang, "No orders yet.", "暂无订单记录。")}</p>
        )}
      </div>
    </div>
  );
}
