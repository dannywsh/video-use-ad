import React from 'react';
import {
  AbsoluteFill, CanvasImage, Interactive, interpolate, Easing, staticFile, useCurrentFrame, useVideoConfig,
} from 'remotion';
import {Prize, SceneProps} from '../../schema';
import {CenteredText, fitLines, FONT} from '../../text';

const ease = Easing.bezier(0.16, 1, 0.3, 1);
const clamped = {extrapolateLeft: 'clamp' as const, extrapolateRight: 'clamp' as const, easing: ease};

// 功能：绘制由帧驱动的星点、光束与全息轨道；输入：主题色；返回：可重复渲染的背景组件。
const Atmosphere: React.FC<{accent: string; background: string}> = ({accent, background}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return <AbsoluteFill style={{overflow: 'hidden', background}}>
    <AbsoluteFill style={{background: `radial-gradient(ellipse at 50% 43%, ${accent}32, transparent 65%), radial-gradient(ellipse at 85% 9%, ${accent}1F, transparent 40%), linear-gradient(160deg,#151025,#080711 60%,#151126)`}}/>
    <AbsoluteFill style={{opacity: 0.18, backgroundImage: `radial-gradient(${accent} 1px,transparent 1px)`, backgroundSize: '26px 26px', maskImage: 'linear-gradient(transparent,#000,transparent)'}}/>
    <div style={{position: 'absolute', left: 140, top: -440, width: 380, height: 2350,
      background: `linear-gradient(90deg,transparent,${accent}0D,transparent)`, rotate: '-24deg',
      translate: `${Math.sin(frame / fps * 0.3) * 70}px 0px`}}/>
    <div style={{position: 'absolute', left: 42, right: 42, top: 42, bottom: 108,
      border: `1px solid ${accent}2B`, clipPath: 'polygon(0 0,100% 0,100% 100%,0 100%,0 88%,1px 88%,1px 12%,0 12%)'}}/>
    {Array.from({length: 26}, (_, i) => <div key={i} style={{position: 'absolute',
      left: 55 + ((i * 163) % 970), top: 180 + ((i * 277) % 1400), width: i % 4 === 0 ? 5 : 3,
      height: i % 4 === 0 ? 5 : 3, borderRadius: '50%', background: accent,
      opacity: 0.12 + (Math.sin(frame / fps * 1.4 + i * 2.2) + 1) * 0.18,
      translate: `0px ${Math.sin(frame / fps * 0.6 + i) * 14}px`, boxShadow: `0 0 14px ${accent}90`}}/>)}
    <div style={{position: 'absolute', left: 540 - 480, top: 418, width: 960, height: 940,
      rotate: `${frame / fps * 3}deg`, opacity: 0.52}}>
      <svg viewBox="0 0 960 940" width="960" height="940">
        <defs><linearGradient id="orbit"><stop stopColor={accent} stopOpacity="0.06"/><stop offset="0.45" stopColor={accent}/><stop offset="1" stopColor={accent} stopOpacity="0.06"/></linearGradient></defs>
        <ellipse cx="480" cy="470" rx="450" ry="380" fill="none" stroke="url(#orbit)" strokeWidth="2" transform="rotate(-28 480 470)"/>
        <ellipse cx="480" cy="470" rx="420" ry="465" fill="none" stroke="url(#orbit)" strokeWidth="1" strokeDasharray="4 14"/>
        <path d="M40 470A440 400 0 0 1 920 470" fill="none" stroke={accent} strokeOpacity="0.4" strokeWidth="4"/>
      </svg>
    </div>
    <div style={{position: 'absolute', left: 190, top: 1210, width: 700, height: 128,
      borderRadius: '50%', background: `radial-gradient(ellipse,${accent}25,transparent 67%)`}}/>
  </AbsoluteFill>;
};

