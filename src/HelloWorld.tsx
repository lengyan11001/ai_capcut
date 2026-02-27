import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
} from "remotion";

export const HelloWorld: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleScale = spring({
    frame,
    fps,
    config: { damping: 12, stiffness: 200 },
  });

  const subtitleOpacity = interpolate(frame, [30, 50], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const bgRotation = interpolate(frame, [0, 90], [0, 360]);

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(${bgRotation}deg, #0f0c29, #302b63, #24243e)`,
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <div
        style={{
          transform: `scale(${titleScale})`,
          fontSize: 80,
          fontWeight: "bold",
          color: "white",
          fontFamily: "system-ui, sans-serif",
          textShadow: "0 4px 20px rgba(0,0,0,0.5)",
        }}
      >
        Hello Remotion!
      </div>
      <div
        style={{
          opacity: subtitleOpacity,
          fontSize: 32,
          color: "#a8a4ff",
          marginTop: 20,
          fontFamily: "system-ui, sans-serif",
        }}
      >
        用 React 编写视频 · 第 {frame} 帧
      </div>
    </AbsoluteFill>
  );
};
