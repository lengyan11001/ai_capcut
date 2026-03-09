"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useCart } from "@/context/CartContext";
import Link from "next/link";
import { formatMoney } from "@/lib/money";
import { isCountrySupported } from "@/lib/shipping";
import { normalizeLang, t, type Lang } from "@/lib/i18n";
import { trackEvent } from "@/lib/analytics";

export default function CheckoutPage() {
  const { items, subtotal, clearCart } = useCart();
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const [lang, setLang] = useState<Lang>("en");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [paymentMethod, setPaymentMethod] = useState<"manual_contact" | "crypto_manual">("manual_contact");
  const [form, setForm] = useState({
    name: "",
    email: "",
    phone: "",
    address: "",
    city: "",
    state: "",
    postalCode: "",
    country: "",
  });
  const countrySupported = form.country ? isCountrySupported(form.country) : true;
  const summaryCurrency = (items[0]?.currency ?? "CNY") as "CNY" | "USD" | "EUR";
  const mixedCurrencies = items.some((item) => (item.currency ?? "CNY") !== summaryCurrency);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!countrySupported) {
      setError(
        t(
          lang,
          "This destination is not available yet. Please contact support for a manual shipping quote.",
          "当前目的地暂不支持自动下单，请联系客服人工确认运费。"
        )
      );
      return;
    }
    setLoading(true);
    trackEvent("submit_order_attempt", {
      payment_method: paymentMethod,
      value: subtotal,
      currency: summaryCurrency,
    });
    try {
      const res = await fetch("/api/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: form.email,
          shipping: form,
          items,
          total: subtotal,
          currency: summaryCurrency,
          paymentMethod,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? t(lang, "Order failed", "订单提交失败"));
      clearCart();
      trackEvent("submit_order_success", {
        payment_method: paymentMethod,
        value: subtotal,
        currency: summaryCurrency,
      });
      router.push(
        `/checkout/thank-you?orderId=${data.orderId ?? ""}&lang=${lang}&paymentMethod=${paymentMethod}`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : t(lang, "Something went wrong", "系统异常，请稍后重试"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      setMounted(true);
      setLang(normalizeLang(new URLSearchParams(window.location.search).get("lang")));
      trackEvent("begin_checkout", {
        value: subtotal,
        currency: summaryCurrency,
      });
    }, 0);
    return () => clearTimeout(timer);
  }, [subtotal, summaryCurrency]);
  const withLang = (path: string) => `${path}?lang=${lang}`;

  if (!mounted) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-10">
        <div className="h-8 w-48 animate-pulse rounded bg-gray-200" />
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-16 text-center">
        <h1 className="text-2xl font-bold text-gray-900">{t(lang, "Your cart is empty", "购物车为空")}</h1>
        <Link href={withLang("/products")} className="mt-4 inline-block text-gray-600 underline">
          {t(lang, "Continue shopping", "继续购物")}
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="text-2xl font-bold text-gray-900">{t(lang, "Checkout", "结账")}</h1>
      <p className="mt-2 text-sm text-gray-500">
        {t(
          lang,
          "Displayed prices are factory-to-forwarder only. International freight and final payable amount will be confirmed after destination review.",
          "当前显示价格仅为工厂到货代，国际运费与最终应付金额将在确认目的地后给出。"
        )}
      </p>
      <form onSubmit={handleSubmit} className="mt-8 grid gap-8 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-4">
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-700">
              {t(lang, "Full name", "收货人姓名")} *
            </label>
            <input
              id="name"
              type="text"
              required
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
            />
          </div>
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700">
              Email *
            </label>
            <input
              id="email"
              type="email"
              required
              value={form.email}
              onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
            />
          </div>
          <div>
            <label htmlFor="phone" className="block text-sm font-medium text-gray-700">
              {t(lang, "Phone", "电话")}
            </label>
            <input
              id="phone"
              type="tel"
              value={form.phone}
              onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
            />
          </div>
          <div>
            <label htmlFor="address" className="block text-sm font-medium text-gray-700">
              {t(lang, "Address", "地址")} *
            </label>
            <input
              id="address"
              type="text"
              required
              value={form.address}
              onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))}
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="city" className="block text-sm font-medium text-gray-700">
                {t(lang, "City", "城市")} *
              </label>
              <input
                id="city"
                type="text"
                required
                value={form.city}
                onChange={(e) => setForm((f) => ({ ...f, city: e.target.value }))}
                className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
              />
            </div>
            <div>
              <label htmlFor="state" className="block text-sm font-medium text-gray-700">
                {t(lang, "State / Province", "州 / 省")}
              </label>
              <input
                id="state"
                type="text"
                value={form.state}
                onChange={(e) => setForm((f) => ({ ...f, state: e.target.value }))}
                className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
              />
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="postalCode" className="block text-sm font-medium text-gray-700">
                {t(lang, "Postal code", "邮编")} *
              </label>
              <input
                id="postalCode"
                type="text"
                required
                value={form.postalCode}
                onChange={(e) => setForm((f) => ({ ...f, postalCode: e.target.value }))}
                className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
              />
            </div>
            <div>
              <label htmlFor="country" className="block text-sm font-medium text-gray-700">
                {t(lang, "Country", "国家")} *
              </label>
              <input
                id="country"
                type="text"
                required
                value={form.country}
                onChange={(e) => setForm((f) => ({ ...f, country: e.target.value }))}
                className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
              />
              {!countrySupported && (
                <p className="mt-1 text-xs text-red-600">
                  {t(lang, "This destination is currently outside our shipping allowlist.", "当前目的地不在可发货白名单中。")}
                </p>
              )}
            </div>
          </div>
          {error && (
            <p className="rounded bg-red-50 p-3 text-sm text-red-700">{error}</p>
          )}
        </div>
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-6">
          <h2 className="font-semibold text-gray-900">{t(lang, "Order summary", "订单摘要")}</h2>
          <ul className="mt-4 space-y-2 text-sm text-gray-600">
            {items.map((item) => (
              <li key={item.productId} className="flex justify-between">
                <span>
                  {item.name} × {item.quantity}
                </span>
                <span>{formatMoney(item.price * item.quantity, item.currency ?? "CNY")}</span>
              </li>
            ))}
          </ul>
          <p className="mt-4 font-medium text-gray-900">
            {t(lang, "Subtotal:", "小计:")}{" "}
            {mixedCurrencies
              ? t(lang, "Mixed currencies in cart", "购物车存在多币种")
              : formatMoney(subtotal, summaryCurrency)}
          </p>
          <p className="mt-1 text-xs text-gray-500">
            {t(lang, "Freight: quoted after destination confirmation.", "运费：确认收货地区后报价。")}
          </p>
          <div className="mt-4 rounded border border-gray-200 bg-white p-3 text-left">
            <p className="text-sm font-medium text-gray-800">{t(lang, "Payment method", "支付方式")}</p>
            <label className="mt-2 flex items-start gap-2 text-sm text-gray-700">
              <input
                type="radio"
                name="paymentMethod"
                value="manual_contact"
                checked={paymentMethod === "manual_contact"}
                onChange={() => setPaymentMethod("manual_contact")}
                className="mt-0.5"
              />
              <span>
                <span className="font-medium">
                  {t(lang, "Manual contact payment", "人工联系支付")}
                </span>
                <span className="block text-xs text-gray-500">
                  {t(
                    lang,
                    "Submit order first, we will contact you to confirm shipping and payment.",
                    "先提交订单，我们将联系你确认运费与支付。"
                  )}
                </span>
              </span>
            </label>
            <label className="mt-2 flex items-start gap-2 text-sm text-gray-700">
              <input
                type="radio"
                name="paymentMethod"
                value="crypto_manual"
                checked={paymentMethod === "crypto_manual"}
                onChange={() => setPaymentMethod("crypto_manual")}
                className="mt-0.5"
              />
              <span>
                <span className="font-medium">{t(lang, "Crypto (manual transfer)", "加密货币（人工转账）")}</span>
                <span className="block text-xs text-gray-500">
                  {t(
                    lang,
                    "After placing order, pay by wallet address shown on thank-you page and contact support.",
                    "下单后按感谢页钱包地址转账，并联系客服确认到账。"
                  )}
                </span>
              </span>
            </label>
            {paymentMethod === "crypto_manual" && (
              <p className="mt-2 text-xs text-amber-700">
                {t(
                  lang,
                  "Tip: transfer with your order reference in memo for faster confirmation.",
                  "提示：转账备注填写订单号可更快确认。"
                )}
              </p>
            )}
          </div>
          <button
            type="submit"
            disabled={loading || !countrySupported}
            className="mt-6 w-full rounded bg-gray-900 py-3 font-medium text-white hover:bg-gray-800 disabled:opacity-70"
          >
            {loading ? t(lang, "Submitting…", "提交中…") : t(lang, "Submit order", "提交订单")}
          </button>
        </div>
      </form>
    </div>
  );
}
