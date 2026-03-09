"use client";

import { useEffect, useState } from "react";
import { normalizeLang, t } from "@/lib/i18n";

const AGE_COOKIE = "age_verified";

export function AgeGate() {
  const enabled = process.env.NEXT_PUBLIC_ENABLE_AGE_GATE !== "false";
  const [show, setShow] = useState(false);
  const [lang, setLang] = useState<"en" | "zh">("en");

  useEffect(() => {
    if (!enabled) return;
    const timer = setTimeout(() => {
      const params = new URLSearchParams(window.location.search);
      setLang(normalizeLang(params.get("lang")));
      const hasVerified = document.cookie.split("; ").some((entry) => entry.startsWith(`${AGE_COOKIE}=1`));
      if (!hasVerified) setShow(true);
    }, 0);
    return () => clearTimeout(timer);
  }, [enabled]);

  if (!enabled || !show) return null;

  const onAccept = () => {
    document.cookie = `${AGE_COOKIE}=1; path=/; max-age=${60 * 60 * 24 * 365}; samesite=lax`;
    setShow(false);
  };

  const onReject = () => {
    window.location.href = "https://www.google.com";
  };

  return (
    <div className="fixed inset-0 z-[130] flex items-center justify-center bg-black/70 px-4">
      <div className="w-full max-w-md rounded-xl bg-white p-6 text-center shadow-xl">
        <h2 className="text-xl font-semibold text-gray-900">{t(lang, "Age Verification", "年龄验证")}</h2>
        <p className="mt-3 text-sm text-gray-600">
          {t(lang, "You must be 18+ to enter this site.", "你必须年满 18 岁才能访问本网站。")}
        </p>
        <div className="mt-5 flex items-center justify-center gap-3">
          <button
            type="button"
            onClick={onReject}
            className="rounded border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
          >
            {t(lang, "I am under 18", "未满18岁")}
          </button>
          <button
            type="button"
            onClick={onAccept}
            className="rounded bg-gray-900 px-4 py-2 text-sm text-white hover:bg-gray-800"
          >
            {t(lang, "I am 18+", "我已满18岁")}
          </button>
        </div>
      </div>
    </div>
  );
}
