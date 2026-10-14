// 功能：验证真实场景与非法输入的前端契约；输入：运行工程路径、props JSON 路径；返回：非零退出码表示失败。
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const Module = require('node:module');
const {createRequire} = Module;

const [project, ...propsPaths] = process.argv.slice(2);
assert(project && propsPaths.length, '用法：node tests/check_lottery_frontend.cjs <工程> <props.json> ...');
const requireProject = createRequire(path.join(path.resolve(project), 'package.json'));
const ts = requireProject('typescript');
const source = fs.readFileSync(path.join(project, 'src/schema.ts'), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS}}).outputText;
const schema = new Module('lottery-schema');
schema._compile(compiled, 'lottery-schema.cjs');
const {validateScene} = schema.exports;

for (const filename of propsPaths) validateScene(JSON.parse(fs.readFileSync(filename, 'utf8')));
const valid = JSON.parse(fs.readFileSync(propsPaths[0], 'utf8'));
const invalid = [
  (props) => {props.templateId = '../default';},
  (props) => {props.motionPixels = 13;},
  (props) => {props.theme.background = 'red';},
  (props) => {props.durationInFrames = 0;},
  (props) => {props.items[0].tier = '另一个档位';},
  (props) => {props.items[0].width = props.items[0].nativeWidth + 1;},
  (props) => {props.items[0].imageBox[1] = 1700;},
  (props) => {props.items[0].height = props.items[0].imageBox[3]; props.motionPixels = 6;},
  (props) => {props.items.push(props.items[0]);},
  (props) => {props.items[0].price = {amount: '78', currency: 'CNY', source_field: 'price', source_endpoint: '/items/info'};},
];
for (const mutate of invalid) {
  const props = JSON.parse(JSON.stringify(valid));
  mutate(props);
  assert.throws(() => validateScene(props), '非法场景应被前端拒绝');
}
console.log(`前端契约检查通过：${propsPaths.length} 个真实场景、${invalid.length} 类非法输入`);
