"use client";

import { useState } from "react";

type Props = {
  id: string;
  initialStatus: string;
  initialCarrier: string;
  initialTrackingNumber: string;
  initialTrackingUrl: string;
  initialAdminNote: string;
  initialTxHash: string;
  initialPaidAmount: string;
};

const STATUS_OPTIONS = [
  "pending",
  "pending_crypto",
  "payment_received",
  "paid",
  "packed",
  "shipped",
  "delivered",
  "completed",
  "cancelled",
  "refund_pending",
  "refunded",
];

export default function OrderEditorForm({
  id,
  initialStatus,
  initialCarrier,
  initialTrackingNumber,
  initialTrackingUrl,
  initialAdminNote,
  initialTxHash,
  initialPaidAmount,
}: Props) {
  const [status, setStatus] = useState(initialStatus || "pending");
  const [shippingCarrier, setShippingCarrier] = useState(initialCarrier);
  const [trackingNumber, setTrackingNumber] = useState(initialTrackingNumber);
  const [trackingUrl, setTrackingUrl] = useState(initialTrackingUrl);
  const [adminNote, setAdminNote] = useState(initialAdminNote);
  const [payTxHash, setPayTxHash] = useState(initialTxHash);
  const [paidAmount, setPaidAmount] = useState(initialPaidAmount);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMsg(null);
    try {
      const payload = {
        status,
        shippingCarrier,
        trackingNumber,
        trackingUrl,
        adminNote,
        payTxHash,
        paidAmount: paidAmount ? Number(paidAmount) : undefined,
      };
      const res = await fetch(`/api/admin/orders/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Save failed");
      setMsg("Saved");
    } catch (error) {
      setMsg(error instanceof Error ? error.message : "Save failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSave} className="space-y-4 rounded border border-gray-200 bg-white p-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="block text-sm font-medium text-gray-700">Status</label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Carrier</label>
          <input
            value={shippingCarrier}
            onChange={(e) => setShippingCarrier(e.target.value)}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
            placeholder="UPS / USPS / FedEx"
          />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="block text-sm font-medium text-gray-700">Tracking number</label>
          <input
            value={trackingNumber}
            onChange={(e) => setTrackingNumber(e.target.value)}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
            placeholder="1Z..."
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Tracking URL</label>
          <input
            value={trackingUrl}
            onChange={(e) => setTrackingUrl(e.target.value)}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
            placeholder="https://..."
          />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="block text-sm font-medium text-gray-700">Payment tx hash</label>
          <input
            value={payTxHash}
            onChange={(e) => setPayTxHash(e.target.value)}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
            placeholder="Optional"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Paid amount</label>
          <input
            value={paidAmount}
            onChange={(e) => setPaidAmount(e.target.value)}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
            placeholder="Optional"
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700">Admin note</label>
        <textarea
          value={adminNote}
          onChange={(e) => setAdminNote(e.target.value)}
          className="mt-1 min-h-24 w-full rounded border border-gray-300 px-3 py-2"
          placeholder="Internal notes only"
        />
      </div>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={loading}
          className="rounded bg-gray-900 px-4 py-2 text-sm text-white hover:bg-gray-800 disabled:opacity-70"
        >
          {loading ? "Saving..." : "Save order update"}
        </button>
        {msg && <p className="text-sm text-gray-600">{msg}</p>}
      </div>
    </form>
  );
}
