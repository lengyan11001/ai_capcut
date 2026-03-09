"use client";

import Script from "next/script";
import { useEffect, useMemo, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { ANALYTICS_COOKIE_NAME } from "@/components/CookieConsentBanner";

function getConsentFromCookie() {
  if (typeof document === "undefined") return false;
  const row = document.cookie
    .split("; ")
    .find((entry) => entry.startsWith(`${ANALYTICS_COOKIE_NAME}=`));
  if (!row) return false;
  return row.split("=")[1] === "yes";
}

export function AnalyticsScripts() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [enabled, setEnabled] = useState(false);
  const gaId = process.env.NEXT_PUBLIC_GA4_ID ?? "";
  const clarityId = process.env.NEXT_PUBLIC_CLARITY_ID ?? "";
  const query = useMemo(() => searchParams.toString(), [searchParams]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setEnabled(getConsentFromCookie());
    }, 0);
    const onUpdate = () => setEnabled(getConsentFromCookie());
    window.addEventListener("analytics-consent-updated", onUpdate as EventListener);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("analytics-consent-updated", onUpdate as EventListener);
    };
  }, []);

  useEffect(() => {
    if (!enabled || !gaId) return;
    const gtag = (window as typeof window & { gtag?: (...args: unknown[]) => void }).gtag;
    if (typeof gtag !== "function") return;
    const pagePath = query ? `${pathname}?${query}` : pathname;
    gtag("event", "page_view", { page_path: pagePath });
  }, [enabled, gaId, pathname, query]);

  if (!enabled) return null;

  return (
    <>
      {gaId ? (
        <>
          <Script src={`https://www.googletagmanager.com/gtag/js?id=${gaId}`} strategy="afterInteractive" />
          <Script id="ga4-init" strategy="afterInteractive">
            {`
              window.dataLayer = window.dataLayer || [];
              function gtag(){dataLayer.push(arguments);}
              window.gtag = gtag;
              gtag('js', new Date());
              gtag('config', '${gaId}', { send_page_view: true });
            `}
          </Script>
        </>
      ) : null}
      {clarityId ? (
        <Script id="clarity-init" strategy="afterInteractive">
          {`
            (function(c,l,a,r,i,t,y){
                c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};
                t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
                y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
            })(window, document, "clarity", "script", "${clarityId}");
          `}
        </Script>
      ) : null}
    </>
  );
}
