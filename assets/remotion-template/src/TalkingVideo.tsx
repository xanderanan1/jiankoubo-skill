import React from 'react';
import {AbsoluteFill, Audio, interpolate, OffthreadVideo, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

type MotionSpec = {
  preset?: string;
  intensity?: number;
  duration_ms?: number;
  sfx?: string;
};

type DecorationSpec = {
  scanline?: boolean;
  sweep_light?: boolean;
  corner_ticks?: boolean;
  progress_bar?: boolean;
  bracket_focus?: boolean;
  dot_grid?: boolean;
  underline?: boolean;
  arrow?: boolean;
};

export type TimedText = {
  text: string;
  start_ms: number;
  end_ms: number;
  style?: string;
  semantic_type?: string;
  visual_style?: string;
  type?: string;
  lane?: string;
  render_mode?: 'caption' | 'flower';
  emphasis_level?: number;
  motion_preset?: string;
  component?: 'metric_card' | 'spec_chip' | 'benefit_badge' | 'callout' | string;
  variant?: string;
  layout?: string;
  palette?: string;
  motion?: MotionSpec;
  decorations?: DecorationSpec;
  treatment?: string;
  label?: string;
  supporting_text?: string;
};

export type Manifest = {
  version: 1;
  output: {width: number; height: number; fps: number; duration_ms: number};
  video: {path: string; start_ms?: number};
  subtitles: TimedText[];
  visual_events: TimedText[];
  packaging?: {
    hook?: TimedText & {enabled?: boolean};
  };
  audio?: {
    bgm?: {path: string; volume?: number; start_ms?: number; end_ms?: number};
    sfx?: Array<{path: string; start_ms: number; volume?: number}>;
  };
  theme?: string;
  attribution?: unknown[];
};

const msToFrame = (ms: number, fps: number) => Math.max(0, Math.round((ms / 1000) * fps));

const activeAt = (item: TimedText, frame: number, fps: number) => {
  const start = msToFrame(item.start_ms, fps);
  const end = msToFrame(item.end_ms, fps);
  return frame >= start && frame <= end;
};

const mediaSrc = (path: string) => {
  if (/^(https?:|data:|blob:)/.test(path)) {
    return path;
  }
  return staticFile(path);
};

const cleanCaption = (text: string) =>
  text.replace(/[，。！？、；：“”‘’（）《》【】,.!?;:"'()[\]{}<>]/g, '').trim();

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

const resolutionScaleFor = (width: number, height: number) => {
  const shortSide = Math.max(1, Math.min(width, height));
  return clamp(shortSide / 1080, 0.85, 2.2);
};

const px = (value: number, resolutionScale: number) => Math.round(value * resolutionScale * 100) / 100;

const stroke = (value: number, resolutionScale: number, color: string) => `${px(value, resolutionScale)}px ${color}`;

const boostSfxVolume = (volume: number | undefined) => clamp((volume ?? 0.6) * 1.5, 0, 1);

const easeOutCubic = (value: number) => 1 - Math.pow(1 - clamp(value, 0, 1), 3);

const easeOutBack = (value: number) => {
  const t = clamp(value, 0, 1) - 1;
  return 1 + 2.2 * t * t * t + 1.2 * t * t;
};

const activeProgress = (item: TimedText, frame: number, fps: number, frames = 12) => {
  const start = msToFrame(item.start_ms, fps);
  return clamp((frame - start) / frames, 0, 1);
};

const motionPreset = (item: TimedText) => item.motion?.preset || item.motion_preset || 'popElastic';

const motionIntensity = (item: TimedText) => clamp(item.motion?.intensity ?? 0.75, 0.2, 1.4);

const motionFrames = (item: TimedText, fps: number, fallback = 420) => {
  const duration = clamp(item.motion?.duration_ms ?? fallback, 160, 900);
  return Math.max(4, msToFrame(duration, fps));
};

const eventProgress = (item: TimedText, frame: number, fps: number) => activeProgress(item, frame, fps, motionFrames(item, fps));

const semanticColor = (semanticType?: string) => {
  switch (semanticType) {
    case 'number':
      return '#ffd43b';
    case 'risk':
      return '#ff4b4b';
    case 'proof':
      return '#c8ff48';
    case 'benefit':
      return '#74f2ce';
    case 'action':
      return '#6ee7ff';
    case 'emotion':
      return '#ff8bd1';
    case 'entity':
    default:
      return '#f8fbff';
  }
};

const accentColor = (item: TimedText) => semanticColor(item.semantic_type);

type Palette = {
  accent: string;
  text: string;
  muted: string;
  background: string;
  panel: string;
  border: string;
  shadow: string;
};

const paletteFor = (item: TimedText): Palette => {
  const semanticAccent = accentColor(item);
  switch (item.palette) {
    case 'auto_yellow_black':
      return {
        accent: semanticAccent === '#f8fbff' ? '#ffd43b' : semanticAccent,
        text: '#ffffff',
        muted: 'rgba(255,255,255,0.72)',
        background: 'rgba(4,6,8,0.78)',
        panel: 'linear-gradient(135deg, rgba(7,11,18,0.9), rgba(24,27,32,0.76))',
        border: semanticAccent === '#f8fbff' ? '#ffd43b' : semanticAccent,
        shadow: 'rgba(255,212,59,0.22)',
      };
    case 'clean_white_blue':
      return {
        accent: '#2f80ff',
        text: '#071016',
        muted: 'rgba(7,16,22,0.62)',
        background: 'rgba(248,251,255,0.9)',
        panel: 'linear-gradient(135deg, rgba(255,255,255,0.94), rgba(222,237,255,0.86))',
        border: '#2f80ff',
        shadow: 'rgba(47,128,255,0.2)',
      };
    case 'neon_cyan_magenta':
      return {
        accent: '#6ee7ff',
        text: '#ffffff',
        muted: 'rgba(255,255,255,0.72)',
        background: 'rgba(7,7,16,0.72)',
        panel: 'linear-gradient(135deg, rgba(7,7,16,0.88), rgba(34,15,42,0.76))',
        border: '#ff8bd1',
        shadow: 'rgba(110,231,255,0.28)',
      };
    case 'warning_red_black':
      return {
        accent: '#ff4b4b',
        text: '#ffffff',
        muted: 'rgba(255,255,255,0.74)',
        background: 'rgba(16,5,5,0.78)',
        panel: 'linear-gradient(135deg, rgba(20,5,5,0.9), rgba(52,9,9,0.74))',
        border: '#ff4b4b',
        shadow: 'rgba(255,75,75,0.28)',
      };
    case 'fresh_green_dark':
      return {
        accent: '#74f2ce',
        text: '#ffffff',
        muted: 'rgba(255,255,255,0.72)',
        background: 'rgba(3,18,16,0.74)',
        panel: 'linear-gradient(135deg, rgba(3,18,16,0.86), rgba(9,42,36,0.72))',
        border: '#74f2ce',
        shadow: 'rgba(116,242,206,0.24)',
      };
    case 'editorial_black_white':
      return {
        accent: '#ffffff',
        text: '#ffffff',
        muted: 'rgba(255,255,255,0.66)',
        background: 'rgba(0,0,0,0.7)',
        panel: 'rgba(0,0,0,0.78)',
        border: '#ffffff',
        shadow: 'rgba(255,255,255,0.12)',
      };
    case 'semantic_auto':
    default:
      return {
        accent: semanticAccent,
        text: '#ffffff',
        muted: 'rgba(255,255,255,0.74)',
        background: 'rgba(8,11,16,0.76)',
        panel: 'linear-gradient(135deg, rgba(8,11,16,0.88), rgba(23,29,37,0.7))',
        border: semanticAccent,
        shadow: `${semanticAccent}38`,
      };
  }
};

const highlightPosition = (
  lane: string | undefined,
  isVertical: boolean,
  resolutionScale: number,
): React.CSSProperties => {
  const margin = px(isVertical ? 44 : 56, resolutionScale);
  switch (lane) {
    case 'upper-left':
      return {left: margin, top: px(isVertical ? 228 : 110, resolutionScale)};
    case 'middle-left':
      return {left: margin, top: px(isVertical ? 430 : 218, resolutionScale)};
    case 'middle-right':
      return {right: margin, top: px(isVertical ? 510 : 252, resolutionScale)};
    case 'upper-right':
    default:
      return {right: margin, top: px(isVertical ? 286 : 142, resolutionScale)};
  }
};

const layoutPosition = (
  item: TimedText,
  isVertical: boolean,
  resolutionScale: number,
  preferredWidth: number,
): React.CSSProperties => {
  const margin = px(isVertical ? 48 : 68, resolutionScale);
  const width = px(preferredWidth, resolutionScale);
  const layout = item.layout || item.lane || 'upper-right';
  switch (layout) {
    case 'upper-left':
      return {left: margin, top: px(isVertical ? 236 : 118, resolutionScale), width};
    case 'middle-left':
      return {left: margin, top: px(isVertical ? 430 : 218, resolutionScale), width};
    case 'middle-right':
      return {right: margin, top: px(isVertical ? 500 : 252, resolutionScale), width};
    case 'lower-left':
      return {left: margin, bottom: px(isVertical ? 570 : 245, resolutionScale), width};
    case 'lower-right':
      return {right: margin, bottom: px(isVertical ? 570 : 245, resolutionScale), width};
    case 'center':
      return {left: '50%', top: '46%', width, transform: 'translate(-50%, -50%)'};
    case 'top-center':
      return {left: '50%', top: px(isVertical ? 248 : 122, resolutionScale), width, transform: 'translateX(-50%)'};
    case 'lower-third':
      return {
        left: px(isVertical ? 58 : 110, resolutionScale),
        right: px(isVertical ? 58 : 110, resolutionScale),
        bottom: px(isVertical ? 560 : 235, resolutionScale),
      };
    case 'upper-right':
    default:
      return {right: margin, top: px(isVertical ? 300 : 142, resolutionScale), width};
  }
};

const mergeTransforms = (...styles: Array<React.CSSProperties | undefined>) =>
  styles
    .map((style) => style?.transform)
    .filter(Boolean)
    .join(' ');

const DecorationLayer: React.FC<{
  item: TimedText;
  progress: number;
  frame: number;
  resolutionScale: number;
  palette: Palette;
}> = ({item, progress, frame, resolutionScale, palette}) => {
  const decorations = item.decorations || {};
  const sweep = (progress * 120 + frame * 1.2) % 140;
  return (
    <>
      {decorations.sweep_light ? (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: `linear-gradient(105deg, transparent ${Math.max(0, sweep - 18)}%, rgba(255,255,255,0.24) ${sweep}%, transparent ${Math.min(100, sweep + 18)}%)`,
            pointerEvents: 'none',
          }}
        />
      ) : null}
      {decorations.scanline ? (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            opacity: 0.22,
            backgroundImage: `repeating-linear-gradient(0deg, transparent 0, transparent ${px(6, resolutionScale)}px, ${palette.accent} ${px(7, resolutionScale)}px)`,
            mixBlendMode: 'screen',
            pointerEvents: 'none',
          }}
        />
      ) : null}
      {decorations.dot_grid ? (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            opacity: 0.18,
            backgroundImage: `radial-gradient(${palette.accent} ${px(1.2, resolutionScale)}px, transparent ${px(1.2, resolutionScale)}px)`,
            backgroundSize: `${px(14, resolutionScale)}px ${px(14, resolutionScale)}px`,
            pointerEvents: 'none',
          }}
        />
      ) : null}
      {decorations.corner_ticks ? (
        <>
          {['left-top', 'right-top', 'left-bottom', 'right-bottom'].map((corner) => (
            <span
              key={corner}
              style={{
                position: 'absolute',
                width: px(24, resolutionScale),
                height: px(24, resolutionScale),
                borderColor: palette.accent,
                borderStyle: 'solid',
                borderTopWidth: corner.includes('top') ? px(3, resolutionScale) : 0,
                borderBottomWidth: corner.includes('bottom') ? px(3, resolutionScale) : 0,
                borderLeftWidth: corner.includes('left') ? px(3, resolutionScale) : 0,
                borderRightWidth: corner.includes('right') ? px(3, resolutionScale) : 0,
                left: corner.includes('left') ? px(8, resolutionScale) : undefined,
                right: corner.includes('right') ? px(8, resolutionScale) : undefined,
                top: corner.includes('top') ? px(8, resolutionScale) : undefined,
                bottom: corner.includes('bottom') ? px(8, resolutionScale) : undefined,
              }}
            />
          ))}
        </>
      ) : null}
      {decorations.bracket_focus ? (
        <>
          <span
            style={{
              position: 'absolute',
              left: px(-16, resolutionScale),
              top: '18%',
              bottom: '18%',
              width: px(10, resolutionScale),
              borderLeft: `${px(4, resolutionScale)}px solid ${palette.accent}`,
              borderTop: `${px(4, resolutionScale)}px solid ${palette.accent}`,
              borderBottom: `${px(4, resolutionScale)}px solid ${palette.accent}`,
            }}
          />
          <span
            style={{
              position: 'absolute',
              right: px(-16, resolutionScale),
              top: '18%',
              bottom: '18%',
              width: px(10, resolutionScale),
              borderRight: `${px(4, resolutionScale)}px solid ${palette.accent}`,
              borderTop: `${px(4, resolutionScale)}px solid ${palette.accent}`,
              borderBottom: `${px(4, resolutionScale)}px solid ${palette.accent}`,
            }}
          />
        </>
      ) : null}
      {decorations.arrow ? (
        <div
          style={{
            position: 'absolute',
            right: px(-34, resolutionScale),
            top: '50%',
            width: 0,
            height: 0,
            borderTop: `${px(15, resolutionScale)}px solid transparent`,
            borderBottom: `${px(15, resolutionScale)}px solid transparent`,
            borderLeft: `${px(24, resolutionScale)}px solid ${palette.accent}`,
            transform: 'translateY(-50%)',
          }}
        />
      ) : null}
      {decorations.progress_bar ? (
        <div
          style={{
            position: 'absolute',
            left: px(14, resolutionScale),
            right: px(14, resolutionScale),
            bottom: px(12, resolutionScale),
            height: px(5, resolutionScale),
            background: 'rgba(255,255,255,0.14)',
          }}
        >
          <div
            style={{
              height: '100%',
              width: `${Math.round(100 * easeOutCubic(progress))}%`,
              background: palette.accent,
              boxShadow: `0 0 ${px(14, resolutionScale)}px ${palette.accent}`,
            }}
          />
        </div>
      ) : null}
    </>
  );
};

