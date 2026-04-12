import guidesData from "@/data/guides.json";
import type { GuideArticle } from "@/types";
import { getProducts } from "@/lib/data";

const guides = guidesData as GuideArticle[];

export function getGuides(): GuideArticle[] {
  return guides;
}

/** Cover for cards: explicit coverImage, else first image in any section */
export function getGuideCoverImage(guide: GuideArticle): string | null {
  if (guide.coverImage) return guide.coverImage;
  for (const section of guide.sections) {
    const first = section.images?.[0]?.src;
    if (first) return first;
  }
  return null;
}

export function getGuideBySlug(slug: string): GuideArticle | undefined {
  return guides.find((g) => g.slug === slug);
}

export async function getGuideProducts(guide: GuideArticle) {
  const productMap = new Map((await getProducts()).map((p) => [p.slug, p]));
  return guide.relatedProductSlugs
    .map((slug) => productMap.get(slug))
    .filter((p) => p != null);
}

