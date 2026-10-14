import React from 'react';
import {Composition} from 'remotion';
import {SceneRenderer} from './SceneRenderer';
import {validateScene} from './schema';
import scene from './scene.json';

// 功能：注册可在 Studio 编辑/渲染的赏品舞台；输入：本次 scene.json 默认数据；返回：竖屏 Composition。
export const RemotionRoot: React.FC = () => <Composition
  id="PrizeCard" component={SceneRenderer} fps={30} width={1080} height={1920}
  durationInFrames={120}
  defaultProps={{templateId: scene.templateId, motionPixels: scene.motionPixels, theme: scene.theme,
    kind: scene.kind, title: scene.title, tier: scene.tier, accent: scene.accent,
    durationInFrames: scene.durationInFrames, items: scene.items}}
  calculateMetadata={({props}) => ({durationInFrames: validateScene(props).durationInFrames})}
/>;
