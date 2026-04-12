export interface Category {
  id: string;
  slug: string;
  name: string;
  description?: string;
}

export interface Product {
  id: string;
  slug: string;
  name: string;
  description: string;
  price: number;
  /** 兼容历史字段：旧逻辑价格（建议逐步只使用 salePrice） */
  currency?: "CNY" | "USD" | "EUR";
  costCurrency?: "CNY" | "USD" | "EUR";
  saleCurrency?: "CNY" | "USD" | "EUR";
  costPrice?: number;
  salePrice?: number;
  assetStatus?: "raw" | "processed" | "published";
  shippingQuoteMode?: "included" | "quote_after_confirm";
  isFreeShippingOverseas?: boolean;
  compareAtPrice?: number;
  images: string[];
  /** 可选：商品介绍视频 URL，上线前替换为自有或供应商授权素材 */
  videoUrl?: string;
  sku?: string;
  sourceType?: "origin" | "overseas_us" | "overseas_eu";
  visibleRegions?: Array<"US" | "EU" | "ROW" | "ALL">;
  shippableCountries?: string[];
  shippingNotice?: string;
  leadTimeDays?: string;
  addOnOptions?: string[];
  categoryId: string;
  material: string;
  specs?: Record<string, string>;
  featured?: boolean;
}

export interface GuideSectionImage {
  src: string;
  alt: string;
  caption?: string;
}

export interface GuideSection {
  heading: string;
  body: string;
  images?: GuideSectionImage[];
}

export interface GuideArticle {
  id: string;
  slug: string;
  title: string;
  excerpt: string;
  category: "Beginner" | "Material" | "Care" | "Scene" | "Comparison";
  readMinutes: number;
  tags: string[];
  sections: GuideSection[];
  relatedProductSlugs: string[];
  /** Optional hero thumbnail for listings; falls back to first section image when unset */
  coverImage?: string;
}

export interface CartItem {
  productId: string;
  slug: string;
  name: string;
  price: number;
  currency?: "CNY" | "USD" | "EUR";
  quantity: number;
  image?: string;
}

export interface ShippingInfo {
  name: string;
  email: string;
  phone?: string;
  address: string;
  city: string;
  state?: string;
  postalCode: string;
  country: string;
}

export interface OrderPayload {
  email: string;
  shipping: ShippingInfo;
  items: CartItem[];
  total: number;
  currency: string;
  paymentMethod?: "manual_contact" | "crypto_manual" | "paypal";
  paypal?: {
    orderId: string;
    captureId: string;
    payerEmail?: string;
    status?: string;
  };
}
