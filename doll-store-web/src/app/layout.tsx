import type { Metadata } from "next";
import "./globals.css";
import { CartProvider } from "@/context/CartContext";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { SupportWidget } from "@/components/SupportWidget";
import { Suspense } from "react";

export const metadata: Metadata = {
  title: "Doll Store | Premium Collectibles",
  description: "Shop full body dolls, TPE and silicone collectibles. Discreet packaging, secure delivery.",
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
            <SupportWidget />
          </Suspense>
          <Footer />
        </CartProvider>
      </body>
    </html>
  );
}