const underliner = (item: TimedText, progress: number, resolutionScale: number, palette: Palette) =>
  item.decorations?.underline ? (
    <div
      style={{
        height: px(5, resolutionScale),
        marginTop: px(8, resolutionScale),
        background: palette.accent,
        transformOrigin: 'left center',
        transform: `scaleX(${easeOutCubic(progress)})`,
        boxShadow: `0 0 ${px(14, resolutionScale)}px ${palette.accent}`,
      }}
    />
  ) : null;

const motionStyle = (
  item: TimedText,
  progress: number,
  resolutionScale: number,
  frame: number,
  fps: number,
): React.CSSProperties => {
  const preset = motionPreset(item);
  const intensity = motionIntensity(item);
  const springEnter = spring({
    frame: Math.max(0, frame - msToFrame(item.start_ms, fps)),
    fps,
    config: {damping: 14, stiffness: 120, mass: 0.9},
    durationInFrames: motionFrames(item, fps),
  });
  const enter = preset === 'stampIn' || preset === 'numberBurst' || preset === 'hookSnap' || preset === 'speedCount' ? easeOutBack(progress) : easeOutCubic(progress);
  const opacity = interpolate(progress, [0, 0.55, 1], [0, 1, 1], {extrapolateRight: 'clamp'});
  const shake = Math.sin(frame * 1.7) * px(3 * intensity, resolutionScale) * (1 - progress);
  switch (preset) {
    case 'impactZoom':
      return {
        opacity,
        transform: `translateY(${px(10 * intensity * (1 - enter), resolutionScale)}px) scale(${0.66 + enter * (0.36 + 0.08 * intensity)}) rotate(${(1 - enter) * -3 * intensity}deg)`,
        filter: `drop-shadow(0 ${px(12, resolutionScale)}px ${px(24, resolutionScale)}px rgba(255,212,59,0.26))`,
      };
    case 'chipSlide':
      return {
        opacity,
        transform: `translateX(${px(46 * intensity * (1 - enter), resolutionScale)}px) scale(${0.9 + enter * 0.1})`,
      };
    case 'badgeSweep':
      return {
        opacity,
        transform: `translateY(${px(18 * intensity * (1 - enter), resolutionScale)}px) scale(${0.9 + enter * 0.1})`,
      };
    case 'scanReveal':
      return {
        opacity,
        clipPath: `inset(0 ${Math.round((1 - enter) * 100)}% 0 0)`,
        transform: `translateX(${px(-18 * intensity * (1 - enter), resolutionScale)}px)`,
      };
    case 'ribbonSnap':
      return {
        opacity,
        transform: `translateX(${px(-58 * intensity * (1 - enter), resolutionScale)}px) skewX(${(1 - enter) * -8 * intensity}deg)`,
      };
    case 'bracketPop':
      return {
        opacity,
        transform: `scale(${0.82 + springEnter * 0.18})`,
      };
    case 'speedCount':
      return {
        opacity,
        transform: `scale(${0.76 + springEnter * 0.26}) rotate(${(1 - enter) * -6 * intensity}deg)`,
        filter: `drop-shadow(0 0 ${px(18 + 12 * enter, resolutionScale)}px rgba(255,212,59,0.36))`,
      };
    case 'numberBurst':
      return {
        opacity,
        transform: `translateY(${px(18 * intensity * (1 - enter), resolutionScale)}px) scale(${0.72 + enter * 0.34}) rotate(${(1 - enter) * -5 * intensity}deg)`,
        filter: `drop-shadow(0 ${px(10, resolutionScale)}px ${px(18, resolutionScale)}px rgba(0,0,0,0.38))`,
      };
    case 'stampIn':
      return {
        opacity,
        transform: `scale(${1.28 - enter * 0.28}) rotate(${(1 - enter) * -9 * intensity}deg)`,
      };
    case 'slideSnap':
      return {
        opacity,
        transform: `translateX(${px(-42 * intensity * (1 - enter), resolutionScale)}px) scale(${0.96 + enter * 0.04})`,
      };
    case 'warningShake':
      return {
        opacity,
        transform: `translateX(${shake}px) scale(${0.86 + enter * 0.14}) rotate(${Math.sin(frame * 0.9) * 1.6 * intensity * (1 - progress)}deg)`,
      };
    case 'softGlow':
      return {
        opacity,
        transform: `translateY(${px(22 * intensity * (1 - enter), resolutionScale)}px) scale(${0.92 + enter * 0.08})`,
        filter: `drop-shadow(0 0 ${px(16 + 10 * enter, resolutionScale)}px rgba(116,242,206,0.44))`,
      };
    case 'cardRise':
      return {
        opacity,
        transform: `translateY(${px(26 * intensity * (1 - enter), resolutionScale)}px) scale(${0.94 + enter * 0.06})`,
      };
    case 'hookSnap':
      return {
        opacity,
        transform: `translateY(${px(36 * intensity * (1 - enter), resolutionScale)}px) scale(${0.78 + enter * 0.22})`,
      };
    case 'popElastic':
    default:
      return {
        opacity,
        transform: `scale(${0.78 + enter * 0.22})`,
      };
  }
};

