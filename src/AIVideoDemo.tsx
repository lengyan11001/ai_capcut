import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Sequence,
} from "remotion";

const SceneCard: React.FC<{
  title: string;
  description: string;
  icon: string;
  color: string;
}> = ({ title, description, icon, color }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const scale = spring({ frame, fps, config: { damping: 12 } });
  const opacity = interpolate(frame, [0, 15], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        backgroundColor: "#0a0a0a",
      }}
    >
      <div
        style={{
          transform: `scale(${scale})`,
          opacity,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 24,
        }}
      >
        <div style={{ fontSize: 120 }}>{icon}</div>
        <div
          style={{
            fontSize: 64,
            fontWeight: "bold",
            color,
            fontFamily: "system-ui, sans-serif",
          }}
        >
          {title}
        </div>
        <div
          style={{
            fontSize: 28,
            color: "#888",
            fontFamily: "system-ui, sans-serif",
            maxWidth: 800,
            textAlign: "center",
            lineHeight: 1.6,
          }}
        >
          {description}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const ProgressBar: React.FC<{ progress: number; label: string }> = ({
  progress,
  label,
}) => (
  <div style={{ width: "100%", maxWidth: 600 }}>
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        marginBottom: 8,
        fontFamily: "monospace",
        fontSize: 16,
        color: "#aaa",
      }}
    >
      <span>{label}</span>
      <span>{Math.round(progress * 100)}%</span>
    </div>
    <div
      style={{
        width: "100%",
        height: 8,
        backgroundColor: "#222",
        borderRadius: 4,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          width: `${progress * 100}%`,
          height: "100%",
          background: "linear-gradient(90deg, #667eea, #764ba2)",
          borderRadius: 4,
          transition: "width 0.1s",
        }}
      />
    </div>
  </div>
);

const PipelineScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const steps = [
    { label: "剧本解析", icon: "📝" },
    { label: "角色提取", icon: "👤" },
    { label: "分镜生成", icon: "🎬" },
    { label: "AI 绘图", icon: "🎨" },
    { label: "语音合成", icon: "🔊" },
    { label: "视频合成", icon: "🎥" },
  ];

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
          fontSize: 48,
          fontWeight: "bold",
          color: "white",
          marginBottom: 60,
          fontFamily: "system-ui, sans-serif",
        }}
      >
        AI 视频制作流水线
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        {steps.map((step, i) => {
          const stepStart = i * 12;
          const progress = interpolate(
            frame,
            [stepStart, stepStart + 15],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );

          const opacity = interpolate(frame, [stepStart, stepStart + 5], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });

          return (
            <div
              key={i}
              style={{
                opacity,
                display: "flex",
                alignItems: "center",
                gap: 20,
              }}
            >
              <div style={{ fontSize: 36, width: 50 }}>{step.icon}</div>
              <ProgressBar progress={progress} label={step.label} />
              {progress >= 1 && (
                <div style={{ fontSize: 24, color: "#4ade80" }}>✓</div>
              )}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

export const AIVideoDemo: React.FC = () => {
  return (
    <AbsoluteFill>
      <Sequence from={0} durationInFrames={60}>
        <SceneCard
          title="AI 视频工作流"
          description="用 Remotion 把 AI 生成的素材自动组装成完整视频"
          icon="🤖"
          color="#667eea"
        />
      </Sequence>

      <Sequence from={60} durationInFrames={60}>
        <SceneCard
          title="分镜驱动"
          description="从剧本自动提取分镜表，每个镜头对应一个 Sequence 组件"
          icon="🎬"
          color="#f093fb"
        />
      </Sequence>

      <Sequence from={120} durationInFrames={60}>
        <SceneCard
          title="素材自动填充"
          description="AI 生成的图片、视频、配音按分镜自动插入对应位置"
          icon="🧩"
          color="#4facfe"
        />
      </Sequence>

      <Sequence from={180} durationInFrames={90}>
        <PipelineScene />
      </Sequence>

      <Sequence from={270} durationInFrames={30}>
        <SceneCard
          title="一键渲染输出"
          description="本地 CLI 或 AWS Lambda 云端渲染，几分钟出片"
          icon="🚀"
          color="#43e97b"
        />
      </Sequence>
    </AbsoluteFill>
  );
};
