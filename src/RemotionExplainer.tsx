import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Sequence,
  Easing,
  Audio,
  staticFile,
  delayRender,
  continueRender,
  cancelRender,
} from "remotion";
import { Lottie, LottieAnimationData } from "@remotion/lottie";
import { useEffect, useState } from "react";

/* ─── Config ─── */

const COLORS = {
  bg: "#0a0a0f",
  accent1: "#6366f1",
  accent2: "#8b5cf6",
  accent3: "#ec4899",
  accent4: "#06b6d4",
  accent5: "#10b981",
  text: "#f1f5f9",
  textMuted: "#94a3b8",
  codeBg: "#1e1b2e",
  codeGreen: "#4ade80",
  codeBlue: "#60a5fa",
  codePurple: "#c084fc",
  codeOrange: "#fb923c",
  codeYellow: "#fbbf24",
};

const SCENES = [
  { id: "hook", frames: 90, audio: "segment-01.mp3", lottie: "segment-01.json" },
  { id: "title", frames: 135, audio: "segment-02.mp3", lottie: "segment-02.json" },
  { id: "whatis", frames: 280, audio: "segment-03.mp3", lottie: "segment-03.json" },
  { id: "code_is_video", frames: 220, audio: "segment-04.mp3", lottie: "segment-04.json" },
  { id: "ecosystem", frames: 285, audio: "segment-05.mp3", lottie: "segment-05.json" },
  { id: "data_driven", frames: 230, audio: "segment-06.mp3", lottie: "segment-06.json" },
  { id: "core_apis", frames: 305, audio: "segment-07.mp3", lottie: "segment-07.json" },
  { id: "live_demo", frames: 275, audio: "segment-08.mp3", lottie: "segment-08.json" },
  { id: "rendering", frames: 265, audio: "segment-09.mp3", lottie: "segment-09.json" },
  { id: "closing", frames: 365, audio: "segment-10.mp3", lottie: "segment-10.json" },
];

export const TOTAL_FRAMES = SCENES.reduce((s, sc) => s + sc.frames, 0);

/* ─── Helpers ─── */

