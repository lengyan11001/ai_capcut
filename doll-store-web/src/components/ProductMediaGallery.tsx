"use client";

import { useMemo, useState } from "react";
import Image from "next/image";

interface Props {
  name: string;
  images: string[];
  videoUrl?: string;
}

type MediaItem =
  | { type: "image"; url: string }
  | { type: "video"; url: string };

export function ProductMediaGallery({ name, images, videoUrl }: Props) {
  const mediaItems = useMemo<MediaItem[]>(() => {
    const items: MediaItem[] = (images ?? []).map((url) => ({ type: "image", url }));
    if (videoUrl) items.push({ type: "video", url: videoUrl });
    return items;
  }, [images, videoUrl]);

  const [activeIndex, setActiveIndex] = useState(0);
  const [zooming, setZooming] = useState(false);
  const [zoomPos, setZoomPos] = useState({ x: 50, y: 50 });
  const active = mediaItems[activeIndex];

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
                  <div className="flex h-full items-center justify-center bg-gray-800 text-xs text-white">Video</div>
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
    <div className="space-y-3">
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
          priority
          unoptimized={isPlaceholder || isProxyImage}
        />
        <div className="pointer-events-none absolute bottom-3 right-3 rounded bg-black/65 px-2 py-1 text-xs text-white">
          Hover to zoom
        </div>
      </div>

      {zooming && (
        <div
          className="hidden h-44 rounded-lg border border-gray-200 bg-white lg:block"
          style={{
            backgroundImage: `url("${active.url}")`,
            backgroundSize: "220%",
            backgroundPosition: `${zoomPos.x}% ${zoomPos.y}%`,
          }}
        />
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
                    unoptimized={item.url.startsWith("https://placehold.co") || item.url.startsWith("/api/image-proxy")}
                  />
                </div>
              ) : (
                <div className="flex h-full items-center justify-center bg-gray-800 text-xs text-white">Video</div>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
