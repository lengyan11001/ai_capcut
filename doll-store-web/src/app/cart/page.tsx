"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useCart } from "@/context/CartContext";
import { formatMoney } from "@/lib/money";
import { normalizeLang, t, type Lang } from "@/lib/i18n";
import { localizeProductName } from "@/lib/product-copy";

export default function CartPage() {
  const { items, updateQuantity, removeItem, subtotal, totalItems } = useCart();
  const [mounted, setMounted] = useState(false);
  const [lang, setLang] = useState<Lang>("en");
  const summaryCurrency = (items[0]?.currency ?? "CNY") as "CNY" | "USD" | "EUR";
  const mixedCurrencies = items.some((item) => (item.currency ?? "CNY") !== summaryCurrency);
  useEffect(() => {
    const timer = setTimeout(() => {
      setMounted(true);
      setLang(normalizeLang(new URLSearchParams(window.location.search).get("lang")));
    }, 0);
    return () => clearTimeout(timer);
  }, []);
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
        <Link
          href={withLang("/products")}
          className="mt-4 inline-block text-gray-600 underline hover:text-gray-900"
        >
          {t(lang, "Continue shopping", "继续购物")}
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="text-2xl font-bold text-gray-900">
        {t(lang, "Cart", "购物车")} ({totalItems} {t(lang, "items", "件")})
      </h1>
      <div className="mt-8 grid gap-8 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ul className="divide-y divide-gray-200">
            {items.map((item) => {
              const localizedName = localizeProductName(item.name, item.slug, lang);
              return (
              <li key={item.productId} className="flex gap-4 py-6">
                <div className="relative h-24 w-24 flex-shrink-0 overflow-hidden rounded bg-gray-100">
                  {item.image ? (
                    <Image
                      src={item.image}
                      alt={localizedName}
                      fill
                      className="object-cover"
                      unoptimized={
                        item.image.startsWith("https://placehold.co") ||
                        item.image.startsWith("/api/image-proxy")
                      }
                    />
                  ) : null}
                </div>
                <div className="flex flex-1 flex-col justify-between">
                  <div>
                    <Link
                      href={`/product/${item.slug}?lang=${lang}`}
                      className="font-medium text-gray-900 hover:underline"
                    >
                      {localizedName}
                    </Link>
                    <p className="text-sm text-gray-500">
                      {formatMoney(item.price, item.currency ?? "CNY")}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => updateQuantity(item.productId, item.quantity - 1)}
                      className="rounded border border-gray-300 px-2 py-1 text-sm hover:bg-gray-50"
                    >
                      −
                    </button>
                    <span className="w-8 text-center text-sm">{item.quantity}</span>
                    <button
                      type="button"
                      onClick={() => updateQuantity(item.productId, item.quantity + 1)}
                      className="rounded border border-gray-300 px-2 py-1 text-sm hover:bg-gray-50"
                    >
                      +
                    </button>
                    <button
                      type="button"
                      onClick={() => removeItem(item.productId)}
                      className="ml-2 text-sm text-red-600 hover:underline"
                    >
                      {t(lang, "Remove", "删除")}
                    </button>
                  </div>
                </div>
                <div className="text-right font-medium">
                  {formatMoney(item.price * item.quantity, item.currency ?? "CNY")}
                </div>
              </li>
              );
            })}
          </ul>
        </div>
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-6">
          <h2 className="font-semibold text-gray-900">{t(lang, "Order summary", "订单摘要")}</h2>
          <p className="mt-2 text-gray-600">
            {t(lang, "Subtotal:", "小计:")}{" "}
            <span className="font-medium">
              {mixedCurrencies
                ? t(lang, "Mixed currencies in cart", "购物车存在多币种")
                : formatMoney(subtotal, summaryCurrency)}
            </span>
          </p>
          <p className="mt-1 text-sm text-gray-500">
            {t(
              lang,
              "Factory prices shown. International freight will be quoted after destination confirmation.",
              "当前显示工厂价格，国际运费将在确认目的地后单独报价。"
            )}
          </p>
          <Link
            href={withLang("/checkout")}
            className="mt-6 block w-full rounded bg-gray-900 py-3 text-center font-medium text-white hover:bg-gray-800"
          >
            {t(lang, "Proceed to checkout", "去结账")}
          </Link>
          <Link
            href={withLang("/products")}
            className="mt-4 block text-center text-sm text-gray-600 hover:text-gray-900"
          >
            {t(lang, "Continue shopping", "继续购物")}
          </Link>
        </div>
      </div>
    </div>
  );
}
