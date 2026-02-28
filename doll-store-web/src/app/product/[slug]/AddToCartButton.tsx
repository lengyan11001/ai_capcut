"use client";

import { useCart } from "@/context/CartContext";
import { useState } from "react";

interface Props {
  productId: string;
  slug: string;
  name: string;
  price: number;
  image?: string;
}

export function AddToCartButton({ productId, slug, name, price, image }: Props) {
  const { addItem } = useCart();
  const [added, setAdded] = useState(false);

  const handleClick = () => {
    addItem({ productId, slug, name, price, image });
    setAdded(true);
    setTimeout(() => setAdded(false), 2000);
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      className="w-full rounded bg-gray-900 px-6 py-3 font-medium text-white hover:bg-gray-800 disabled:opacity-70 sm:w-auto"
    >
      {added ? "Added to cart" : "Add to cart"}
    </button>
  );
}