const PackagingLayer: React.FC<{
  hook?: TimedText & {enabled?: boolean};
  frame: number;
  fps: number;
  isVertical: boolean;
  resolutionScale: number;
}> = ({hook, frame, fps, isVertical, resolutionScale}) => {
  if (!hook?.enabled || !activeAt(hook, frame, fps)) {
    return null;
  }
  const progress = eventProgress(hook, frame, fps);
  const exitStart = msToFrame(hook.end_ms, fps) - 10;
  const exitProgress = clamp((frame - exitStart) / 10, 0, 1);
  const palette = paletteFor(hook);
  const color = palette.accent;
  const variant = hook.variant || 'product_launch';
  const label = cleanCaption(hook.label || (variant === 'editorial_clean' ? '重点' : variant === 'punch_number' ? '核心数字' : '开场重点'));
  const hookLayout = layoutPosition(hook, isVertical, resolutionScale, isVertical ? 660 : 720);
  const hookMotion = motionStyle({...hook, motion_preset: 'hookSnap'}, progress, resolutionScale, frame, fps);
  return (
    <AbsoluteFill
      style={{
        pointerEvents: 'none',
        background: `rgba(0,0,0,${0.34 * (1 - exitProgress)})`,
        opacity: 1 - exitProgress,
      }}
    >
      <div
        style={{
          position: 'absolute',
          overflow: 'hidden',
          padding: variant === 'editorial_clean' ? `${px(10, resolutionScale)}px 0` : 0,
          ...hookLayout,
          ...hookMotion,
          transform: mergeTransforms(hookLayout, hookMotion),
        }}
      >
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: px(10, resolutionScale),
            padding: `${px(7, resolutionScale)}px ${px(14, resolutionScale)}px`,
            color: variant === 'editorial_clean' ? palette.text : color,
            background: variant === 'editorial_clean' ? 'rgba(255,255,255,0.16)' : palette.background,
            border: `${px(2, resolutionScale)}px solid ${color}`,
            fontSize: px(isVertical ? 22 : 17, resolutionScale),
            fontWeight: 900,
            lineHeight: 1,
          }}
        >
          <span style={{width: px(8, resolutionScale), height: px(8, resolutionScale), background: color}} />
          {label}
        </div>
        <div
          style={{
            marginTop: px(18, resolutionScale),
            color: variant === 'punch_number' ? color : palette.text,
            fontSize: px(variant === 'punch_number' ? (isVertical ? 86 : 64) : isVertical ? 72 : 52, resolutionScale),
            fontWeight: 950,
            lineHeight: 1.02,
            textAlign: 'left',
            WebkitTextStroke: stroke(isVertical ? 1.7 : 1.3, resolutionScale, 'rgba(0,0,0,0.82)'),
            textShadow: `${px(3, resolutionScale)}px ${px(5, resolutionScale)}px 0 rgba(0,0,0,0.58), 0 ${px(16, resolutionScale)}px ${px(28, resolutionScale)}px rgba(0,0,0,0.42)`,
          }}
        >
          {cleanCaption(hook.text)}
        </div>
        <div
          style={{
            marginTop: px(12, resolutionScale),
            display: 'flex',
            gap: px(8, resolutionScale),
            alignItems: 'center',
            color: 'rgba(255,255,255,0.78)',
            fontSize: px(isVertical ? 18 : 14, resolutionScale),
            fontWeight: 800,
            letterSpacing: 0,
          }}
        >
          <span style={{width: px(52, resolutionScale), height: px(2, resolutionScale), background: color}} />
          {cleanCaption(hook.supporting_text || hook.semantic_type || 'DIRECTOR PICK')}
          <span style={{width: px(52, resolutionScale), height: px(2, resolutionScale), background: color}} />
        </div>
        <div
          style={{
            width: px(isVertical ? 180 : 150, resolutionScale),
            height: px(8, resolutionScale),
            marginTop: px(18, resolutionScale),
            background: color,
            boxShadow: `0 0 ${px(18, resolutionScale)}px ${color}`,
          }}
        />
        <DecorationLayer item={hook} progress={progress} frame={frame} resolutionScale={resolutionScale} palette={palette} />
      </div>
    </AbsoluteFill>
  );
};

