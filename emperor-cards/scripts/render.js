import { renderBase } from "./render-base.js";
const argument = process.argv[2];
if (!argument || argument === "--all") throw new Error("请改用 node scripts/render-all.js --stage base；单人物用 node scripts/render-base.js <json>");
await renderBase(argument);
