const PAYPAL_BASE = "https://api-m.paypal.com";
const PAYPAL_SANDBOX_BASE = "https://api-m.sandbox.paypal.com";

function getPaypalConfig() {
  const clientId = process.env.NEXT_PUBLIC_PAYPAL_CLIENT_ID;
  const clientSecret = process.env.PAYPAL_CLIENT_SECRET;
  const env = process.env.PAYPAL_ENV === "live" ? "live" : "sandbox";
  if (!clientId || !clientSecret) {
    throw new Error("PayPal is not configured");
  }
  return {
    clientId,
    clientSecret,
    baseUrl: env === "live" ? PAYPAL_BASE : PAYPAL_SANDBOX_BASE,
  };
}

async function getAccessToken(): Promise<{ accessToken: string; baseUrl: string }> {
  const { clientId, clientSecret, baseUrl } = getPaypalConfig();
  const auth = Buffer.from(`${clientId}:${clientSecret}`).toString("base64");
  const res = await fetch(`${baseUrl}/v1/oauth2/token`, {
    method: "POST",
    headers: {
      Authorization: `Basic ${auth}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: "grant_type=client_credentials",
    cache: "no-store",
  });
  const data = (await res.json()) as { access_token?: string; error_description?: string };
  if (!res.ok || !data.access_token) {
    throw new Error(data.error_description ?? "Failed to get PayPal access token");
  }
  return { accessToken: data.access_token, baseUrl };
}

export async function createPaypalOrder(input: {
  amount: number;
  currency: "USD" | "EUR" | "CNY";
  referenceId?: string;
}) {
  const { accessToken, baseUrl } = await getAccessToken();
  const value = input.amount.toFixed(2);
  const res = await fetch(`${baseUrl}/v2/checkout/orders`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
      Prefer: "return=representation",
    },
    body: JSON.stringify({
      intent: "CAPTURE",
      purchase_units: [
        {
          reference_id: input.referenceId ?? `order-${Date.now()}`,
          amount: {
            currency_code: input.currency,
            value,
          },
        },
      ],
      application_context: {
        brand_name: process.env.PAYPAL_BRAND_NAME ?? "RealDollHub",
        shipping_preference: "NO_SHIPPING",
        user_action: "PAY_NOW",
      },
    }),
    cache: "no-store",
  });
  const data = (await res.json()) as { id?: string; message?: string };
  if (!res.ok || !data.id) {
    throw new Error(data.message ?? "Failed to create PayPal order");
  }
  return data;
}

export async function capturePaypalOrder(orderId: string) {
  const { accessToken, baseUrl } = await getAccessToken();
  const res = await fetch(`${baseUrl}/v2/checkout/orders/${orderId}/capture`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
      Prefer: "return=representation",
    },
    cache: "no-store",
  });
  const data = (await res.json()) as {
    id?: string;
    status?: string;
    payer?: { email_address?: string };
    purchase_units?: Array<{
      payments?: {
        captures?: Array<{ id?: string; status?: string }>;
      };
    }>;
    message?: string;
  };
  if (!res.ok) {
    throw new Error(data.message ?? "Failed to capture PayPal order");
  }
  const capture = data.purchase_units?.[0]?.payments?.captures?.[0];
  return {
    orderId: data.id ?? orderId,
    status: data.status ?? capture?.status ?? "UNKNOWN",
    captureId: capture?.id ?? "",
    payerEmail: data.payer?.email_address,
  };
}
