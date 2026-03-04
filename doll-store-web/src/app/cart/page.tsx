"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useCart } from "@/context/CartContext";
import { formatMoney } from "@/lib/money";

export default function CartPage() {
  const { items, updateQuantity, removeItem, subtotal, totalItems } = useCart();
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setMounted(true), 0);
    return () => clearTimeout(timer);
  }, []);

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
        <h1 className="text-2xl font-bold text-gray-900">Your cart is empty</h1>
        <Link
          href="/products"
          className="mt-4 inline-block text-gray-600 underline hover:text-gray-900"
        >
          Continue shopping
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="text-2xl font-bold text-gray-900">Cart ({totalItems} items)</h1>
      <div className="mt-8 grid gap-8 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ul className="divide-y divide-gray-200">
            {items.map((item) => (
              <li key={item.productId} className="flex gap-4 py-6">
                <div className="relative h-24 w-24 flex-shrink-0 overflow-hidden rounded bg-gray-100">
                  {item.image ? (
                    <Image
                      src={item.image}
                      alt={item.name}
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
                      href={`/product/${item.slug}`}
                      className="font-medium text-gray-900 hover:underline"
                    >
                      {item.name}
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
                      Remove
                    </button>
                  </div>
                </div>
                <div className="text-right font-medium">
                  {formatMoney(item.price * item.quantity, item.currency ?? "CNY")}
                </div>
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-6">
          <h2 className="font-semibold text-gray-900">Order summary</h2>
          <p className="mt-2 text-gray-600">
            Subtotal: <span className="font-medium">{formatMoney(subtotal, "CNY")}</span>
          </p>
          <p className="mt-1 text-sm text-gray-500">
            Factory prices shown. International freight will be quoted after destination confirmation.
          </p>
          <Link
            href="/checkout"
            className="mt-6 block w-full rounded bg-gray-900 py-3 text-center font-medium text-white hover:bg-gray-800"
          >
            Proceed to checkout
          </Link>
          <Link
            href="/products"
            className="mt-4 block text-center text-sm text-gray-600 hover:text-gray-900"
          >
            Continue shopping
          </Link>
        </div>
      </div>
    </div>
  );
}
