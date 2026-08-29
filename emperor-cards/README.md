# 皇帝人物卡批量生产模板 v0.1

Node.js、HTML/CSS、SVG 和 Playwright 截图驱动的固定双页人物卡模板。当前只包含朱元璋样例。

## 当前生产流程：AI 完整成图

1. **第一步 Codex：**根据 JSON 输出结构稿、雷达校验图与完整出图指令。
2. **第二步 GPT 网页版：**直接生成两张包含人物、背景、书法、雷达、八卡片及全部文字的完整成图。
3. **第三步 Codex：**校验 JSON、八轴顺序和雷达点位依据；人工逐项核对 AI 成图的文字、档位与卡片内容。发现错误则重出对应页面。

这是当前唯一的生产路径。透明 `text` / `radar` / `stroke` 覆层与 `compose-final.js` 保留为实验代码，不得用于正式成图：它不能无损替换 AI 已绘制的文字、雷达或卡片内容。

版式族、主题包、完整出图提示词、人工校验表及批量 SOP 见 [production-sop-v3.md](docs/production-sop-v3.md)。

```text
assets/portraits/        本地肖像
data/emperors/           每位人物一份 JSON
templates/               page1、page2 固定版式
scripts/radar.js         八轴 18 级 SVG 雷达图
scripts/render-base.js   结构稿与雷达调试图导出
scripts/render-overlay.js 透明精确覆盖层导出
scripts/compose-final.js AI 成片缩放裁切与精确层合成
output/<id>/base|overlay|ai|final|debug/  批量流水线产物
```

首次在独立环境使用：

```bash
npm install
npx playwright install chromium
```

渲染朱元璋：

```bash
node scripts/render-base.js data/emperors/zhuyuanzhang.json
node scripts/build-ai-brief.js data/emperors/zhuyuanzhang.json
```

批量渲染 `data/emperors/`：

```bash
node scripts/render-all.js --stage pipeline

`pipeline` 会生成 base 与 overlay；存在 `output/<id>/ai/page1_ai.png`、`page2_ai.png` 时，再输出 final，否则给出缺失清单。可单独执行 `--stage base`、`overlay` 或 `final`。
```

执行 `npm run verify` 可断言 18 级映射（`E- = 0`、`S = 16`、`S+ = 17`）与样例固定八轴顺序。模板不计算画像总分或轴内排名。
