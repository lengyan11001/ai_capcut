import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Easing,
} from "remotion";

const lines = [
  { text: "第一幕：黎明", color: "#ff6b6b" },
  { text: "角色登场", color: "#feca57" },
  { text: "剧情展开", color: "#48dbfb" },
  { text: "高潮迭起", color: "#ff9ff3" },
  { text: "完美收场", color: "#54a0ff" },
];

export const TextAnimation: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#0a0a0a",
        justifyContent: "center",
        alignItems: "center",
        padding: 80,
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 60,
          left: 80,
          fontSize: 24,
          color: "#666",
          fontFamily: "monospace",
        }}
      >
        Remotion · 文字逐行动画演示
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 30 }}>
        {lines.map((line, i) => {
          const delay = i * 20;

          const slideIn = spring({
            frame: frame - delay,
            fps,
            config: { damping: 15, stiffness: 100 },
          });

          const opacity = interpolate(frame - delay, [0, 10], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });

          const translateX = interpolate(slideIn, [0, 1], [-100, 0]);

          return (
            <div
              key={i}
              style={{
                transform: `translateX(${translateX}px)`,
                opacity,
                fontSize: 56,
                fontWeight: "bold",
                color: line.color,
                fontFamily: "system-ui, sans-serif",
                display: "flex",
                alignItems: "center",
                gap: 20,
              }}
            >
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  backgroundColor: line.color,
                  boxShadow: `0 0 20px ${line.color}`,
                }}
              />
              {line.text}
            </div>
          );
        })}
      </div>

      <div
        style={{
          position: "absolute",
          bottom: 60,
          fontSize: 20,
          color: "#444",
          fontFamily: "monospace",
        }}
      >
        帧: {frame} / 150
      </div>
    </AbsoluteFill>
  );
};
