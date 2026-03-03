export function formatMoney(
  amount: number,
  currency: "CNY" | "USD" | "EUR" = "CNY"
) {
  if (currency === "USD") return `$${amount.toLocaleString()}`;
  if (currency === "EUR") return `€${amount.toLocaleString()}`;
  return `¥${amount.toLocaleString()}`;
}

