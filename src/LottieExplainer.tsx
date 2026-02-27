import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Sequence,
  Audio,
  staticFile,
  delayRender,
  continueRender,
  cancelRender,
} from "remotion";
import { Lottie, LottieAnimationData } from "@remotion/lottie";
import { useEffect, useState } from "react";

/* ─── Types ─── */

export interface SegmentConfig {
  id: string;
  narration: string;
  lottieFile: string;
  audioFile: string;
  durationFrames: number;
}

export interface LottieExplainerProps {
  project: string;
  segments: SegmentConfig[];
  totalFrames: number;
}

/* ─── Color Themes (6 rotating) ─── */

const COLOR_THEMES = [
  { accent: "#3B82F6", light: "#93C5FD", glow: "rgba(59,130,246,0.15)", bgLight: "#111827", bgDark: "#08080f" },
  { accent: "#8B5CF6", light: "#C4B5FD", glow: "rgba(139,92,246,0.15)", bgLight: "#130f1f", bgDark: "#08080f" },
  { accent: "#EC4899", light: "#F9A8D4", glow: "rgba(236,72,153,0.15)", bgLight: "#1a0f15", bgDark: "#08080f" },
  { accent: "#F59E0B", light: "#FCD34D", glow: "rgba(245,158,11,0.15)", bgLight: "#1a1508", bgDark: "#08080f" },
  { accent: "#10B981", light: "#6EE7B7", glow: "rgba(16,185,129,0.15)", bgLight: "#0f1a16", bgDark: "#08080f" },
  { accent: "#06B6D4", light: "#67E8F9", glow: "rgba(6,182,212,0.15)", bgLight: "#0f171a", bgDark: "#08080f" },
];

/* ─── Animation Helpers ─── */

const fadeIn = (frame: number, start: number, duration = 15) =>
  interpolate(frame, [start, start + duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

const scaleIn = (frame: number, fps: number, delay = 0) =>
  spring({
    frame: Math.max(0, frame - delay),
    fps,
    config: { damping: 12, stiffness: 120 },
  });

/* ─── Lottie Loader Hook ─── */

function useLottieData(path: string): LottieAnimationData | null {
  const [handle] = useState(() => delayRender(`Loading ${path}`));
  const [data, setData] = useState<LottieAnimationData | null>(null);

  useEffect(() => {
    fetch(staticFile(path))
      .then((r) => r.json())
      .then((d) => {
        setData(d);
        continueRender(handle);
      })
      .catch((e) => cancelRender(e));
  }, [handle, path]);

  return data;
}

/* ─── Single Segment Scene ─── */

const SegmentScene: React.FC<{
  project: string;
  segment: SegmentConfig;
  index: number;
  total: number;
}> = ({ project, segment, index, total }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const theme = COLOR_THEMES[index % COLOR_THEMES.length];

  const lottiePath = `${project}/lottie/${segment.lottieFile}`;
  const animData = useLottieData(lottiePath);

  const lottieScale = scaleIn(frame, fps, 0);
  const textOpacity = fadeIn(frame, 8, 18);
  const textSlideY = interpolate(
    spring({ frame: Math.max(0, frame - 8), fps, config: { damping: 14, stiffness: 100 } }),
    [0, 1],
    [30, 0]
  );
  const counterOpacity = fadeIn(frame, 0, 25);

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at 50% 30%, ${theme.bgLight}, ${theme.bgDark} 60%, #050508)`,
        fontFamily: "'PingFang SC','Noto Sans SC','Microsoft YaHei',system-ui,sans-serif",
      }}
    >
      {/* Background orbs */}
      <div
        style={{
          position: "absolute",
          width: 900,
          height: 900,
          borderRadius: "50%",
          background: theme.glow,
          top: -300,
          left: -200,
          opacity: 0.4,
          filter: "blur(120px)",
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 600,
          height: 600,
          borderRadius: "50%",
          background: theme.glow,
          bottom: 50,
          right: -150,
          opacity: 0.25,
          filter: "blur(120px)",
        }}
      />

      {/* Lottie animation */}
      <div
        style={{
          position: "absolute",
          top: 40,
          left: 0,
          width: 1920,
          height: 700,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          overflow: "hidden",
          transform: `scale(${lottieScale})`,
        }}
      >
        {animData && (
          <Lottie
            animationData={animData}
            style={{
              width: 560,
              height: 560,
              filter: `drop-shadow(0 0 80px ${theme.glow})`,
            }}
            playbackRate={1}
          />
        )}
      </div>

      {/* Bottom text bar */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: 340,
          background:
            "linear-gradient(to bottom, transparent 0%, rgba(5,5,8,0.7) 25%, rgba(5,5,8,0.95) 50%)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "0 120px",
        }}
      >
        <div
          style={{
            fontSize: 64,
            fontWeight: 800,
            lineHeight: 1.4,
            textAlign: "center" as const,
            letterSpacing: 4,
            background: `linear-gradient(135deg, #ffffff 0%, ${theme.light} 100%)`,
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            opacity: textOpacity,
            transform: `translateY(${textSlideY}px)`,
          }}
        >
          {segment.narration}
        </div>
      </div>

      {/* Accent dot */}
      <div
        style={{
          position: "absolute",
          bottom: 60,
          left: "50%",
          transform: "translateX(-50%)",
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: theme.accent,
          opacity: interpolate(frame % 45, [0, 22, 44], [0.3, 0.8, 0.3]),
        }}
      />

      {/* Segment counter */}
      <div
        style={{
          position: "absolute",
          top: 20,
          right: 40,
          fontSize: 18,
          color: "rgba(255,255,255,0.12)",
          fontWeight: 500,
          opacity: counterOpacity,
        }}
      >
        {String(index + 1).padStart(2, "0")} / {String(total).padStart(2, "0")}
      </div>
    </AbsoluteFill>
  );
};

/* ─── Main Composition ─── */

export const LottieExplainer: React.FC<LottieExplainerProps> = ({
  project,
  segments,
}) => {
  let offset = 0;

  return (
    <AbsoluteFill style={{ background: "#08080f" }}>
      {segments.map((seg, i) => {
        const from = offset;
        offset += seg.durationFrames;
        return (
          <Sequence key={seg.id} from={from} durationInFrames={seg.durationFrames}>
            <SegmentScene
              project={project}
              segment={seg}
              index={i}
              total={segments.length}
            />
            <Audio
              src={staticFile(`${project}/audio/${seg.audioFile}`)}
              volume={0.9}
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
