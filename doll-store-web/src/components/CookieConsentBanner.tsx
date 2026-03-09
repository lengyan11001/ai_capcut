"use client";

import { useEffect, useState } from "react";
import { normalizeLang, t } from "@/lib/i18n";

export const ANALYTICS_COOKIE_NAME = "cookie_analytics_consent";

export function CookieConsentBanner() {
  const [visible, setVisible] = useState(false);
  const [lang, setLang] = useState<"en" | "zh">("en");

  useEffect(() => {
    const timer = setTimeout(() => {
      const params = new URLSearchParams(window.location.search);
      setLang(normalizeLang(params.get("lang")));
      const hasConsent = document.cookie.split("; ").some((entry) => entry.startsWith(`${ANALYTICS_COOKIE_NAME}=`));
      if (!hasConsent) setVisible(true);
    }, 0);
    return () => clearTimeout(timer);
  }, []);

  const setConsent = (value: "yes" | "no") => {
    document.cookie = `${ANALYTICS_COOKIE_NAME}=${value}; path=/; max-age=${60 * 60 * 24 * 365}; samesite=lax`;
    setVisible(false);
    window.dispatchEvent(new CustomEvent("analytics-consent-updated"));
  };

  if (!visible) return null;

  return (
    <div className="fixed inset-x-0 bottom-0 z-[120] border-t border-gray-200 bg-white/95 p-4 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-gray-700">
          {t(
            lang,
            "We use analytics cookies to understand traffic sources and browsing behavior.",
            "我们使用统计 Cookie 来分析访客来源与浏览行为。"
          )}
        </p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setConsent("no")}
            className="rounded border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
          >
            {t(lang, "Reject", "拒绝")}
          </button>
          <button
            type="button"
            onClick={() => setConsent("yes")}
            className="rounded bg-gray-900 px-3 py-2 text-sm text-white hover:bg-gray-800"
          >
            {t(lang, "Accept", "同意")}
          </button>
        </div>
      </div>
    </div>
  );
}
