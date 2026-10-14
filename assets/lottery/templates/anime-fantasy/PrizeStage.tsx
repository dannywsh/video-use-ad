import React from 'react';
import {AbsoluteFill, CanvasImage, Easing, Interactive, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Prize, SceneProps} from '../../schema';
import {CenteredText, fitLines} from '../../text';

const ease = Easing.bezier(0.16, 1, 0.3, 1);
const clamp = {extrapolateLeft: 'clamp' as const, extrapolateRight: 'clamp' as const, easing: ease};

// 功能：铺设中央留白、边角樱花与猫猫头的静态位图；输入：无；返回：不干扰商品和字幕的背景层。
const FantasyBackground: React.FC = () => <AbsoluteFill style={{overflow: 'hidden', background: '#FFFCF8'}}>
  <CanvasImage src={staticFile('templates/anime-fantasy/background.png')} style={{position: 'absolute',
    width: '100%', height: '100%', objectFit: 'cover'}}/>
</AbsoluteFill>;

// 功能：绘制日系收藏标题和奖级主视觉；输入：场景；返回：居中且可换色的标题层。
const FantasyHeading: React.FC<{scene: SceneProps}> = ({scene}) => {
  const frame = useCurrentFrame();
  const tier = fitLines(scene.tier, 820, 164, 140, 72);
  return <>
    <div style={{position: 'absolute', left: 354, top: 66, width: 372, height: 64, borderRadius: 32,
      display: 'flex', justifyContent: 'center', alignItems: 'center', background: '#FFFFFFDE',
      border: `1px solid ${scene.accent}30`, color: scene.accent,
      fontSize: 34, fontWeight: 700, letterSpacing: 6}}>
      {scene.kind === 'magic' ? '魔力赏' : '一番赏'}
    </div>
    <CenteredText text={scene.title} box={[130, 149, 820, 76]} size={40} min={28} color={scene.theme.muted}/>
    <Interactive.Div name="幻想奖级" style={{position: 'absolute', left: 130, top: 241, width: 820, height: 164,
      display: 'flex', justifyContent: 'center', alignItems: 'center', whiteSpace: 'pre', textAlign: 'center',
      fontSize: tier.fontSize, lineHeight: tier.lineHeight, fontWeight: 900, letterSpacing: 5,
      color: scene.accent,
      translate: `0px ${interpolate(frame, [0,18], [16,0], clamp)}px`, opacity: interpolate(frame,[0,14],[0.72,1],clamp)}}>{tier.lines.join('\n')}</Interactive.Div>
    <div style={{position: 'absolute', left: 305, top: 410, width: 470, height: 2,
      background: `linear-gradient(90deg,transparent,${scene.accent}45,transparent)`}}/>
  </>;
};

// 功能：绘制单卡名称纸片或合并卡承载层；输入：商品区域、主题、合并状态；返回：不遮挡商品的文字底板。
const CollectionPlate: React.FC<{item: Prize; accent: string; grid: boolean}> = ({item, accent, grid}) => {
  const [x, y, width] = grid ? item.imageBox : item.nameBox;
  const top = y - 14;
  const bottom = item.price ? item.priceBox[1] + item.priceBox[3] + 14 : item.nameBox[1] + item.nameBox[3] + 14;
  return <div style={{position: 'absolute', left: x - 18, top, width: width + 36, height: bottom - top,
    borderRadius: 28, background: '#FFFFFFC9',
    border: `1px solid ${accent}20`, boxShadow: '0 8px 28px #9775A510'}}/>;
};

// 功能：显示原图完整主体、名称与对应参考价；输入：奖品、场景、次序；返回：商品收藏卡。
const FantasyPrize: React.FC<{item: Prize; scene: SceneProps; index: number}> = ({item, scene, index}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const grid = scene.items.length > 1;
  const [x,y,w,h] = item.imageBox;
  const left = x + (w - item.width) / 2;
  const top = y + (h - item.height) / 2;
  const start = index * 3;
  const price = item.price ? fitLines(`¥${item.price.amount.replace(/\.0+$/, '')}`, item.priceBox[2] - 128, item.priceBox[3], grid ? 38 : 54, 24) : null;
  return <>
    <CollectionPlate item={item} accent={scene.accent} grid={grid}/>
    {!grid && item.transparent && <div style={{position: 'absolute', left: 190, top: 1150, width: 700, height: 170,
      borderRadius: '50%', background: 'radial-gradient(ellipse,#69527612,transparent 65%)'}}/>}
    <Interactive.Div name={`幻想商品-${item.id}`} style={{position: 'absolute', left, top, width: item.width, height: item.height,
      scale: interpolate(frame,[start,start+22],[0.94,1],clamp),
      translate: `0px ${Math.sin(frame / fps * 0.75 + index) * scene.motionPixels}px`,
      opacity: interpolate(frame,[start,start+14],[0.65,1],clamp)}}>
      {!item.transparent && <div style={{position: 'absolute', inset: -8, borderRadius: 10,
        background: '#FFFFFF', border: `1px solid ${scene.accent}30`,
        boxShadow: '0 10px 28px #614E6F18'}}/>}
      <CanvasImage src={staticFile(item.src)} style={{position: 'absolute', width: item.width, height: item.height,
        objectFit: 'contain', filter: item.transparent ? 'drop-shadow(0 16px 14px #49345528)' : undefined}}/>
    </Interactive.Div>
    <CenteredText text={item.name} box={item.nameBox} size={grid ? 40 : 52} min={grid ? 30 : 36} color={scene.theme.ink}/>
    {item.price && price && <div data-prize-text style={{position: 'absolute', left: item.priceBox[0], top: item.priceBox[1],
      width: item.priceBox[2], height: item.priceBox[3], display: 'flex', alignItems: 'center', justifyContent: 'center',
      textAlign: 'center', gap: 12, borderRadius: 24,
      background: 'transparent'}}>
      <span style={{fontSize: grid ? 26 : 30, color: scene.theme.muted}}>参考价</span>
      <span style={{fontSize: price.fontSize, color: scene.accent, fontWeight: 900, fontVariantNumeric: 'tabular-nums',
        whiteSpace: 'pre', lineHeight: price.lineHeight}}>{price.lines.join('\n')}</span>
    </div>}
  </>;
};

// 功能：组合位图场景与可编辑前景；输入：统一场景 props；返回：1080×1920 的二次元展示画面。
export const PrizeStage: React.FC<SceneProps> = (scene) => <AbsoluteFill style={{color: scene.theme.ink}}>
  <FantasyBackground/>
  <FantasyHeading scene={scene}/>
  {scene.items.map((item,index) => <FantasyPrize key={item.id} item={item} scene={scene} index={index}/>)}
</AbsoluteFill>;
