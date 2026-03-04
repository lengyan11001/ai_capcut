import { getLangFromSearchParams } from "@/lib/i18n";
import OrdersLookupClient from "./OrdersLookupClient";

export default async function OrdersPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const lang = getLangFromSearchParams(params);
  return <OrdersLookupClient lang={lang} />;
}