const FlowerEmphasis: React.FC<{
  item: TimedText;
  frame: number;
  fps: number;
  isVertical: boolean;
  resolutionScale: number;
}> = ({item, frame, fps, isVertical, resolutionScale}) => {
  const progress = eventProgress(item, frame, fps);
  const color = accentColor(item);
  const component = item.component || '';
  if (component === 'metric_card') {
    return (
      <MetricCard item={item} progress={progress} frame={frame} fps={fps} isVertical={isVertical} resolutionScale={resolutionScale} />
    );
  }
  if (component === 'spec_chip') {
    return (
      <SpecChip item={item} progress={progress} frame={frame} fps={fps} isVertical={isVertical} resolutionScale={resolutionScale} />
    );
  }
  if (component === 'benefit_badge') {
    return (
      <BenefitBadge item={item} progress={progress} frame={frame} fps={fps} isVertical={isVertical} resolutionScale={resolutionScale} />
    );
  }
  if (component === 'callout') {
    return (
      <Callout item={item} progress={progress} frame={frame} fps={fps} isVertical={isVertical} resolutionScale={resolutionScale} />
    );
  }
  const palette = paletteFor(item);
  const layout = layoutPosition(item, isVertical, resolutionScale, isVertical ? 460 : 380);
  const motion = motionStyle(item, progress, resolutionScale, frame, fps);
  const base: React.CSSProperties = {
    position: 'absolute',
    maxWidth: isVertical ? '62%' : '48%',
    padding: `${px(isVertical ? 16 : 12, resolutionScale)}px ${px(isVertical ? 22 : 18, resolutionScale)}px`,
    color: palette.text,
    fontWeight: 950,
    lineHeight: 1.02,
    textAlign: 'center',
    background: palette.background,
    border: `${px(2.5, resolutionScale)}px solid ${palette.border}`,
    boxShadow: `0 ${px(10, resolutionScale)}px ${px(24, resolutionScale)}px rgba(0,0,0,0.38), 0 0 ${px(22, resolutionScale)}px ${palette.shadow}, inset 0 0 0 ${px(1, resolutionScale)}px rgba(255,255,255,0.16)`,
    WebkitTextStroke: stroke(isVertical ? 1.8 : 1.4, resolutionScale, 'rgba(0,0,0,0.78)'),
    textShadow: `0 ${px(4, resolutionScale)}px ${px(12, resolutionScale)}px rgba(0,0,0,0.48)`,
    ...layout,
    ...motion,
    transform: mergeTransforms(layout, motion),
    overflow: 'hidden',
  };
  const semanticType = item.semantic_type || 'entity';
  const fontSize = px(semanticType === 'number' ? (isVertical ? 64 : 50) : isVertical ? 46 : 34, resolutionScale);
  return (
    <div style={{...base, fontSize}}>
      {semanticType === 'proof' ? (
        <div
          style={{
            position: 'absolute',
            right: px(-14, resolutionScale),
            top: px(-16, resolutionScale),
            padding: `${px(5, resolutionScale)}px ${px(9, resolutionScale)}px`,
            color: '#0a0d10',
            background: color,
            fontSize: px(isVertical ? 18 : 14, resolutionScale),
            fontWeight: 950,
            transform: 'rotate(8deg)',
          }}
        >
          PROOF
        </div>
      ) : null}
      {semanticType === 'risk' ? (
        <div
          style={{
            position: 'absolute',
            left: px(-12, resolutionScale),
            top: px(-12, resolutionScale),
            width: px(34, resolutionScale),
            height: px(34, resolutionScale),
            color: '#050505',
            background: color,
            fontSize: px(24, resolutionScale),
            lineHeight: `${px(34, resolutionScale)}px`,
          }}
        >
          !
        </div>
      ) : null}
      <span style={{color: semanticType === 'number' ? color : palette.text}}>{cleanCaption(item.text)}</span>
      {underliner(item, progress, resolutionScale, palette)}
      <DecorationLayer item={item} progress={progress} frame={frame} resolutionScale={resolutionScale} palette={palette} />
    </div>
  );
};

