import React from 'react';
import {Composition, getInputProps, registerRoot} from 'remotion';
import {TalkingVideo, Manifest} from './TalkingVideo';

const manifest = getInputProps<Manifest>();

export const RemotionRoot: React.FC = () => {
  const fps = manifest.output.fps;
  const durationInFrames = Math.ceil((manifest.output.duration_ms / 1000) * fps);
  return (
    <Composition
      id="TalkingVideo"
      component={TalkingVideo}
      durationInFrames={durationInFrames}
      fps={fps}
      width={manifest.output.width}
      height={manifest.output.height}
      defaultProps={{manifest}}
    />
  );
};

registerRoot(RemotionRoot);
