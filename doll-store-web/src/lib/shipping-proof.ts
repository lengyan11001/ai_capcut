import proofs from "@/data/shipping-proofs.json";

export type ShippingProof = {
  id: string;
  title: string;
  summary: string;
  image: string;
  videoUrl?: string;
  carrier?: string;
  route?: string;
  eventTime?: string;
};

export function getShippingProofs(): ShippingProof[] {
  return proofs as ShippingProof[];
}