const MetricCard: React.FC<{
  item: TimedText;
  progress: number;
  frame: number;
  fps: number;
  isVertical: boolean;
  resolutionScale: number;
}> = ({item, progress, frame, fps, isVertical, resolutionScale}) => {
  const palette = paletteFor(item);
  const variant = item.variant || 'dashboard_glow';
  const layout = layoutPosition(item, isVertical, resolutionScale, variant === 'giant_number' ? (isVertical ? 430 : 360) : isVertical ? 350 : 290);
  const motion = motionStyle({...item, motion_preset: item.motion_preset || (variant === 'speedometer' ? 'speedCount' : 'impactZoom')}, progress, resolutionScale, frame, fps);
  const sweep = easeOutCubic(progress);
  const text = cleanCaption(item.text);
  const label = cleanCaption(item.label || '核心指标');
  const support = cleanCaption(item.supporting_text || '关键数值');
  const isClean = variant === 'minimal_clean';
  if (variant === 'giant_number') {
    return (
      <div
        style={{
          position: 'absolute',
          padding: `${px(4, resolutionScale)}px ${px(8, resolutionScale)}px`,
          color: palette.accent,
          textAlign: 'left',
          ...layout,
          ...motion,
          transform: mergeTransforms(layout, motion),
        }}
      >
        <div style={{fontSize: px(isVertical ? 24 : 18, resolutionScale), color: palette.muted, fontWeight: 900}}>{label}</div>
        <div
          style={{
            fontSize: px(isVertical ? 104 : 76, resolutionScale),
            fontWeight: 950,
            lineHeight: 0.9,
            WebkitTextStroke: stroke(2, resolutionScale, 'rgba(0,0,0,0.82)'),
            textShadow: `0 ${px(10, resolutionScale)}px ${px(22, resolutionScale)}px rgba(0,0,0,0.52), 0 0 ${px(24, resolutionScale)}px ${palette.shadow}`,
          }}
        >
          {text}
        </div>
        <div
          style={{
            width: px(isVertical ? 310 : 245, resolutionScale),
            height: px(7, resolutionScale),
            marginTop: px(10, resolutionScale),
            background: palette.accent,
            transformOrigin: 'left center',
            transform: `scaleX(${easeOutCubic(progress)})`,
            boxShadow: `0 0 ${px(15, resolutionScale)}px ${palette.accent}`,
          }}
        />
      </div>
    );
  }
  if (variant === 'speedometer') {
    return (
      <div
        style={{
          position: 'absolute',
          width: px(isVertical ? 350 : 300, resolutionScale),
          height: px(isVertical ? 210 : 174, resolutionScale),
          color: palette.text,
          ...layout,
          ...motion,
          transform: mergeTransforms(layout, motion),
        }}
      >
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            bottom: 0,
            height: px(isVertical ? 178 : 146, resolutionScale),
            borderTop: `${px(12, resolutionScale)}px solid ${palette.accent}`,
            borderLeft: `${px(12, resolutionScale)}px solid rgba(255,255,255,0.18)`,
            borderRight: `${px(12, resolutionScale)}px solid rgba(255,255,255,0.18)`,
            borderRadius: `${px(180, resolutionScale)}px ${px(180, resolutionScale)}px 0 0`,
            background: palette.background,
            boxShadow: `0 ${px(12, resolutionScale)}px ${px(28, resolutionScale)}px rgba(0,0,0,0.42), 0 0 ${px(26, resolutionScale)}px ${palette.shadow}`,
          }}
        />
        <div style={{position: 'absolute', left: px(28, resolutionScale), right: px(28, resolutionScale), bottom: px(28, resolutionScale), textAlign: 'center'}}>
          <div style={{fontSize: px(isVertical ? 19 : 15, resolutionScale), color: palette.muted, fontWeight: 900}}>{label}</div>
          <div style={{fontSize: px(isVertical ? 70 : 54, resolutionScale), color: palette.accent, fontWeight: 950, lineHeight: 0.96}}>{text}</div>
          <div style={{fontSize: px(isVertical ? 16 : 13, resolutionScale), color: palette.muted, fontWeight: 800}}>{support}</div>
        </div>
      </div>
    );
  }
  return (
    <div
      style={{
        position: 'absolute',
        padding: `${px(18, resolutionScale)}px ${px(22, resolutionScale)}px ${px(20, resolutionScale)}px`,
        color: palette.text,
        background: isClean ? palette.panel : palette.panel,
        border: `${px(isClean ? 1.5 : 2, resolutionScale)}px solid ${palette.border}`,
        boxShadow: isClean
          ? `0 ${px(10, resolutionScale)}px ${px(20, resolutionScale)}px rgba(0,0,0,0.24)`
          : `0 ${px(14, resolutionScale)}px ${px(34, resolutionScale)}px rgba(0,0,0,0.46), 0 0 ${px(26, resolutionScale)}px ${palette.shadow}`,
        overflow: 'hidden',
        ...layout,
        ...motion,
        transform: mergeTransforms(layout, motion),
      }}
    >
      {item.decorations?.sweep_light === false ? null : (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: `linear-gradient(105deg, transparent ${Math.max(0, sweep * 100 - 18)}%, rgba(255,255,255,0.2) ${sweep * 100}%, transparent ${Math.min(100, sweep * 100 + 18)}%)`,
          }}
        />
      )}
      <div style={{position: 'relative', color: palette.muted, fontSize: px(17, resolutionScale), fontWeight: 900}}>
        {label}
      </div>
      <div
        style={{
          position: 'relative',
          marginTop: px(6, resolutionScale),
          color: palette.accent,
          fontSize: px(isVertical ? 78 : 58, resolutionScale),
          fontWeight: 950,
          lineHeight: 0.96,
          WebkitTextStroke: stroke(1.6, resolutionScale, 'rgba(0,0,0,0.72)'),
          textShadow: `0 ${px(7, resolutionScale)}px ${px(16, resolutionScale)}px rgba(0,0,0,0.48)`,
        }}
      >
        {text}
      </div>
      <div style={{position: 'relative', marginTop: px(12, resolutionScale), height: px(6, resolutionScale), background: 'rgba(255,255,255,0.16)'}}>
        <div style={{height: '100%', width: `${Math.round(100 * sweep)}%`, background: palette.accent, boxShadow: `0 0 ${px(16, resolutionScale)}px ${palette.accent}`}} />
      </div>
      <div style={{position: 'relative', marginTop: px(10, resolutionScale), color: palette.muted, fontSize: px(16, resolutionScale), fontWeight: 800}}>
        {support}
      </div>
      <DecorationLayer item={item} progress={progress} frame={frame} resolutionScale={resolutionScale} palette={palette} />
    </div>
  );
};

