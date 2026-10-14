import React, {useEffect, useState} from 'react';
import {loadFont} from '@remotion/fonts';
import {AbsoluteFill, cancelRender, continueRender, delayRender, staticFile} from 'remotion';
import {TemplateStage, TEMPLATE_ID} from './SelectedTemplate';
import {SceneProps, validateScene} from './schema';
import {FONT} from './text';

// 功能：等待字体并验证统一场景，再调用所选模板；输入：场景 props；返回：模板画面或加载占位。
export const SceneRenderer: React.FC<SceneProps> = (props) => {
  const scene = validateScene(props);
  if (scene.templateId !== TEMPLATE_ID) throw new Error('场景模板与当前工程不匹配，禁止串用模板');
  const [handle] = useState(() => delayRender('加载赏品中文粗体字体'));
  const [ready, setReady] = useState(false);
  useEffect(() => {
    loadFont({family: FONT, url: staticFile('fonts/prize.ttf'), weight: '700', format: 'truetype'})
      .then(() => {
        // 中文后备字体可能具有相同字宽，直接检查 FontFace 的加载状态。
        let loaded = false;
        document.fonts.forEach((face) => {if (face.family === FONT && face.status === 'loaded') loaded = true;});
        if (!loaded) throw new Error('本地中文字体尚未加载，禁止使用后备字体截图');
        setReady(true);
      }).catch(cancelRender);
  }, []);
  useEffect(() => {if (ready) continueRender(handle);}, [ready, handle]);
  return ready ? <AbsoluteFill style={{fontFamily: FONT, color: scene.theme.ink}}><TemplateStage {...scene}/></AbsoluteFill> : null;
};
