import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { AXES } from "./radar.js";
import { loadData, root } from "./render-common.js";

export async function buildAiBrief(input) {
  const data = await loadData(input); const output = path.join(root, "output", data.id, "brief"); await fs.mkdir(output, { recursive: true });
  const axes = AXES.map(axis => `| ${axis} | ${data.axes[axis]} |`).join("\n");
  const cards = data.cards.map((card, index) => `${index + 1}. **${card.axis}｜${card.grade}**：${card.text}`).join("\n");
  const brief = `# ${data.name}｜AI 完整成图指令\n\n## 固定条件\n\n- 输出：两张 1920×1080 PNG。\n- 主题：${data.theme.id}；版式：${data.layout}。\n- 人物：${data.name}；副标题：${data.subtitle}；实际掌权：${data.years}。\n- 大标题：${data.tagline}；身份签：${data.sideLabel}。\n- 标签：${data.labels.join("、")}。\n\n## 必须精确写入的雷达数据\n\n| 八轴 | 档位 |\n| --- | --- |\n${axes}\n\n雷达必须是八轴十八级：E- = 0，S+ = 17；轴顺序严格按上表。\n\n## Page 2 八张卡片（逐字使用）\n\n${cards}\n\n## 美术要求\n\n生成完整可交付的人物卡，而不是留白模板。人物、背景、金箔、墨迹、宫阙、边饰、书法标题、卡片图标与整体光影由 AI 完成。卡片图标在同一主题内保持固定语义和统一风格。禁止乱码、占位文字、错误档位、错误雷达、缺卡或重复卡。\n\n## 出图后人工校对\n\n逐项核对姓名、副标题、年份、标签、八轴名、八个档位、雷达点位、八张卡片标题/正文/档位；任一项错误则直接以本指令重出该页，不进行局部去字或程序覆字。\n`;
  const destination = path.join(output, "ai-production-brief.md"); await fs.writeFile(destination, brief, "utf8"); console.log(destination); return destination;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) { if (!process.argv[2]) throw new Error("用法：node scripts/build-ai-brief.js data/emperors/<id>.json"); await buildAiBrief(process.argv[2]); }
