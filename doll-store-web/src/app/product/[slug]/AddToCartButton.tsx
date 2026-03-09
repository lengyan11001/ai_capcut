"use client";

import { useCart } from "@/context/CartContext";
import { useState } from "react";
import type { Lang } from "@/lib/i18n";
import { t } from "@/lib/i18n";
import { trackEvent } from "@/lib/analytics";

interface Props {
  productId: string;
  slug: string;
  name: string;
  price: number;
  currency?: "CNY" | "USD" | "EUR";
  image?: string;
  lang?: Lang;
}

export function AddToCartButton({ productId, slug, name, price, currency, image, lang = "en" }: Props) {
  const { addItem } = useCart();
  const [added, setAdded] = useState(false);

  const handleClick = () => {
    addItem({ productId, slug, name, price, currency, image });
    trackEvent("add_to_cart", {
      item_id: slug,
      item_name: name,
      value: price,
      currency: currency ?? "CNY",
    });
    setAdded(true);
    setTimeout(() => setAdded(false), 2000);
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      className="w-full rounded bg-gray-900 px-6 py-3 font-medium text-white hover:bg-gray-800 disabled:opacity-70 sm:w-auto"
    >
      {added ? t(lang, "Added to cart", "已加入购物车") : t(lang, "Add to cart", "加入购物车")}
    </button>
  );
}