const fadeIn = (frame: number, start: number, duration = 15) =>
  interpolate(frame, [start, start + duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

const slideUp = (frame: number, fps: number, delay = 0) =>
  spring({ frame: Math.max(0, frame - delay), fps, config: { damping: 14, stiffness: 120 } });

function useLottieData(filename: string): LottieAnimationData | null {
  const [handle] = useState(() => delayRender(`Loading ${filename}`));
  const [data, setData] = useState<LottieAnimationData | null>(null);

  useEffect(() => {
    fetch(staticFile(`lottie/${filename}`))
      .then((r) => r.json())
      .then((d) => {
        setData(d);
        continueRender(handle);
      })
      .catch((e) => cancelRender(e));
  }, [handle, filename]);

  return data;
}

const LottieIcon: React.FC<{
  filename: string;
  size?: number;
  style?: React.CSSProperties;
}> = ({ filename, size = 320, style }) => {
  const animData = useLottieData(filename);
  if (!animData) return null;
  return (
    <Lottie
      animationData={animData}
      style={{ width: size, height: size, ...style }}
      playbackRate={1.5}
    />
  );
};

/* ─── Scene 1: Hook ─── */
const HookScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const words = ["你", "还在", "手动", "剪视频？"];

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at 50% 40%, #1a1040 0%, ${COLORS.bg} 70%)`,
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <div style={{ position: "absolute", top: 120, opacity: fadeIn(frame, 10, 20) }}>
        <LottieIcon filename="segment-01.json" size={300} />
      </div>
      <div style={{ display: "flex", gap: 16, marginTop: 160 }}>
        {words.map((word, i) => {
          const wordScale = spring({
            frame: Math.max(0, frame - i * 8),
            fps,
            config: { damping: 10, stiffness: 200 },
          });
          return (
            <span
              key={i}
              style={{
                fontSize: 88,
                fontWeight: 900,
                fontFamily: "system-ui, sans-serif",
                color: i === 2 ? COLORS.accent3 : COLORS.text,
                transform: `scale(${wordScale})`,
                display: "inline-block",
              }}
            >
              {word}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/* ─── Scene 2: Title Reveal ─── */
const TitleScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const logoScale = spring({ frame, fps, config: { damping: 8, stiffness: 100, mass: 0.8 } });
  const glowOpacity = interpolate(frame, [20, 50], [0, 0.6], { extrapolateRight: "clamp" });
  const subtitleY = spring({ frame: Math.max(0, frame - 25), fps, config: { damping: 15 } });

  return (
    <AbsoluteFill style={{ background: COLORS.bg, justifyContent: "center", alignItems: "center" }}>
      <div style={{ position: "absolute", top: 80, opacity: fadeIn(frame, 30, 25) }}>
        <LottieIcon filename="segment-02.json" size={260} />
      </div>
      <div
        style={{
          position: "absolute",
          width: 600, height: 600, borderRadius: "50%",
          background: `radial-gradient(circle, ${COLORS.accent1}40 0%, transparent 60%)`,
          opacity: glowOpacity, filter: "blur(40px)",
        }}
      />
      <div
        style={{
          transform: `scale(${logoScale})`,
          fontSize: 120, fontWeight: 900, marginTop: 100,
          background: `linear-gradient(135deg, ${COLORS.accent1}, ${COLORS.accent2}, ${COLORS.accent3})`,
          WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
          fontFamily: "system-ui, sans-serif", letterSpacing: -2,
        }}
      >
        Remotion
      </div>
      <div
        style={{
          transform: `translateY(${interpolate(subtitleY, [0, 1], [30, 0])}px)`,
          opacity: subtitleY, fontSize: 36, color: COLORS.textMuted,
          marginTop: 24, fontFamily: "system-ui, sans-serif", letterSpacing: 8,
        }}
      >
        用 React 写视频
      </div>
    </AbsoluteFill>
  );
};

/* ─── Scene 3: What is Remotion ─── */
const WhatIsScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const items = [
    { icon: "⚛️", label: "React", color: COLORS.codeBlue },
    { icon: "➕", label: "", color: COLORS.textMuted },
    { icon: "🎬", label: "Video", color: COLORS.accent3 },
    { icon: "＝", label: "", color: COLORS.textMuted },
    { icon: "🚀", label: "Remotion", color: COLORS.accent1 },
  ];

  return (
    <AbsoluteFill style={{ background: COLORS.bg, justifyContent: "center", alignItems: "center", gap: 40 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 60 }}>
        <div style={{ opacity: fadeIn(frame, 0, 20) }}>
          <LottieIcon filename="segment-03.json" size={360} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 36 }}>
          <div style={{ fontSize: 48, fontWeight: 700, color: COLORS.text, fontFamily: "system-ui, sans-serif", opacity: fadeIn(frame, 0) }}>
            什么是 Remotion？
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
            {items.map((item, i) => {
              const s = spring({ frame: Math.max(0, frame - 20 - i * 10), fps, config: { damping: 12, stiffness: 150 } });
              return (
                <div key={i} style={{ transform: `scale(${s})`, display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 56 }}>{item.icon}</span>
                  {item.label && <span style={{ fontSize: 22, fontWeight: 600, color: item.color, fontFamily: "system-ui, sans-serif" }}>{item.label}</span>}
                </div>
              );
            })}
          </div>
          <div style={{ opacity: fadeIn(frame, 80, 20), fontSize: 26, color: COLORS.textMuted, fontFamily: "system-ui, sans-serif", maxWidth: 700, lineHeight: 1.8 }}>
            一个开源框架，让你用 React 组件和 TypeScript 来创建视频
            <br />每一帧都是一个函数调用，完全可编程
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* ─── Scene 4: Code = Video ─── */
const CodeIsVideoScene: React.FC = () => {
  const frame = useCurrentFrame();

  const codeLines = [
    { tokens: [{ t: "const ", c: COLORS.codePurple }, { t: "frame", c: COLORS.codeBlue }, { t: " = ", c: COLORS.text }, { t: "useCurrentFrame", c: COLORS.codeYellow }, { t: "()", c: COLORS.text }] },
    { tokens: [{ t: "const ", c: COLORS.codePurple }, { t: "opacity", c: COLORS.codeBlue }, { t: " = ", c: COLORS.text }, { t: "frame", c: COLORS.codeBlue }, { t: " / ", c: COLORS.text }, { t: "30", c: COLORS.codeOrange }] },
    { tokens: [{ t: "return ", c: COLORS.codePurple }, { t: "<", c: COLORS.text }, { t: "h1", c: COLORS.codeGreen }, { t: " style=", c: COLORS.text }, { t: "{{ opacity }}", c: COLORS.codeOrange }, { t: ">", c: COLORS.text }] },
    { tokens: [{ t: "  Hello!", c: COLORS.text }] },
    { tokens: [{ t: "</", c: COLORS.text }, { t: "h1", c: COLORS.codeGreen }, { t: ">", c: COLORS.text }] },
  ];

  const resultOpacity = interpolate(frame, [60, 150], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ background: COLORS.bg, justifyContent: "center", alignItems: "center" }}>
      <div style={{ position: "absolute", top: 60, fontSize: 40, fontWeight: 700, color: COLORS.accent1, fontFamily: "system-ui, sans-serif", opacity: fadeIn(frame, 0) }}>
        优势 ① · 代码即视频
      </div>
      <div style={{ display: "flex", gap: 60, alignItems: "center", marginTop: 40 }}>
        <div style={{ background: COLORS.codeBg, borderRadius: 16, padding: "32px 36px", border: `1px solid ${COLORS.accent1}30`, opacity: fadeIn(frame, 0, 20), boxShadow: `0 0 60px ${COLORS.accent1}15`, minWidth: 480 }}>
          {codeLines.map((line, li) => (
            <div key={li} style={{ fontFamily: "'SF Mono', 'Fira Code', monospace", fontSize: 21, lineHeight: 2, opacity: fadeIn(frame, 10 + li * 8), whiteSpace: "pre" }}>
              {line.tokens.map((tok, ti) => (<span key={ti} style={{ color: tok.c }}>{tok.t}</span>))}
            </div>
          ))}
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
          <div style={{ opacity: fadeIn(frame, 50) }}>
            <LottieIcon filename="segment-04.json" size={200} />
          </div>
          <div style={{ fontSize: 40, color: COLORS.accent2, opacity: fadeIn(frame, 50) }}>→</div>
        </div>
        <div style={{ width: 320, height: 200, background: `linear-gradient(135deg, ${COLORS.accent1}15, ${COLORS.accent2}15)`, borderRadius: 16, display: "flex", justifyContent: "center", alignItems: "center", border: `1px solid ${COLORS.accent2}30`, opacity: fadeIn(frame, 55) }}>
          <span style={{ fontSize: 52, fontWeight: 700, color: COLORS.text, fontFamily: "system-ui, sans-serif", opacity: resultOpacity }}>Hello!</span>
        </div>
      </div>
      <div style={{ position: "absolute", bottom: 90, fontSize: 24, color: COLORS.textMuted, fontFamily: "system-ui, sans-serif", opacity: fadeIn(frame, 80) }}>
        写 React 组件 → 自动渲染为 MP4 视频文件
      </div>
    </AbsoluteFill>
  );
};

/* ─── Scene 5: React Ecosystem ─── */
const EcosystemScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const badges = [
    { label: "TypeScript", color: "#3178c6" },
    { label: "npm 生态", color: "#cb3837" },
    { label: "组件复用", color: "#10b981" },
    { label: "Tailwind", color: "#38bdf8" },
    { label: "三方库", color: "#f59e0b" },
    { label: "自定义 Hook", color: "#8b5cf6" },
  ];

  return (
    <AbsoluteFill style={{ background: COLORS.bg, justifyContent: "center", alignItems: "center", gap: 30 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 50 }}>
        <div style={{ opacity: fadeIn(frame, 5, 20) }}>
          <LottieIcon filename="segment-05.json" size={340} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 30, alignItems: "flex-start" }}>
          <div style={{ fontSize: 40, fontWeight: 700, color: COLORS.accent2, fontFamily: "system-ui, sans-serif", opacity: fadeIn(frame, 0) }}>
            优势 ② · 拥抱 React 生态
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 16, maxWidth: 650 }}>
            {badges.map((b, i) => {
              const s = spring({ frame: Math.max(0, frame - 15 - i * 8), fps, config: { damping: 12, stiffness: 160 } });
              return (
                <div key={i} style={{ transform: `scale(${s})`, padding: "14px 28px", borderRadius: 12, background: `${b.color}20`, border: `2px solid ${b.color}60`, fontSize: 22, fontWeight: 600, color: b.color, fontFamily: "system-ui, sans-serif" }}>
                  {b.label}
                </div>
              );
            })}
          </div>
          <div style={{ fontSize: 24, color: COLORS.textMuted, fontFamily: "system-ui, sans-serif", lineHeight: 1.8, opacity: fadeIn(frame, 70) }}>
            你已有的前端技能全部可以复用<br />不需要学习新的视频编辑语言
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* ─── Scene 6: Data Driven ─── */
const DataDrivenScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const dataItems = [
    { source: "API 数据", result: "实时数据视频", icon: "📊" },
    { source: "数据库", result: "个性化视频", icon: "🗄️" },
    { source: "JSON 配置", result: "批量生成 1000 条", icon: "📋" },
  ];

  return (
    <AbsoluteFill style={{ background: COLORS.bg, justifyContent: "center", alignItems: "center", gap: 30 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 50 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 30, alignItems: "flex-start" }}>
          <div style={{ fontSize: 40, fontWeight: 700, color: COLORS.accent4, fontFamily: "system-ui, sans-serif", opacity: fadeIn(frame, 0) }}>
            优势 ③ · 数据驱动 & 批量生成
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
            {dataItems.map((item, i) => {
              const s = slideUp(frame, fps, 20 + i * 15);
              return (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 20, opacity: interpolate(s, [0, 1], [0, 1]), transform: `translateY(${interpolate(s, [0, 1], [40, 0])}px)` }}>
                  <span style={{ fontSize: 40 }}>{item.icon}</span>
                  <div style={{ padding: "12px 24px", background: `${COLORS.accent4}15`, borderRadius: 10, border: `1px solid ${COLORS.accent4}30`, fontSize: 22, color: COLORS.accent4, fontFamily: "system-ui, sans-serif", fontWeight: 600, minWidth: 140, textAlign: "center" as const }}>{item.source}</div>
                  <span style={{ fontSize: 28, color: COLORS.textMuted }}>→</span>
                  <div style={{ padding: "12px 24px", background: `${COLORS.accent5}15`, borderRadius: 10, border: `1px solid ${COLORS.accent5}30`, fontSize: 22, color: COLORS.accent5, fontFamily: "system-ui, sans-serif", fontWeight: 600 }}>{item.result}</div>
                </div>
              );
            })}
          </div>
          <div style={{ fontSize: 22, color: COLORS.textMuted, fontFamily: "system-ui, sans-serif", opacity: fadeIn(frame, 80) }}>同一模板 + 不同数据 = 无限视频</div>
        </div>
        <div style={{ opacity: fadeIn(frame, 10, 20) }}>
          <LottieIcon filename="segment-06.json" size={360} />
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* ─── Scene 7: Core APIs ─── */
const CoreAPIsScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const apis = [
    { name: "useCurrentFrame()", desc: "获取当前帧号，视频的时间轴", color: COLORS.codeYellow },
    { name: "interpolate()", desc: "将帧映射为任意动画值", color: COLORS.codeBlue },
    { name: "spring()", desc: "物理弹簧动画，自然流畅", color: COLORS.codeGreen },
    { name: "<Sequence>", desc: "时间线分段，组合多场景", color: COLORS.codePurple },
  ];

  return (
    <AbsoluteFill style={{ background: COLORS.bg, justifyContent: "center", alignItems: "center", gap: 30 }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 50 }}>
        <div style={{ opacity: fadeIn(frame, 5, 20) }}>
          <LottieIcon filename="segment-07.json" size={280} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div style={{ fontSize: 44, fontWeight: 700, color: COLORS.text, fontFamily: "system-ui, sans-serif", opacity: fadeIn(frame, 0) }}>
            四个核心 API 就够了
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
            {apis.map((api, i) => {
              const s = spring({ frame: Math.max(0, frame - 15 - i * 10), fps, config: { damping: 14, stiffness: 140 } });
              return (
                <div key={i} style={{ transform: `scale(${s})`, background: `${api.color}08`, border: `1px solid ${api.color}30`, borderRadius: 14, padding: "24px 28px", display: "flex", flexDirection: "column", gap: 8 }}>
                  <span style={{ fontFamily: "'SF Mono', 'Fira Code', monospace", fontSize: 24, fontWeight: 700, color: api.color }}>{api.name}</span>
                  <span style={{ fontSize: 18, color: COLORS.textMuted, fontFamily: "system-ui, sans-serif" }}>{api.desc}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* ─── Scene 8: Live Demo ─── */
const LiveDemoScene: React.FC = () => {
  const frame = useCurrentFrame();

  const circleX = interpolate(frame, [0, 240], [100, 1100], { easing: Easing.inOut(Easing.cubic) });
  const circleSize = interpolate(frame, [0, 120, 240], [40, 120, 40]);
  const hue = interpolate(frame, [0, 240], [230, 360]);
  const barWidth = interpolate(frame, [0, 240], [0, 1]);
  const rotation = interpolate(frame, [0, 240], [0, 720]);

  return (
    <AbsoluteFill style={{ background: COLORS.bg, justifyContent: "center", alignItems: "center" }}>
      <div style={{ position: "absolute", top: 50, display: "flex", alignItems: "center", gap: 20 }}>
        <div style={{ opacity: fadeIn(frame, 0, 15) }}>
          <LottieIcon filename="segment-08.json" size={100} />
        </div>
        <div style={{ fontSize: 40, fontWeight: 700, color: COLORS.codeYellow, fontFamily: "system-ui, sans-serif" }}>
          interpolate() 实时演示
        </div>
      </div>
      <div style={{ position: "absolute", top: 140, fontFamily: "'SF Mono', monospace", fontSize: 22, color: COLORS.textMuted }}>
        frame: {frame} / 240
      </div>
      <div style={{ position: "absolute", top: 300, left: circleX, width: circleSize, height: circleSize, borderRadius: "50%", background: `hsl(${hue}, 80%, 65%)`, transform: `translate(-50%, -50%) rotate(${rotation}deg)`, boxShadow: `0 0 40px hsl(${hue}, 80%, 65%, 0.5)` }} />
      <div style={{ position: "absolute", top: 450, width: 1200, height: 6, background: "#1e293b", borderRadius: 3 }}>
        <div style={{ width: `${barWidth * 100}%`, height: "100%", background: `linear-gradient(90deg, ${COLORS.accent1}, ${COLORS.accent3})`, borderRadius: 3 }} />
      </div>
      <div style={{ position: "absolute", bottom: 140, background: COLORS.codeBg, borderRadius: 12, padding: "22px 32px", border: `1px solid ${COLORS.accent1}25` }}>
        <div style={{ fontFamily: "'SF Mono', monospace", fontSize: 20, lineHeight: 1.8 }}>
          <span style={{ color: COLORS.codePurple }}>const </span>
          <span style={{ color: COLORS.codeBlue }}>x</span>
          <span style={{ color: COLORS.text }}> = </span>
          <span style={{ color: COLORS.codeYellow }}>interpolate</span>
          <span style={{ color: COLORS.text }}>(frame, [</span>
          <span style={{ color: COLORS.codeOrange }}>0</span>
          <span style={{ color: COLORS.text }}>, </span>
          <span style={{ color: COLORS.codeOrange }}>240</span>
          <span style={{ color: COLORS.text }}>], [</span>
          <span style={{ color: COLORS.codeOrange }}>100</span>
          <span style={{ color: COLORS.text }}>, </span>
          <span style={{ color: COLORS.codeOrange }}>1100</span>
          <span style={{ color: COLORS.text }}>])</span>
          <span style={{ color: COLORS.textMuted }}> {"// "}→ {Math.round(circleX)}</span>
        </div>
      </div>
      {[0, 1, 2].map((i) => (
        <div key={i} style={{ position: "absolute", top: 550 + i * 60, left: 960, width: 60 - i * 15, height: 60 - i * 15, border: `2px solid hsl(${hue + i * 40}, 70%, 60%)`, borderRadius: 8, transform: `translate(-50%, -50%) rotate(${interpolate(frame, [0, 240], [i * 120, i * 120 + 360])}deg)`, opacity: interpolate(frame, [i * 20, i * 20 + 30], [0, 0.3], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }} />
      ))}
    </AbsoluteFill>
  );
};

/* ─── Scene 9: Rendering Pipeline ─── */
const RenderingScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const steps = [
    { cmd: "npx remotion studio", desc: "本地预览 & 实时编辑", icon: "🖥️" },
    { cmd: "npx remotion render", desc: "CLI 一键渲染 MP4", icon: "⚡" },
    { cmd: "npx remotion lambda", desc: "AWS Lambda 云端渲染", icon: "☁️" },
  ];

  return (
    <AbsoluteFill style={{ background: COLORS.bg, justifyContent: "center", alignItems: "center", gap: 30 }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 50 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
          <div style={{ fontSize: 44, fontWeight: 700, color: COLORS.accent5, fontFamily: "system-ui, sans-serif", opacity: fadeIn(frame, 0) }}>
            三种方式输出视频
          </div>
          {steps.map((step, i) => {
            const s = slideUp(frame, fps, 15 + i * 18);
            return (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 20, opacity: interpolate(s, [0, 1], [0, 1]), transform: `translateX(${interpolate(s, [0, 1], [-60, 0])}px)` }}>
                <span style={{ fontSize: 44 }}>{step.icon}</span>
                <div style={{ background: COLORS.codeBg, borderRadius: 10, padding: "14px 24px", border: `1px solid ${COLORS.accent5}25`, minWidth: 360 }}>
                  <div style={{ fontFamily: "'SF Mono', monospace", fontSize: 20, color: COLORS.codeGreen }}>$ {step.cmd}</div>
                </div>
                <span style={{ fontSize: 20, color: COLORS.textMuted, fontFamily: "system-ui, sans-serif" }}>{step.desc}</span>
              </div>
            );
          })}
          <div style={{ fontSize: 22, color: COLORS.textMuted, fontFamily: "system-ui, sans-serif", opacity: fadeIn(frame, 80) }}>从开发到生产，完整的工作流</div>
        </div>
        <div style={{ opacity: fadeIn(frame, 10, 20) }}>
          <LottieIcon filename="segment-09.json" size={360} />
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* ─── Scene 10: Closing ─── */
const ClosingScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const summaryPoints = [
    "✦ 用 React 写视频，前端秒上手",
    "✦ 完全可编程，数据驱动",
    "✦ 批量生成，自动化流水线",
    "✦ 开源免费，社区活跃",
  ];

  const titleScale = spring({ frame, fps, config: { damping: 10, stiffness: 100 } });
  const bgPulse = interpolate(frame, [0, 180, 360], [0, 0.3, 0], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ background: COLORS.bg, justifyContent: "center", alignItems: "center" }}>
      <div style={{ position: "absolute", width: 800, height: 800, borderRadius: "50%", background: `radial-gradient(circle, ${COLORS.accent1}30, transparent 70%)`, opacity: bgPulse, filter: "blur(60px)" }} />
      <div style={{ position: "absolute", top: 100, opacity: fadeIn(frame, 20, 25) }}>
        <LottieIcon filename="segment-10.json" size={280} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 32, marginTop: 140 }}>
        <div style={{ transform: `scale(${titleScale})`, fontSize: 56, fontWeight: 900, background: `linear-gradient(135deg, ${COLORS.accent1}, ${COLORS.accent3})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", fontFamily: "system-ui, sans-serif" }}>
          开始用 Remotion 吧
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {summaryPoints.map((point, i) => {
            const pointOpacity = fadeIn(frame, 20 + i * 15);
            const pointX = spring({ frame: Math.max(0, frame - 20 - i * 15), fps, config: { damping: 15 } });
            return (
              <div key={i} style={{ opacity: pointOpacity, transform: `translateX(${interpolate(pointX, [0, 1], [-40, 0])}px)`, fontSize: 28, color: COLORS.textMuted, fontFamily: "system-ui, sans-serif" }}>
                {point}
              </div>
            );
          })}
        </div>
        <div style={{ marginTop: 16, opacity: fadeIn(frame, 90), fontSize: 22, color: COLORS.accent1, fontFamily: "'SF Mono', monospace" }}>
          npm i remotion @remotion/cli
        </div>
        <div style={{ opacity: fadeIn(frame, 100), fontSize: 20, color: COLORS.textMuted, fontFamily: "system-ui, sans-serif" }}>
          remotion.dev
        </div>
      </div>
      <div style={{ position: "absolute", bottom: 50, opacity: fadeIn(frame, 130, 30), fontSize: 18, color: `${COLORS.textMuted}80`, fontFamily: "system-ui, sans-serif", fontStyle: "italic" }}>
        本视频由 Remotion 生成 — 以身作则
      </div>
    </AbsoluteFill>
  );
};

/* ─── Main Composition ─── */
export const RemotionExplainer: React.FC = () => {
  let offset = 0;
  const sceneOffsets = SCENES.map((sc) => {
    const start = offset;
    offset += sc.frames;
    return start;
  });

  const sceneComponents = [
    HookScene, TitleScene, WhatIsScene, CodeIsVideoScene, EcosystemScene,
    DataDrivenScene, CoreAPIsScene, LiveDemoScene, RenderingScene, ClosingScene,
  ];

  return (
    <AbsoluteFill style={{ background: COLORS.bg }}>
      {SCENES.map((sc, i) => {
        const SceneComp = sceneComponents[i];
        return (
          <Sequence key={sc.id} from={sceneOffsets[i]} durationInFrames={sc.frames}>
            <SceneComp />
            <Audio src={staticFile(`audio/${sc.audio}`)} volume={0.9} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
