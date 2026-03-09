"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { Lang } from "@/lib/i18n";
import { normalizeLang, t } from "@/lib/i18n";

export function Footer() {
  const [lang, setLang] = useState<Lang>("en");

  useEffect(() => {
    const timer = setTimeout(() => {
      const params = new URLSearchParams(window.location.search);
      setLang(normalizeLang(params.get("lang")));
    }, 0);
    return () => clearTimeout(timer);
  }, []);

  const withLang = useMemo(
    () => (path: string) => `${path}?lang=${lang}`,
    [lang]
  );

  return (
    <footer className="mt-auto border-t border-gray-200 bg-gray-50">
      <div className="mx-auto max-w-6xl px-4 py-10">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <h3 className="font-semibold text-gray-900">{t(lang, "Shop", "商城")}</h3>
            <ul className="mt-3 space-y-2">
              <li>
                <Link href={withLang("/products")} className="text-gray-600 hover:text-gray-900">
                  {t(lang, "All Products", "全部商品")}
                </Link>
              </li>
              <li>
                <Link href={withLang("/guides")} className="text-gray-600 hover:text-gray-900">
                  {t(lang, "Buying Guides", "选购指南")}
                </Link>
              </li>
              <li>
                <Link href={withLang("/category/full-body")} className="text-gray-600 hover:text-gray-900">
                  {t(lang, "Full Body", "全身款")}
                </Link>
              </li>
              <li>
                <Link href={withLang("/category/tpe")} className="text-gray-600 hover:text-gray-900">
                  {t(lang, "TPE Dolls", "TPE 娃娃")}
                </Link>
              </li>
              <li>
                <Link href={withLang("/category/silicone")} className="text-gray-600 hover:text-gray-900">
                  {t(lang, "Silicone", "硅胶款")}
                </Link>
              </li>
              <li>
                <Link href={withLang("/category/accessories")} className="text-gray-600 hover:text-gray-900">
                  {t(lang, "Accessories", "配件")}
                </Link>
              </li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">{t(lang, "Info", "信息")}</h3>
            <ul className="mt-3 space-y-2">
              <li>
                <Link href={withLang("/about")} className="text-gray-600 hover:text-gray-900">
                  {t(lang, "About Us", "关于我们")}
                </Link>
              </li>
              <li>
                <Link href={withLang("/shipping")} className="text-gray-600 hover:text-gray-900">
                  {t(lang, "Shipping & Delivery", "物流与配送")}
                </Link>
              </li>
              <li>
                <Link href={withLang("/guides/how-to-choose-first-doll")} className="text-gray-600 hover:text-gray-900">
                  {t(lang, "First Purchase Guide", "首次购买指南")}
                </Link>
              </li>
              <li>
                <Link href={withLang("/contact")} className="text-gray-600 hover:text-gray-900">
                  {t(lang, "Contact", "联系我们")}
                </Link>
              </li>
              <li>
                <Link href={withLang("/shipping-proof")} className="text-gray-600 hover:text-gray-900">
                  {t(lang, "Shipping Proof", "发货实拍")}
                </Link>
              </li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">{t(lang, "Legal", "法律信息")}</h3>
            <ul className="mt-3 space-y-2">
              <li>
                <Link href={withLang("/privacy")} className="text-gray-600 hover:text-gray-900">
                  {t(lang, "Privacy Policy", "隐私政策")}
                </Link>
              </li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">{t(lang, "Trust", "信任保障")}</h3>
            <p className="mt-3 text-sm text-gray-600">
              {t(
                lang,
                "Discreet packaging. Secure checkout. We’ll contact you for secure payment after order confirmation.",
                "隐私包装，安全下单。订单确认后我们会联系你完成安全支付。"
              )}
            </p>
          </div>
        </div>
        <p className="mt-8 border-t border-gray-200 pt-6 text-center text-sm text-gray-500">
          © {new Date().getFullYear()} Doll Store. {t(lang, "All rights reserved.", "保留所有权利。")}
        </p>
      </div>
    </footer>
  );
}
