import Link from "next/link";
import { normalizeLang, t } from "@/lib/i18n";

export default async function ThankYouPage({
  searchParams,
}: {
  searchParams: Promise<{ orderId?: string; lang?: string; paymentMethod?: string }>;
}) {
  const params = await searchParams;
  const orderId = params.orderId ?? "";
  const lang = normalizeLang(params.lang);
  const paymentMethod =
    params.paymentMethod === "crypto_manual"
      ? "crypto_manual"
      : params.paymentMethod === "paypal"
        ? "paypal"
        : "manual_contact";
  const cryptoAddress = process.env.CRYPTO_PAY_ADDRESS;
  const cryptoNetwork = process.env.CRYPTO_PAY_NETWORK ?? "TRON (TRC20)";
  const cryptoCoin = process.env.CRYPTO_PAY_COIN ?? "USDT";
  const supportWhatsapp = process.env.NEXT_PUBLIC_SUPPORT_WHATSAPP;
  const supportTelegram = process.env.NEXT_PUBLIC_SUPPORT_TELEGRAM;
  const productsHref = `/products?lang=${lang}`;

  return (
    <div className="mx-auto max-w-2xl px-4 py-16 text-center">
      <h1 className="text-2xl font-bold text-gray-900">
        {t(lang, "Thank you for your order", "感谢你的订单")}
      </h1>
      <p className="mt-4 text-gray-600">
        {paymentMethod === "crypto_manual"
          ? t(
              lang,
              "Order received. Please complete crypto transfer using the details below, then contact support for confirmation.",
              "订单已收到。请按下方信息完成加密货币转账，并联系客服确认到账。"
            )
          : paymentMethod === "paypal"
            ? t(
                lang,
                "PayPal payment completed successfully. We will now process your order.",
                "PayPal 支付已完成，我们将开始处理你的订单。"
              )
            : t(
              lang,
              "We’ve received your order and will contact you shortly for secure payment and shipping details.",
              "我们已收到订单，将尽快联系你确认支付与发货细节。"
            )}
      </p>
      {orderId && (
        <p className="mt-2 text-sm text-gray-500">{t(lang, "Order reference:", "订单编号:")} {orderId}</p>
      )}
      {paymentMethod === "crypto_manual" && (
        <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-4 text-left">
          <p className="text-sm font-semibold text-amber-900">{t(lang, "Crypto payment details", "加密支付信息")}</p>
          {cryptoAddress ? (
            <ul className="mt-2 space-y-1 text-sm text-amber-900">
              <li>{t(lang, "Coin:", "币种:")} {cryptoCoin}</li>
              <li>{t(lang, "Network:", "网络:")} {cryptoNetwork}</li>
              <li className="break-all">
                {t(lang, "Address:", "地址:")} {cryptoAddress}
              </li>
              {orderId && (
                <li>{t(lang, "Memo/Note:", "转账备注:")} {orderId}</li>
              )}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-amber-900">
              {t(
                lang,
                "Crypto wallet details are not configured yet. Please contact support to get the payment address.",
                "当前未配置加密钱包信息，请联系客服获取收款地址。"
              )}
            </p>
          )}
        </div>
      )}
      {(supportWhatsapp || supportTelegram) && (
        <div className="mx-auto mt-6 max-w-xl rounded-lg border border-gray-200 bg-gray-50 p-4 text-left">
          <p className="text-sm font-medium text-gray-900">{t(lang, "Private support channel", "私域客服通道")}</p>
          <p className="mt-1 text-sm text-gray-600">
            {t(
              lang,
              "Share your order reference for faster confirmation and shipping follow-up.",
              "发送订单编号可更快完成支付确认和发货跟进。"
            )}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {supportWhatsapp ? (
              <a
                href={supportWhatsapp.startsWith("http") ? supportWhatsapp : `https://wa.me/${supportWhatsapp}`}
                target="_blank"
                rel="noreferrer"
                className="rounded border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700"
              >
                WhatsApp
              </a>
            ) : null}
            {supportTelegram ? (
              <a
                href={supportTelegram.startsWith("http") ? supportTelegram : `https://t.me/${supportTelegram.replace(/^@/, "")}`}
                target="_blank"
                rel="noreferrer"
                className="rounded border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700"
              >
                Telegram
              </a>
            ) : null}
          </div>
        </div>
      )}
      <Link
        href={productsHref}
        className="mt-8 inline-block rounded bg-gray-900 px-6 py-3 text-white hover:bg-gray-800"
      >
        {t(lang, "Continue shopping", "继续购物")}
      </Link>
    </div>
  );
}
