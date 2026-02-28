"use client";

import Link from "next/link";
import { useCart } from "@/context/CartContext";
import { useState } from "react";

export function Header() {
  const { totalItems } = useCart();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-gray-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <Link href="/" className="text-lg font-semibold text-gray-900">
          Doll Store
        </Link>
        <nav className="hidden items-center gap-6 md:flex">
          <Link
            href="/"
            className="text-sm text-gray-600 hover:text-gray-900"
          >
            Home
          </Link>
          <Link
            href="/products"
            className="text-sm text-gray-600 hover:text-gray-900"
          >
            Products
          </Link>
          <Link
            href="/cart"
            className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900"
          >
            Cart
            {totalItems > 0 && (
              <span className="rounded-full bg-gray-900 px-2 py-0.5 text-xs text-white">
                {totalItems}
              </span>
            )}
          </Link>
        </nav>
        <button
          type="button"
          className="md:hidden flex flex-col gap-1 p-2"
          onClick={() => setOpen((o) => !o)}
          aria-label="Menu"
        >
          <span className="h-0.5 w-5 bg-gray-700" />
          <span className="h-0.5 w-5 bg-gray-700" />
          <span className="h-0.5 w-5 bg-gray-700" />
        </button>
      </div>
      {open && (
        <div className="border-t border-gray-200 bg-white px-4 py-3 md:hidden">
          <Link
            href="/"
            className="block py-2 text-gray-600"
            onClick={() => setOpen(false)}
          >
            Home
          </Link>
          <Link
            href="/products"
            className="block py-2 text-gray-600"
            onClick={() => setOpen(false)}
          >
            Products
          </Link>
          <Link
            href="/cart"
            className="block py-2 text-gray-600"
            onClick={() => setOpen(false)}
          >
            Cart {totalItems > 0 && `(${totalItems})`}
          </Link>
        </div>
      )}
    </header>
  );
}
