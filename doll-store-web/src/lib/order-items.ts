import type { CartItem } from "@/types";

export type OrderPaymentMethod = "manual_contact" | "crypto_manual";

export type OrderPaymentMeta = {
  txHash?: string;
  paidAmount?: number;
  paidAt?: string;
  network?: string;
  coin?: string;
};

export type OrderFulfillmentMeta = {
  carrier?: string;
  trackingNumber?: string;
  trackingUrl?: string;
  proofImages?: string[];
  proofVideos?: string[];
  shippedAt?: string;
  deliveredAt?: string;
};

export type OrderItemsPayload = {
  lines: CartItem[];
  paymentMethod: OrderPaymentMethod;
  payment?: OrderPaymentMeta;
  fulfillment?: OrderFulfillmentMeta;
  notes?: {
    customer?: string;
    admin?: string;
  };
};

export function normalizeOrderItems(raw: unknown): OrderItemsPayload {
  if (Array.isArray(raw)) {
    return {
      lines: raw as CartItem[],
      paymentMethod: "manual_contact",
    };
  }

  if (!raw || typeof raw !== "object") {
    return {
      lines: [],
      paymentMethod: "manual_contact",
    };
  }

  const value = raw as Partial<OrderItemsPayload> & { lines?: unknown };
  const lines = Array.isArray(value.lines) ? (value.lines as CartItem[]) : [];
  const paymentMethod = value.paymentMethod === "crypto_manual" ? "crypto_manual" : "manual_contact";

  return {
    lines,
    paymentMethod,
    payment: value.payment,
    fulfillment: value.fulfillment,
    notes: value.notes,
  };
}