// 功能：绘制奖级标题与金属装饰线；输入：场景属性；返回：居中的奖级主视觉。
const RarityHeading: React.FC<{scene: SceneProps}> = ({scene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const kind = scene.kind === 'magic' ? '魔力赏' : '一番赏';
  const fitted = fitLines(scene.tier, 850, 170, 140, 90);
  return <>
    <div style={{position: 'absolute', top: 66, width: '100%', textAlign: 'center', color: scene.accent,
      fontSize: 30, fontWeight: 700, letterSpacing: 10}}>{kind} <span style={{fontSize: 22, letterSpacing: 5, color: '#A49CB8'}}> / 赏品图鉴</span></div>
    <CenteredText text={scene.title} box={[96, 112, 888, 68]} size={36} min={26} color={scene.theme.muted}/>
    <Interactive.Div name="奖级主标题" premountFor={fps} style={{position: 'absolute', left: 100, top: 193, width: 880, height: 170,
      display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center',
      fontSize: fitted.fontSize, fontWeight: 900, lineHeight: 1.1, letterSpacing: 6,
      color: scene.accent, background: `linear-gradient(180deg,#FFFFFF 8%,${scene.accent} 60%,${scene.accent}88)`,
      backgroundClip: 'text', WebkitTextFillColor: 'transparent', filter: `drop-shadow(0 0 25px ${scene.accent}50)`,
      translate: `0px ${interpolate(frame,[0,16],[20,0],clamped)}px`,
      opacity: interpolate(frame,[0,12],[0.65,1],clamped)}}>{scene.tier}</Interactive.Div>
    <div style={{position: 'absolute', left: 112, top: 355, width: 856, height: 2,
      background: `linear-gradient(90deg,transparent,${scene.accent}66,${scene.accent},${scene.accent}66,transparent)`}}/>
    <div style={{position: 'absolute', left: 531, top: 348, width: 18, height: 18, rotate: '45deg',
      background: scene.accent, boxShadow: `0 0 22px ${scene.accent}`}}/>
  </>;
};

// 功能：显示完整商品、名称及可核实参考价；输入：奖品、主题和次序；返回：独立商品展示层。
const PrizeItem: React.FC<{item: Prize; accent: string; grid: boolean; index: number; motion: number}> = ({item, accent, grid, index, motion}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const [x, y, w, h] = item.imageBox;
  const left = x + (w - item.width) / 2;
  const top = y + (h - item.height) / 2;
  const start = Math.min(index * 3, 9);
  return <>
    {grid && <div style={{position: 'absolute', left: x - 10, top: y - 18, width: w + 20,
      height: item.priceBox[1] + item.priceBox[3] - y + 30, borderRadius: 24,
      background: 'linear-gradient(135deg,#FFFFFF08,#FFFFFF02)', border: `1px solid ${accent}38`,
      boxShadow: `inset 0 1px 0 ${accent}30`}}/>}
    {!item.transparent && <div style={{position: 'absolute', left: left - 10, top: top - 10,
      width: item.width + 20, height: item.height + 20, borderRadius: 8,
      background: `linear-gradient(135deg,${accent}B0,#FFFFFF50,${accent}40)`,
      boxShadow: `0 20px 70px #00000090,0 0 48px ${accent}25`}}/>}
    <Interactive.Div name={`奖品-${item.id}`} premountFor={fps} style={{position: 'absolute', left, top, width: item.width, height: item.height,
      scale: interpolate(frame,[start,start+18],[0.94,1],{...clamped, output:'perceptual-scale'}),
      translate: `0px ${Math.sin(frame / fps * 0.7 + index) * motion}px`,
      opacity: interpolate(frame,[start,start+12],[0.5,1],clamped)}}>
      <CanvasImage src={staticFile(item.src)} premountFor={fps} style={{width: item.width, height: item.height,
        objectFit: 'contain', filter: item.transparent ? `drop-shadow(0 24px 26px #000000A0) drop-shadow(0 0 30px ${accent}30)` : undefined}}/>
    </Interactive.Div>
    <CenteredText text={item.name} box={item.nameBox} size={grid ? 36 : 50} min={grid ? 28 : 34}/>
    {item.price && <div data-prize-text style={{position: 'absolute', left: item.priceBox[0], top: item.priceBox[1], width: item.priceBox[2], height: item.priceBox[3],
      display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center', gap: grid ? 10 : 16, color: accent,
      borderRadius: 16, background: grid ? 'transparent' : `linear-gradient(90deg,transparent,${accent}0E,transparent)`}}>
      <span style={{fontSize: grid ? 26 : 32, letterSpacing: 2, color: '#B9B2CB'}}>参考价</span>
      <span style={{fontSize: grid ? 34 : 56, fontWeight: 900, letterSpacing: 1, fontVariantNumeric: 'tabular-nums'}}>¥{item.price.amount.replace(/\.0+$/, '')}</span>
    </div>}
  </>;
};

// 功能：组合暗色赏品舞台；输入：已验证场景；返回：有字幕留白的 1080×1920 React 画面。
export const PrizeStage: React.FC<SceneProps> = (props) => {
  const scene = props;
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return <AbsoluteFill style={{fontFamily: FONT, color: scene.theme.ink}}>
    <Atmosphere accent={scene.accent} background={scene.theme.background}/>
    <div style={{position: 'absolute', left: 72, top: 380, width: 936, height: 1220,
      background: `linear-gradient(155deg,${scene.accent}60,#FFFFFF18 28%,${scene.accent}15 60%,${scene.accent}7A)`,
      clipPath: 'polygon(32px 0,calc(100% - 32px) 0,100% 32px,100% calc(100% - 32px),calc(100% - 32px) 100%,32px 100%,0 calc(100% - 32px),0 32px)'}}>
      <div style={{position: 'absolute', inset: 2, background: 'linear-gradient(140deg,#171127BB,#0A0818D8)',
        clipPath: 'polygon(31px 0,calc(100% - 31px) 0,100% 31px,100% calc(100% - 31px),calc(100% - 31px) 100%,31px 100%,0 calc(100% - 31px),0 31px)'}}/>
      <div style={{position: 'absolute', width: 460, height: 1600, top: -240,
        left: interpolate(frame,[0,5*fps],[-900,1500],{extrapolateRight:'extend'}), rotate: '-25deg',
        background: 'linear-gradient(90deg,transparent,#FFFFFF09,transparent)'}}/>
    </div>
    <RarityHeading scene={scene}/>
    {scene.items.map((item,index) => <PrizeItem key={item.id} item={item} index={index} accent={scene.accent} grid={scene.items.length > 1} motion={scene.motionPixels}/>)}
    <div style={{position: 'absolute', left: 110, right: 110, top: 1630, height: 1,
      background: `linear-gradient(90deg,transparent,${scene.accent}30,transparent)`}}/>
    <div style={{position: 'absolute', top: 1848, width: '100%', textAlign: 'center', color: '#756D87',
      fontSize: 18, letterSpacing: 7}}>PRIZE COLLECTION</div>
  </AbsoluteFill>;
};
