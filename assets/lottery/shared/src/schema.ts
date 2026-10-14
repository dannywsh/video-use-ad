export type Price = {amount: string; currency: string; source_field: string; source_endpoint: string};
export type Prize = {
  id: string; name: string; tier: string; src: string; width: number; height: number;
  nativeWidth: number; nativeHeight: number; transparent: boolean; price: Price | null;
  imageBox: number[]; nameBox: number[]; priceBox: number[];
};
export type SceneProps = {
  templateId: string; motionPixels: number;
  theme: {background: string; ink: string; muted: string};
  kind: string; title: string; tier: string; accent: string;
  durationInFrames: number; items: Prize[];
};

// 功能：校验前端输入并与 Python 规则保持一致；输入：场景 props；返回：有效场景，错误阻塞渲染。
export const validateScene = (props: SceneProps): SceneProps => {
  if (!/^[a-z][a-z0-9-]{0,63}$/.test(props.templateId) ||
      !Number.isFinite(props.motionPixels) || props.motionPixels < 0 || props.motionPixels > 12 ||
      !props.theme || ![props.theme.background, props.theme.ink, props.theme.muted].every((color) => /^#[0-9a-f]{6}$/i.test(color))) {
    throw new Error('模板身份、主题或运动余量无效');
  }
  if (!['magic', 'ichiban'].includes(props.kind) || !props.title || !props.tier ||
      !/^#[0-9a-f]{6}$/i.test(props.accent) || !Number.isInteger(props.durationInFrames) || props.durationInFrames < 1) {
    throw new Error('赏场景身份、颜色或时长无效');
  }
  if (!Array.isArray(props.items) || props.items.length < 1 || props.items.length > 4 ||
      new Set(props.items.map((item) => item.id)).size !== props.items.length) {
    throw new Error('每张卡必须为 1–4 个不同的同档位商品');
  }
  for (const item of props.items) {
    if (!item.id || !item.name || item.tier !== props.tier || !/^[a-zA-Z0-9/-]+\.png$/.test(item.src) ||
        ![item.width, item.height, item.nativeWidth, item.nativeHeight].every((n) => Number.isFinite(n) && n > 0) ||
        item.width > item.nativeWidth || item.height > item.nativeHeight ||
        (props.kind === 'ichiban' && item.width > 800)) {
      throw new Error('奖品图片身份或像素尺寸无效，禁止放大原图');
    }
    for (const box of [item.imageBox, item.nameBox, item.priceBox]) {
      if (!Array.isArray(box) || box.length !== 4 || !box.every(Number.isFinite) || box[0] < 72 || box[1] < 0 ||
          box[2] <= 0 || box[3] <= 0 || box[0] + box[2] > 1008 || box[1] + box[3] > 1620) {
        throw new Error('商品图或文字侵入画布边缘/字幕安全区');
      }
    }
    if (item.width > item.imageBox[2] || item.height + 2 * props.motionPixels > item.imageBox[3]) {
      throw new Error('商品完整主体或运动余量超出显示区域');
    }
    if (item.price && (item.price.currency !== 'CNY' || !item.price.source_field ||
        item.price.source_field === 'price' || !item.price.source_endpoint ||
        !/^\d+(\.\d+)?$/.test(item.price.amount) || !Number.isFinite(Number(item.price.amount)) || Number(item.price.amount) <= 0)) {
      throw new Error('奖品参考价无效或误用了单抽价');
    }
  }
  return props;
};
