import { Composition, staticFile } from "remotion";
import { HelloWorld } from "./HelloWorld";
import { TextAnimation } from "./TextAnimation";
import { AIVideoDemo } from "./AIVideoDemo";
import { RemotionExplainer, TOTAL_FRAMES } from "./RemotionExplainer";
import { LottieExplainer, LottieExplainerProps } from "./LottieExplainer";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="LottieExplainer"
        component={LottieExplainer}
        durationInFrames={300}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          project: "default",
          segments: [],
          totalFrames: 300,
        }}
        calculateMetadata={async ({ props }) => {
          const resp = await fetch(
            staticFile(`${props.project}/config.json`)
          );
          const config = await resp.json();
          return {
            durationInFrames: config.totalFrames,
            fps: config.fps || 30,
            props: {
              ...props,
              segments: config.segments,
              totalFrames: config.totalFrames,
            },
          };
        }}
      />
      <Composition
        id="RemotionExplainer"
        component={RemotionExplainer}
        durationInFrames={TOTAL_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="HelloWorld"
        component={HelloWorld}
        durationInFrames={90}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="TextAnimation"
        component={TextAnimation}
        durationInFrames={150}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="AIVideoDemo"
        component={AIVideoDemo}
        durationInFrames={300}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