const SpecChip: React.FC<{
  item: TimedText;
  progress: number;
  frame: number;
  fps: number;
  isVertical: boolean;
  resolutionScale: number;
}> = ({item, progress, frame, fps, isVertical, resolutionScale}) => {
  const palette = paletteFor(item);
  const variant = item.variant || 'dark_glass';
  const layout = layoutPosition(item, isVertical, resolutionScale, variant === 'stacked_specs' ? (isVertical ? 310 : 260) : isVertical ? 300 : 250);
  const motion = motionStyle({...item, motion_preset: item.motion_preset || 'chipSlide'}, progress, resolutionScale, frame, fps);
  const text = cleanCaption(item.text);
  const label = cleanCaption(item.label || item.supporting_text || '');
  const isWhite = variant === 'white_label';
  const isStacked = variant === 'stacked_specs';
  return (
    <div
      style={{
        position: 'absolute',
        display: 'flex',
        flexDirection: isStacked ? 'column' : 'row',
        alignItems: isStacked ? 'flex-start' : 'center',
        gap: px(10, resolutionScale),
        padding: `${px(isStacked ? 16 : 13, resolutionScale)}px ${px(isStacked ? 20 : 18, resolutionScale)}px`,
        color: isWhite ? '#061016' : variant === 'neon_pill' ? palette.accent : palette.text,
        background: isWhite ? 'rgba(255,255,255,0.92)' : variant === 'neon_pill' ? 'rgba(0,0,0,0.42)' : palette.background,
        border: variant === 'neon_pill' ? `${px(2, resolutionScale)}px solid ${palette.accent}` : `${px(1, resolutionScale)}px solid rgba(255,255,255,0.2)`,
        boxShadow: `0 ${px(10, resolutionScale)}px ${px(24, resolutionScale)}px rgba(0,0,0,0.34), 0 0 ${px(18, resolutionScale)}px ${palette.shadow}`,
        fontWeight: 950,
        fontSize: px(isVertical ? 36 : 28, resolutionScale),
        lineHeight: 1,
        overflow: 'hidden',
        ...layout,
        ...motion,
        transform: mergeTransforms(layout, motion),
      }}
    >
      {label ? <span style={{color: isWhite ? 'rgba(6,16,22,0.58)' : palette.muted, fontSize: px(isVertical ? 17 : 13, resolutionScale)}}>{label}</span> : null}
      <span style={{display: 'inline-flex', alignItems: 'center', gap: px(10, resolutionScale)}}>
        <span style={{width: px(8, resolutionScale), height: px(28, resolutionScale), background: isWhite ? palette.accent : 'rgba(255,255,255,0.78)'}} />
        {text}
      </span>
      <DecorationLayer item={item} progress={progress} frame={frame} resolutionScale={resolutionScale} palette={palette} />
    </div>
  );
};

