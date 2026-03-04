"use client";

import { useMemo, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { normalizeLang, t } from "@/lib/i18n";

function buildWhatsappUrl(input?: string) {
  if (!input) return "";
  if (input.startsWith("http://") || input.startsWith("https://")) return input;
  const digits = input.replace(/[^\d]/g, "");
  return digits ? `https://wa.me/${digits}` : "";
}

function buildTelegramUrl(input?: string) {
  if (!input) return "";
  if (input.startsWith("http://") || input.startsWith("https://")) return input;
  const clean = input.replace(/^@/, "");
  return clean ? `https://t.me/${clean}` : "";
}

export function SupportWidget() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [open, setOpen] = useState(false);
  const lang = normalizeLang(searchParams.get("lang"));

  const whatsapp = buildWhatsappUrl(process.env.NEXT_PUBLIC_SUPPORT_WHATSAPP);
  const telegram = buildTelegramUrl(process.env.NEXT_PUBLIC_SUPPORT_TELEGRAM);
  const email = process.env.NEXT_PUBLIC_SUPPORT_EMAIL ?? "";
  const emailHref = email ? `mailto:${email}` : "";

  const links = useMemo(
    () =>
      [
        whatsapp ? { key: "wa", label: "WhatsApp", href: whatsapp } : null,
        telegram ? { key: "tg", label: "Telegram", href: telegram } : null,
        emailHref ? { key: "mail", label: "Email", href: emailHref } : null,
      ].filter(Boolean) as Array<{ key: string; label: string; href: string }>,
    [whatsapp, telegram, emailHref]
  );

  if (pathname?.startsWith("/admin")) return null;
  if (links.length === 0) return null;

  return (
    <div className="fixed bottom-5 right-5 z-[90]">
      {open && (
        <div className="mb-2 w-56 rounded-lg border border-gray-200 bg-white p-3 shadow-lg">
          <p className="text-sm font-medium text-gray-800">{t(lang, "Need help?", "需要帮助？")}</p>
          <div className="mt-2 space-y-2">
            {links.map((link) => (
              <a
                key={link.key}
                href={link.href}
                target={link.href.startsWith("mailto:") ? undefined : "_blank"}
                rel={link.href.startsWith("mailto:") ? undefined : "noreferrer"}
                className="block rounded border border-gray-200 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
              >
                {link.label}
              </a>
            ))}
          </div>
        </div>
      )}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="rounded-full bg-gray-900 px-4 py-3 text-sm font-medium text-white shadow-lg hover:bg-gray-800"
      >
        {open ? t(lang, "Close", "关闭") : t(lang, "Chat", "咨询")}
      </button>
    </div>
  );
}
