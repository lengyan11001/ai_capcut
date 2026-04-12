import type { Metadata } from "next";
import "./globals.css";
import { CartProvider } from "@/context/CartContext";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { SupportWidget } from "@/components/SupportWidget";
import { AnalyticsScripts } from "@/components/AnalyticsScripts";
import { CookieConsentBanner } from "@/components/CookieConsentBanner";
import { AgeGate } from "@/components/AgeGate";
import { Suspense } from "react";

export const metadata: Metadata = {
  title: "Doll Store | Premium Collectibles",
  description: "Premium silicone dolls and collectibles. Discreet packaging, secure delivery.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="flex min-h-screen flex-col bg-white text-gray-900 antialiased">
        <CartProvider>
          <Suspense fallback={<div className="h-14 border-b border-gray-200 bg-white" />}>
            <Header />
          </Suspense>
          <main className="flex-1">{children}</main>
          <Suspense fallback={null}>
            <AnalyticsScripts />
          </Suspense>
          <AgeGate />
          <CookieConsentBanner />
          <Suspense fallback={null}>
            <SupportWidget />
          </Suspense>
          <Footer />
        </CartProvider>
      </body>
    </html>
  );
}
