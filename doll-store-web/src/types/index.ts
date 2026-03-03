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
  currency?: "CNY" | "USD" | "EUR";
  compareAtPrice?: number;
  images: string[];
  /** 可选：商品介绍视频 URL，上线前替换为自有或供应商授权素材 */
  videoUrl?: string;
  sku?: string;
  sourceType?: "origin" | "overseas_us" | "overseas_eu";
  shippingNotice?: string;
  leadTimeDays?: string;
  addOnOptions?: string[];
  categoryId: string;
  material: string;
  specs?: Record<string, string>;
  featured?: boolean;
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
}
