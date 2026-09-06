# 皇帝人物卡批量生产模板 v0.1

Node.js、HTML/CSS、SVG 和 Playwright 截图驱动的固定双页人物卡模板。当前只包含朱元璋样例。

## 当前生产流程：AI 完整成图

1. **第一步 Codex：**根据 JSON 输出结构稿、雷达校验图与完整出图指令。
2. **第二步 GPT 网页版：**直接生成两张包含人物、背景、书法、雷达、八卡片及全部文字的完整成图。
3. **第三步 Codex：**校验 JSON、八轴顺序和雷达点位依据；人工逐项核对 AI 成图的文字、档位与卡片内容。发现错误则重出对应页面。

这是当前唯一的生产路径。透明 `text` / `radar` / `stroke` 覆层与 `compose-final.js` 保留为实验代码，不得用于正式成图：它不能无损替换 AI 已绘制的文字、雷达或卡片内容。

制作人物卡时按需查阅 [production-sop-v3.md](docs/production-sop-v3.md) 中的版式、提示词及验收章节；普通文案维护无需执行整套制作流程。人物 JSON 是展示制作输入，档位与轴义须追溯正式画像结算。

```text
assets/portraits/        本地肖像
data/emperors/           每位人物一份 JSON
templates/               page1、page2 固定版式
scripts/radar.js         八轴 18 级 SVG 雷达图
scripts/render-base.js   结构稿与雷达调试图导出
output/<id>/base|ai|debug/  结构参考、AI 成图与调试产物
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

批量生产按 SOP 对各人物执行上述结构稿与出图指令命令，再生成、校对对应 AI 页面。`render-all.js --stage pipeline`、`render-overlay.js` 和 `compose-final.js` 属于实验路径，不用于正式交付。

映射或结构逻辑变化时执行 `npm run verify`，检查 18 级映射（`E- = 0`、`S = 16`、`S+ = 17`）与八轴顺序；内容修订核对受影响数据与页面。模板不计算画像总分或轴内排名。