const BenefitBadge: React.FC<{
  item: TimedText;
  progress: number;
  frame: number;
  fps: number;
  isVertical: boolean;
  resolutionScale: number;
}> = ({item, progress, frame, fps, isVertical, resolutionScale}) => {
  const palette = paletteFor(item);
  const variant = item.variant || 'scanline_bar';
  const layout = layoutPosition(item, isVertical, resolutionScale, isVertical ? 360 : 300);
  const motion = motionStyle({...item, motion_preset: item.motion_preset || (variant === 'left_ribbon' ? 'ribbonSnap' : 'badgeSweep')}, progress, resolutionScale, frame, fps);
  const text = cleanCaption(item.text);
  const label = cleanCaption(item.label || '');
  const ribbon = variant === 'left_ribbon';
  const glow = variant === 'glow_label';
  return (
    <div
      style={{
        position: 'absolute',
        padding: `${px(ribbon ? 12 : 10, resolutionScale)}px ${px(ribbon ? 22 : 16, resolutionScale)}px`,
        color: glow ? palette.text : palette.accent,
        background: ribbon ? palette.accent : glow ? palette.panel : palette.background,
        borderLeft: ribbon ? 0 : `${px(7, resolutionScale)}px solid ${palette.accent}`,
        borderTop: `${px(1, resolutionScale)}px solid rgba(255,255,255,0.24)`,
        borderBottom: `${px(1, resolutionScale)}px solid rgba(255,255,255,0.18)`,
        fontSize: px(isVertical ? 34 : 26, resolutionScale),
        fontWeight: 950,
        boxShadow: glow
          ? `0 ${px(8, resolutionScale)}px ${px(20, resolutionScale)}px rgba(0,0,0,0.32), 0 0 ${px(26, resolutionScale)}px ${palette.shadow}`
          : `0 ${px(8, resolutionScale)}px ${px(20, resolutionScale)}px rgba(0,0,0,0.32)`,
        overflow: 'hidden',
        ...layout,
        ...motion,
        transform: mergeTransforms(layout, motion),
      }}
    >
      {label ? <div style={{color: ribbon ? 'rgba(0,0,0,0.58)' : palette.muted, fontSize: px(isVertical ? 15 : 12, resolutionScale), marginBottom: px(4, resolutionScale)}}>{label}</div> : null}
      <span style={{color: ribbon ? '#061016' : undefined}}>{text}</span>
      <DecorationLayer item={{...item, decorations: {scanline: variant === 'scanline_bar', ...item.decorations}}} progress={progress} frame={frame} resolutionScale={resolutionScale} palette={palette} />
    </div>
  );
};

const Callout: React.FC<{
  item: TimedText;
  progress: number;
  frame: number;
  fps: number;
  isVertical: boolean;
  resolutionScale: number;
}> = ({item, progress, frame, fps, isVertical, resolutionScale}) => {
  const palette = paletteFor(item);
  const variant = item.variant || 'bracket_focus';
  const layout = layoutPosition(item, isVertical, resolutionScale, isVertical ? 390 : 320);
  const motion = motionStyle({...item, motion_preset: item.motion_preset || 'bracketPop'}, progress, resolutionScale, frame, fps);
  const decorations = {
    bracket_focus: variant === 'bracket_focus',
    arrow: variant === 'arrow_pointer',
    scanline: variant === 'area_scan',
    corner_ticks: variant === 'area_scan',
    ...item.decorations,
  };
  return (
    <div
      style={{
        position: 'absolute',
        padding: `${px(16, resolutionScale)}px ${px(20, resolutionScale)}px`,
        color: palette.text,
        background: variant === 'arrow_pointer' ? palette.panel : palette.background,
        border: `${px(2, resolutionScale)}px solid ${palette.border}`,
        boxShadow: `0 ${px(12, resolutionScale)}px ${px(26, resolutionScale)}px rgba(0,0,0,0.36), 0 0 ${px(22, resolutionScale)}px ${palette.shadow}`,
        fontSize: px(isVertical ? 34 : 26, resolutionScale),
        fontWeight: 950,
        lineHeight: 1.08,
        overflow: 'visible',
        ...layout,
        ...motion,
        transform: mergeTransforms(layout, motion),
      }}
    >
      <div style={{position: 'relative', zIndex: 1}}>{cleanCaption(item.text)}</div>
      {item.supporting_text ? (
        <div style={{position: 'relative', zIndex: 1, marginTop: px(6, resolutionScale), color: palette.muted, fontSize: px(isVertical ? 16 : 13, resolutionScale), fontWeight: 800}}>
          {cleanCaption(item.supporting_text)}
        </div>
      ) : null}
      <DecorationLayer item={{...item, decorations}} progress={progress} frame={frame} resolutionScale={resolutionScale} palette={palette} />
    </div>
  );
};

