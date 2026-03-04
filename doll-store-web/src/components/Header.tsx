"use client";

import Link from "next/link";
import { useCart } from "@/context/CartContext";
import { useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import type { Lang } from "@/lib/i18n";
import { normalizeLang, t } from "@/lib/i18n";

export function Header() {
  const { totalItems } = useCart();
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const lang = normalizeLang(searchParams.get("lang"));

  const buildHref = (path: string, nextLang?: Lang) => {
    const qs = new URLSearchParams();
    const debugRegion = searchParams.get("debug_region");
    const debugAll = searchParams.get("debug_all");
    if (debugRegion) qs.set("debug_region", debugRegion);
    if (debugAll) qs.set("debug_all", debugAll);
    qs.set("lang", nextLang ?? lang);
    const query = qs.toString();
    return query ? `${path}?${query}` : path;
  };

  const langSwitchHref = (nextLang: Lang) => buildHref(pathname || "/", nextLang);

  return (
    <header className="sticky top-0 z-50 border-b border-gray-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <Link href={buildHref("/")} className="text-lg font-semibold text-gray-900">
          Doll Store
        </Link>
        <nav className="hidden items-center gap-6 md:flex">
          <Link href={buildHref("/")} className="text-sm text-gray-600 hover:text-gray-900">
            {t(lang, "Home", "首页")}
          </Link>
          <Link href={buildHref("/products")} className="text-sm text-gray-600 hover:text-gray-900">
            {t(lang, "Products", "商品")}
          </Link>
          <Link href={buildHref("/guides")} className="text-sm text-gray-600 hover:text-gray-900">
            {t(lang, "Guides", "指南")}
          </Link>
          <Link href={buildHref("/orders")} className="text-sm text-gray-600 hover:text-gray-900">
            {t(lang, "Track order", "订单查询")}
          </Link>
          <Link
            href={buildHref("/cart")}
            className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900"
          >
            {t(lang, "Cart", "购物车")}
            {totalItems > 0 && (
              <span className="rounded-full bg-gray-900 px-2 py-0.5 text-xs text-white">
                {totalItems}
              </span>
            )}
          </Link>
          <div className="flex items-center gap-2 rounded border border-gray-200 px-2 py-1 text-xs">
            <Link
              href={langSwitchHref("en")}
              className={lang === "en" ? "font-semibold text-gray-900" : "text-gray-500 hover:text-gray-700"}
            >
              EN
            </Link>
            <span className="text-gray-300">|</span>
            <Link
              href={langSwitchHref("zh")}
              className={lang === "zh" ? "font-semibold text-gray-900" : "text-gray-500 hover:text-gray-700"}
            >
              中文
            </Link>
          </div>
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
            href={buildHref("/")}
            className="block py-2 text-gray-600"
            onClick={() => setOpen(false)}
          >
            {t(lang, "Home", "首页")}
          </Link>
          <Link
            href={buildHref("/products")}
            className="block py-2 text-gray-600"
            onClick={() => setOpen(false)}
          >
            {t(lang, "Products", "商品")}
          </Link>
          <Link
            href={buildHref("/guides")}
            className="block py-2 text-gray-600"
            onClick={() => setOpen(false)}
          >
            {t(lang, "Guides", "指南")}
          </Link>
          <Link
            href={buildHref("/cart")}
            className="block py-2 text-gray-600"
            onClick={() => setOpen(false)}
          >
            {t(lang, "Cart", "购物车")} {totalItems > 0 && `(${totalItems})`}
          </Link>
          <Link
            href={buildHref("/orders")}
            className="block py-2 text-gray-600"
            onClick={() => setOpen(false)}
          >
            {t(lang, "Track order", "订单查询")}
          </Link>
          <div className="mt-2 flex items-center gap-3 text-sm">
            <Link href={langSwitchHref("en")} className={lang === "en" ? "font-semibold text-gray-900" : "text-gray-500"}>
              EN
            </Link>
            <Link href={langSwitchHref("zh")} className={lang === "zh" ? "font-semibold text-gray-900" : "text-gray-500"}>
              中文
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
