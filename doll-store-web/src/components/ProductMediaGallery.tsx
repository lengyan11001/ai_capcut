"use client";

import { useEffect, useMemo, useState } from "react";
import Image from "next/image";
import type { Lang } from "@/lib/i18n";
import { t } from "@/lib/i18n";

interface Props {
  name: string;
  images: string[];
  videoUrl?: string;
  lang?: Lang;
}

type MediaItem =
  | { type: "image"; url: string }
  | { type: "video"; url: string };

export function ProductMediaGallery({ name, images, videoUrl, lang = "en" }: Props) {
  const ZOOM_SCALE = 3.2;
  const ZOOM_WIDTH = 360;
  const ZOOM_HEIGHT = 520;

  const mediaItems = useMemo<MediaItem[]>(() => {
    const imageItems: MediaItem[] = (images ?? []).map((url) => ({ type: "image", url }));
    if (!videoUrl) return imageItems;
    return [{ type: "video", url: videoUrl }, ...imageItems];
  }, [images, videoUrl]);

  const [activeIndex, setActiveIndex] = useState(0);
  const [zooming, setZooming] = useState(false);
  const [zoomPos, setZoomPos] = useState({ x: 50, y: 50 });
  const active = mediaItems[activeIndex];
  const activeImageUrl = active?.type === "image" ? active.url : "";

  const zoomStyle = useMemo(() => {
    const scaledWidth = ZOOM_WIDTH * ZOOM_SCALE;
    const scaledHeight = ZOOM_HEIGHT * ZOOM_SCALE;
    const centerX = ZOOM_WIDTH / 2 - (zoomPos.x / 100) * scaledWidth;
    const centerY = ZOOM_HEIGHT / 2 - (zoomPos.y / 100) * scaledHeight;
    const minX = ZOOM_WIDTH - scaledWidth;
    const minY = ZOOM_HEIGHT - scaledHeight;
    const clampedX = Math.max(minX, Math.min(0, centerX));
    const clampedY = Math.max(minY, Math.min(0, centerY));
    return {
      backgroundSize: `${ZOOM_SCALE * 100}% ${ZOOM_SCALE * 100}%`,
      backgroundPosition: `${clampedX}px ${clampedY}px`,
    };
  }, [zoomPos.x, zoomPos.y]);

  useEffect(() => {
    if (!activeImageUrl) return;
    const img = new window.Image();
    img.decoding = "async";
    img.src = activeImageUrl;
  }, [activeImageUrl]);

  if (!active) return null;

  if (active.type === "video") {
    return (
      <div className="space-y-3">
        <div className="overflow-hidden rounded-lg bg-gray-900">
          <video src={active.url} controls className="aspect-video w-full object-contain" preload="metadata">
            Your browser does not support the video tag.
          </video>
        </div>
        {mediaItems.length > 1 && (
          <div className="grid grid-cols-5 gap-2">
            {mediaItems.map((item, index) => (
              <button
                key={`${item.type}-${item.url}-${index}`}
                type="button"
                onClick={() => setActiveIndex(index)}
                className={`aspect-square overflow-hidden rounded border ${
                  index === activeIndex ? "border-gray-900" : "border-gray-200"
                }`}
              >
                {item.type === "image" ? (
                  <div className="relative h-full w-full bg-gray-100">
                    <Image
                      src={item.url}
                      alt={`${name} preview ${index + 1}`}
                      fill
                      className="object-cover"
                      unoptimized={item.url.startsWith("https://placehold.co") || item.url.startsWith("/api/image-proxy")}
                    />
                  </div>
                ) : (
                  <video
                    src={item.url}
                    className="h-full w-full object-cover"
                    preload="metadata"
                    muted
                    playsInline
                  />
                )}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  const isPlaceholder = active.url.startsWith("https://placehold.co");
  const isProxyImage = active.url.startsWith("/api/image-proxy");

  return (
    <div className="relative space-y-3 overflow-visible">
      <div
        className="group relative aspect-[3/4] overflow-hidden rounded-lg bg-gray-100"
        onMouseEnter={() => setZooming(true)}
        onMouseLeave={() => setZooming(false)}
        onMouseMove={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          const x = ((event.clientX - rect.left) / rect.width) * 100;
          const y = ((event.clientY - rect.top) / rect.height) * 100;
          setZoomPos({
            x: Math.min(100, Math.max(0, x)),
            y: Math.min(100, Math.max(0, y)),
          });
        }}
      >
        <Image
          src={active.url}
          alt={name}
          fill
          className="object-cover transition duration-200"
          sizes="(max-width: 1024px) 100vw, 50vw"
          priority={activeIndex === 0}
          quality={75}
          unoptimized={isPlaceholder || isProxyImage}
        />
        <div className="pointer-events-none absolute bottom-3 right-3 rounded bg-black/65 px-2 py-1 text-xs text-white">
          {t(lang, "Hover to zoom", "悬停放大")}
        </div>
      </div>

      {zooming && (
        <div
          className="pointer-events-none absolute left-[calc(100%+16px)] top-0 z-50 hidden h-[520px] w-[360px] rounded-lg border border-gray-200 bg-white shadow-2xl lg:block"
        >
          <div
            className="h-full w-full overflow-hidden rounded-lg bg-no-repeat"
            style={{
              backgroundImage: `url("${active.url}")`,
              ...zoomStyle,
            }}
          >
            <span className="sr-only">{`${name} zoom`}</span>
          </div>
        </div>
      )}

      {mediaItems.length > 1 && (
        <div className="grid grid-cols-5 gap-2">
          {mediaItems.map((item, index) => (
            <button
              key={`${item.type}-${item.url}-${index}`}
              type="button"
              onClick={() => setActiveIndex(index)}
              className={`aspect-square overflow-hidden rounded border ${
                index === activeIndex ? "border-gray-900" : "border-gray-200"
              }`}
            >
              {item.type === "image" ? (
                <div className="relative h-full w-full bg-gray-100">
                  <Image
                    src={item.url}
                    alt={`${name} preview ${index + 1}`}
                    fill
                    className="object-cover"
                    sizes="96px"
                    loading="lazy"
                    quality={60}
                    unoptimized={item.url.startsWith("https://placehold.co") || item.url.startsWith("/api/image-proxy")}
                  />
                </div>
              ) : (
                <video
                  src={item.url}
                  className="h-full w-full object-cover"
                  preload="metadata"
                  muted
                  playsInline
                />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
