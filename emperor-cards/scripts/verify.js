import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { AXES, GRADES, gradeIndex } from "./radar.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const data = JSON.parse(await fs.readFile(path.join(root, "data", "emperors", "zhuyuanzhang.json"), "utf8"));

assert.equal(GRADES.length, 18);
assert.equal(gradeIndex("E-"), 0);
assert.equal(gradeIndex("S-"), 15);
assert.equal(gradeIndex("S"), 16);
assert.equal(gradeIndex("S+"), 17);
assert.deepEqual(data.cards.map(card => card.axis), AXES);
assert.deepEqual(AXES.map(axis => data.axes[axis]), ["A+", "B+", "B", "B+", "S", "C", "C+", "E-"]);
console.log("雷达映射与朱元璋固定八轴顺序：PASS");