const EmphasisLayer: React.FC<{
  events: TimedText[];
  frame: number;
  fps: number;
  isVertical: boolean;
  resolutionScale: number;
}> = ({events, frame, fps, isVertical, resolutionScale}) => {
  const flowerEvents = events.filter((item) => (item.render_mode || 'flower') === 'flower');
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      {flowerEvents.map((item, index) => (
        <FlowerEmphasis
          key={`${item.text}-${item.start_ms}-${index}`}
          item={item}
          frame={frame}
          fps={fps}
          isVertical={isVertical}
          resolutionScale={resolutionScale}
        />
      ))}
    </AbsoluteFill>
  );
};

const captionParts = (text: string, events: TimedText[]) => {
  const clean = cleanCaption(text);
  const matches: Array<{start: number; end: number; event: TimedText}> = [];
  for (const event of events) {
    const phrase = cleanCaption(event.text);
    if (!phrase || phrase.length < 2) {
      continue;
    }
    const start = clean.indexOf(phrase);
    if (start >= 0) {
      matches.push({start, end: start + phrase.length, event});
    }
  }
  matches.sort((left, right) => left.start - right.start || right.end - right.start - (left.end - left.start));
  const parts: Array<{text: string; event?: TimedText}> = [];
  let cursor = 0;
  for (const match of matches) {
    if (match.start < cursor) {
      continue;
    }
    if (match.start > cursor) {
      parts.push({text: clean.slice(cursor, match.start)});
    }
    parts.push({text: clean.slice(match.start, match.end), event: match.event});
    cursor = match.end;
  }
  if (cursor < clean.length) {
    parts.push({text: clean.slice(cursor)});
  }
  return parts.length ? parts : [{text: clean}];
};

const CaptionLayer: React.FC<{
  subtitle?: TimedText;
  activeEvents: TimedText[];
  isVertical: boolean;
  resolutionScale: number;
}> = ({subtitle, activeEvents, isVertical, resolutionScale}) => {
  if (!subtitle) {
    return null;
  }
  const parts = captionParts(subtitle.text, activeEvents);
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div
        style={{
          position: 'absolute',
          left: px(isVertical ? 42 : 72, resolutionScale),
          right: px(isVertical ? 42 : 72, resolutionScale),
          bottom: px(isVertical ? 390 : 160, resolutionScale),
          minHeight: px(isVertical ? 112 : 82, resolutionScale),
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'center',
          padding: `${px(isVertical ? 6 : 4, resolutionScale)}px ${px(isVertical ? 18 : 16, resolutionScale)}px`,
          color: 'white',
          fontFamily: '"Microsoft YaHei", "微软雅黑", "PingFang SC", Arial, sans-serif',
          fontSize: px(isVertical ? 46 : 36, resolutionScale),
          fontWeight: 850,
          lineHeight: 1.16,
          textAlign: 'center',
          whiteSpace: 'pre-line',
          wordBreak: 'break-word',
          overflowWrap: 'anywhere',
          WebkitTextStroke: stroke(isVertical ? 1.8 : 1.4, resolutionScale, 'rgba(0,0,0,0.88)'),
          textShadow: `0 ${px(3, resolutionScale)}px 0 rgba(0,0,0,0.82), 0 ${px(8, resolutionScale)}px ${px(18, resolutionScale)}px rgba(0,0,0,0.58)`,
        }}
      >
        <span>
          {parts.map((part, index) => {
            if (!part.event) {
              return <span key={`${part.text}-${index}`}>{part.text}</span>;
            }
            const color = accentColor(part.event);
            return (
              <span
                key={`${part.text}-${index}`}
                style={{
                  color,
                  display: 'inline-block',
                  padding: `0 ${px(3, resolutionScale)}px`,
                  WebkitTextStroke: stroke(isVertical ? 1.4 : 1.1, resolutionScale, 'rgba(0,0,0,0.9)'),
                  textShadow: `0 0 ${px(12, resolutionScale)}px ${color}, 0 ${px(4, resolutionScale)}px ${px(12, resolutionScale)}px rgba(0,0,0,0.72)`,
                }}
              >
                {part.text}
              </span>
            );
          })}
        </span>
      </div>
    </AbsoluteFill>
  );
};

export const TalkingVideo: React.FC<{manifest: Manifest}> = ({manifest}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const activeSubtitle = manifest.subtitles.find((item) => activeAt(item, frame, fps));
  const activeEvents = manifest.visual_events.filter((item) => activeAt(item, frame, fps));
  const captionEvents = activeEvents.filter((item) => item.render_mode === 'caption');
  const isVertical = height > width;
  const resolutionScale = resolutionScaleFor(width, height);

  return (
    <AbsoluteFill style={{backgroundColor: '#050505'}}>
      <OffthreadVideo src={mediaSrc(manifest.video.path)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
      <PackagingLayer
        hook={manifest.packaging?.hook}
        frame={frame}
        fps={fps}
        isVertical={isVertical}
        resolutionScale={resolutionScale}
      />
      <EmphasisLayer
        events={activeEvents}
        frame={frame}
        fps={fps}
        isVertical={isVertical}
        resolutionScale={resolutionScale}
      />
      <CaptionLayer subtitle={activeSubtitle} activeEvents={captionEvents} isVertical={isVertical} resolutionScale={resolutionScale} />
      {manifest.audio?.bgm?.path ? (
        <Sequence from={msToFrame(manifest.audio.bgm.start_ms ?? 0, fps)}>
          <Audio src={mediaSrc(manifest.audio.bgm.path)} volume={manifest.audio.bgm.volume ?? 0.18} />
        </Sequence>
      ) : null}
      {manifest.audio?.sfx?.map((sfx, index) => (
        <Sequence key={index} from={msToFrame(sfx.start_ms, fps)}>
          <Audio src={mediaSrc(sfx.path)} volume={boostSfxVolume(sfx.volume)} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
