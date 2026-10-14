import React from 'react';
import {measureText} from '@remotion/layout-utils';

export const FONT = 'PrizeSans';
// 功能：以真实浏览器字体宽度完整分行；输入：文字、区域、字号；返回：居中排版参数，不截断名称。
export const fitLines = (text: string, width: number, height: number, maximum: number, minimum: number) => {
  // 优先保留空格分隔的品牌、作品和完整角色名，只有单个词块超宽才按字退让。
  const tokens = text.match(/\S+|\s+/gu) || [];
  for (let size = maximum; size >= minimum; size--) {
    const lines: string[] = [];
    let line = '';
    const length = (value: string) => measureText({text: value, fontFamily: FONT, fontSize: size, fontWeight: '700'}).width;
    for (const token of tokens) {
      if (line && length(line + token) > width) {
        lines.push(line.trim());
        line = '';
      }
      if (length(token) > width) {
        for (const char of token) {
          if (line && length(line + char) > width) {lines.push(line.trim()); line = '';}
          line += char;
        }
      } else {line += token;}
    }
    if (line.trim()) lines.push(line.trim());
    if (lines.length * size * 1.28 <= height) return {lines, fontSize: size, lineHeight: 1.28};
  }
  throw new Error(`商品名无法完整展示，需拆卡：${text}`);
};

// 功能：绘制居中文字；输入：文字区域和视觉属性；返回：有固定中心轴的 DOM 文本块。
export const CenteredText: React.FC<{text: string; box: number[]; size: number; min: number; color?: string}> = ({text, box, size, min, color = '#F6F2FF'}) => {
  const fitted = fitLines(text, box[2], box[3], size, min);
  return <div data-prize-text style={{position: 'absolute', left: box[0], top: box[1], width: box[2], height: box[3],
    display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center', fontWeight: 700,
    whiteSpace: 'pre', fontSize: fitted.fontSize, lineHeight: fitted.lineHeight, color}}>{fitted.lines.join('\n')}</div>;
};
