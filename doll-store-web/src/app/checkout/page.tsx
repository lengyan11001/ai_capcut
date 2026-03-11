"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useCart } from "@/context/CartContext";
import Link from "next/link";
import { formatMoney } from "@/lib/money";
import { isCountrySupported } from "@/lib/shipping";
import { normalizeLang, t, type Lang } from "@/lib/i18n";
import { trackEvent } from "@/lib/analytics";
import { localizeProductName } from "@/lib/product-copy";

type PayPalButtonsActions = {
  render: (container: HTMLElement) => Promise<void>;
};

type PayPalOnClickActions = {
  resolve: () => Promise<void>;
  reject: () => Promise<void>;
};

type PayPalNamespace = {
  Buttons: (config: {
    style?: { layout?: string; shape?: string; label?: string };
    onClick?: (_data: unknown, actions: PayPalOnClickActions) => Promise<void> | void;
    createOrder: () => Promise<string>;
    onApprove: (data: { orderID?: string }) => Promise<void>;
    onCancel: () => void;
    onError: () => void;
  }) => PayPalButtonsActions;
};

export default function CheckoutPage() {
  const { items, subtotal, clearCart } = useCart();
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const [lang, setLang] = useState<Lang>("en");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [paymentMethod, setPaymentMethod] = useState<"manual_contact" | "crypto_manual" | "paypal">("manual_contact");
  const [paypalSdkError, setPaypalSdkError] = useState<string | null>(null);
  const [paypalReady, setPaypalReady] = useState(false);
  const paypalButtonsRef = useRef<HTMLDivElement | null>(null);
  const checkoutFormRef = useRef<HTMLFormElement | null>(null);
  const paypalClientId = process.env.NEXT_PUBLIC_PAYPAL_CLIENT_ID ?? "";
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
  const paypalCurrency = summaryCurrency;
  const paypalCurrencySupported = paypalCurrency === "USD" || paypalCurrency === "EUR";
  const requiredShippingMissing = !form.name || !form.email || !form.address || !form.city || !form.postalCode || !form.country;

  const paypalValidationHint = useMemo(() => {
    if (paymentMethod !== "paypal") return null;
    if (requiredShippingMissing) {
      return t(lang, "Complete required shipping fields before opening PayPal.", "请先填写完整收货信息，再打开 PayPal。");
    }
    if (!countrySupported) {
      return t(
        lang,
        "This destination is not available yet. Please contact support for a manual quote.",
        "当前目的地暂不支持自动下单，请联系客服人工确认运费。"
      );
    }
    if (mixedCurrencies) {
      return t(
        lang,
        "Mixed currencies in cart are not supported for PayPal checkout.",
        "PayPal 暂不支持购物车多币种同时结算。"
      );
    }
    if (!paypalCurrencySupported) {
      return t(lang, "PayPal currently supports USD/EUR checkout only.", "PayPal 当前仅支持 USD/EUR 结算。");
    }
    return null;
  }, [paymentMethod, requiredShippingMissing, countrySupported, mixedCurrencies, paypalCurrencySupported, lang]);

  const validateCheckout = useMemo(
    () => () => {
      if (!form.name || !form.email || !form.address || !form.city || !form.postalCode || !form.country) {
        setError(t(lang, "Please complete all required shipping fields.", "请填写完整收货信息。"));
        return false;
      }
      if (!countrySupported) {
        setError(
          t(
            lang,
            "This destination is not available yet. Please contact support for a manual shipping quote.",
            "当前目的地暂不支持自动下单，请联系客服人工确认运费。"
          )
        );
        return false;
      }
      if (mixedCurrencies) {
        setError(
          t(
            lang,
            "Mixed currencies in cart are not supported for PayPal checkout.",
            "PayPal 暂不支持购物车多币种同时结算。"
          )
        );
        return false;
      }
      if (paymentMethod === "paypal" && !paypalCurrencySupported) {
        setError(
          t(
            lang,
            "PayPal currently supports USD/EUR checkout only.",
            "PayPal 当前仅支持 USD/EUR 结算。"
          )
        );
        return false;
      }
      return true;
    },
    [
      countrySupported,
      form.address,
      form.city,
      form.country,
      form.email,
      form.name,
      form.postalCode,
      lang,
      mixedCurrencies,
      paymentMethod,
      paypalCurrencySupported,
    ]
  );

  const submitOrder = useCallback(
    async (
      method: "manual_contact" | "crypto_manual" | "paypal",
      paypalMeta?: { orderId: string; captureId: string; payerEmail?: string; status?: string }
    ) => {
      const res = await fetch("/api/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: form.email,
          shipping: form,
          items,
          total: subtotal,
          currency: summaryCurrency,
          paymentMethod: method,
          paypal: paypalMeta,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? t(lang, "Order failed", "订单提交失败"));
      clearCart();
      trackEvent("submit_order_success", {
        payment_method: method,
        value: subtotal,
        currency: summaryCurrency,
      });
      router.push(`/checkout/thank-you?orderId=${data.orderId ?? ""}&lang=${lang}&paymentMethod=${method}`);
    },
    [form, items, subtotal, summaryCurrency, lang, clearCart, router]
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (paymentMethod === "paypal") {
      setError(t(lang, "Please complete payment using the PayPal button below.", "请点击下方 PayPal 按钮完成支付。"));
      return;
    }
    if (!validateCheckout()) return;
    setLoading(true);
    trackEvent("submit_order_attempt", {
      payment_method: paymentMethod,
      value: subtotal,
      currency: summaryCurrency,
    });
    try {
      await submitOrder(paymentMethod);
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

  useEffect(() => {
    if (!mounted || paymentMethod !== "paypal") return;
    if (!paypalClientId) {
      setPaypalSdkError(
        t(
          lang,
          "PayPal is not configured yet. Please contact support.",
          "PayPal 尚未配置，请联系客服。"
        )
      );
      return;
    }

    let cancelled = false;
    const scriptId = "paypal-sdk-js";

    const renderButtons = () => {
      if (cancelled) return;
      const paypal = (window as typeof window & { paypal?: PayPalNamespace }).paypal;
      const container = paypalButtonsRef.current;
      if (!paypal || !container) return;
      container.innerHTML = "";
      setPaypalReady(false);
      paypal
        .Buttons({
          style: { layout: "vertical", shape: "rect", label: "paypal" },
          onClick: async (_data: unknown, actions: PayPalOnClickActions) => {
            setError(null);
            const formValid = checkoutFormRef.current?.reportValidity() ?? true;
            if (!formValid) {
              setError(
                t(
                  lang,
                  "Please complete required checkout fields before PayPal payment.",
                  "请先填写完整结账必填信息，再使用 PayPal 支付。"
                )
              );
              await actions.reject();
              return;
            }
            if (!validateCheckout()) {
              await actions.reject();
              return;
            }
            await actions.resolve();
          },
          createOrder: async () => {
            trackEvent("submit_order_attempt", {
              payment_method: "paypal",
              value: subtotal,
              currency: paypalCurrency,
            });
            const res = await fetch("/api/paypal/create-order", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ amount: subtotal, currency: paypalCurrency }),
            });
            const data = await res.json();
            if (!res.ok || !data.paypalOrderId) {
              throw new Error(data.error ?? "Failed to initialize PayPal");
            }
            return data.paypalOrderId;
          },
          onApprove: async (data: { orderID?: string }) => {
            setLoading(true);
            try {
              if (!data.orderID) throw new Error("Missing PayPal order ID");
              const captureRes = await fetch("/api/paypal/capture-order", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ paypalOrderId: data.orderID }),
              });
              const captureData = await captureRes.json();
              if (!captureRes.ok) {
                throw new Error(captureData.error ?? "Failed to capture PayPal payment");
              }
              await submitOrder("paypal", {
                orderId: captureData.orderId,
                captureId: captureData.captureId,
                payerEmail: captureData.payerEmail,
                status: captureData.status,
              });
            } catch (err) {
              setError(err instanceof Error ? err.message : "PayPal checkout failed");
            } finally {
              setLoading(false);
            }
          },
          onCancel: () => {
            setError(t(lang, "PayPal payment was cancelled.", "PayPal 支付已取消。"));
          },
          onError: () => {
            setError(t(lang, "PayPal failed to initialize. Try again later.", "PayPal 初始化失败，请稍后重试。"));
          },
        })
        .render(container)
        .then(() => {
          if (!cancelled) setPaypalReady(true);
        })
        .catch(() => {
          if (!cancelled) {
            setPaypalSdkError(
              t(lang, "PayPal button failed to render.", "PayPal 按钮渲染失败。")
            );
          }
        });
    };

    const existingScript = document.getElementById(scriptId) as HTMLScriptElement | null;
    const desiredSrc = `https://www.paypal.com/sdk/js?client-id=${encodeURIComponent(
      paypalClientId
    )}&currency=${encodeURIComponent(paypalCurrency)}&intent=capture`;

    if (existingScript && existingScript.src !== desiredSrc) {
      existingScript.remove();
    }
    const currentScript = (document.getElementById(scriptId) as HTMLScriptElement | null) ?? null;
    if (currentScript) {
      if ((window as typeof window & { paypal?: PayPalNamespace }).paypal) {
        renderButtons();
      } else {
        currentScript.addEventListener("load", renderButtons, { once: true });
      }
    } else {
      const script = document.createElement("script");
      script.id = scriptId;
      script.src = desiredSrc;
      script.async = true;
      script.onload = renderButtons;
      script.onerror = () => {
        if (!cancelled) {
          setPaypalSdkError(
            t(lang, "Failed to load PayPal SDK.", "加载 PayPal SDK 失败。")
          );
        }
      };
      document.body.appendChild(script);
    }

    return () => {
      cancelled = true;
    };
  }, [
    mounted,
    paymentMethod,
    paypalClientId,
    paypalCurrency,
    subtotal,
    validateCheckout,
    lang,
    paypalCurrencySupported,
    submitOrder,
  ]);
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
          "Displayed prices are final payable prices and include shipping.",
          "当前显示价格为最终应付价格，已包含运费。"
        )}
      </p>
      <form ref={checkoutFormRef} onSubmit={handleSubmit} className="mt-8 grid gap-8 lg:grid-cols-3">
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
                  {localizeProductName(item.name, item.slug, lang)} × {item.quantity}
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
            {t(lang, "Shipping is included in the amount above.", "运费已包含在上方金额中。")}
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
            <label className="mt-2 flex items-start gap-2 text-sm text-gray-700">
              <input
                type="radio"
                name="paymentMethod"
                value="paypal"
                checked={paymentMethod === "paypal"}
                onChange={() => setPaymentMethod("paypal")}
                className="mt-0.5"
                disabled={!paypalCurrencySupported}
              />
              <span>
                <span className="font-medium">PayPal</span>
                <span className="block text-xs text-gray-500">
                  {!paypalCurrencySupported
                    ? t(lang, "Unavailable for current currency.", "当前币种暂不支持 PayPal。")
                    : t(
                        lang,
                        "Pay now with PayPal. Order is confirmed immediately after successful payment.",
                        "使用 PayPal 立即支付，支付成功后自动确认订单。"
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
            {paymentMethod === "paypal" && (
              <div className="mt-3 space-y-2">
                <div ref={paypalButtonsRef} />
                {paypalValidationHint && (
                  <p className="text-xs text-amber-700">{paypalValidationHint}</p>
                )}
                {!paypalReady && !paypalSdkError && (
                  <p className="text-xs text-gray-500">
                    {t(lang, "Loading PayPal...", "正在加载 PayPal...")}
                  </p>
                )}
                {paypalSdkError && <p className="text-xs text-red-600">{paypalSdkError}</p>}
              </div>
            )}
          </div>
          {paymentMethod !== "paypal" && (
            <button
              type="submit"
              disabled={loading || !countrySupported}
              className="mt-6 w-full rounded bg-gray-900 py-3 font-medium text-white hover:bg-gray-800 disabled:opacity-70"
            >
              {loading ? t(lang, "Submitting…", "提交中…") : t(lang, "Submit order", "提交订单")}
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
