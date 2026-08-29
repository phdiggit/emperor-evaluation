export const AXES = ["军事统帅", "外交博弈", "民生财政", "联盟整合", "战略风控", "学习纠错", "识才授权", "权力克制"];
export const GRADES = ["E-", "E", "E+", "D-", "D", "D+", "C-", "C", "C+", "B-", "B", "B+", "A-", "A", "A+", "S-", "S", "S+"];

const point = (cx, cy, radius, index) => {
  const angle = -Math.PI / 2 + index * Math.PI / 4;
  return [cx + radius * Math.cos(angle), cy + radius * Math.sin(angle)];
};
const ringPoints = (cx, cy, radius) => AXES.map((_, index) => point(cx, cy, radius, index).map(value => value.toFixed(2)).join(",")).join(" ");

export function gradeIndex(grade) {
  const index = GRADES.indexOf(grade);
  if (index < 0) throw new Error(`未知雷达档位：${grade}`);
  return index;
}

export function radarLayers(axes, options = {}) {
  const width = options.width ?? options.size ?? 600;
  const height = options.height ?? options.size ?? width;
  const cx = options.cx ?? width / 2;
  const cy = options.cy ?? height / 2;
  const radius = options.radius ?? Math.min(width, height) * 0.34;
  const labelRadius = options.labelRadius ?? radius + 62;
  const axisFont = options.axisFont ?? 22;
  const gradeFont = options.gradeFont ?? 28;
  const showLevelMarks = options.showLevelMarks ?? false;
  const rings = Array.from({ length: 17 }, (_, offset) => {
    const level = offset + 1;
    return `<polygon points="${ringPoints(cx, cy, radius * level / 17)}" class="${[2, 5, 8, 11, 14, 17].includes(level) ? "major" : "minor"}"/>`;
  }).join("");
  const spokes = AXES.map((_, index) => {
    const [x, y] = point(cx, cy, radius, index);
    return `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" class="spoke"/>`;
  }).join("");
  const labels = AXES.map((axis, index) => {
    const [x, y] = point(cx, cy, labelRadius, index);
    const anchor = Math.abs(x - cx) < 1 ? "middle" : x > cx ? "start" : "end";
    return `<text x="${x}" y="${y}" text-anchor="${anchor}" class="axis"><tspan x="${x}" dy="0">${axis}</tspan><tspan x="${x}" dy="${axisFont + 8}" class="grade">${axes[axis]}</tspan></text>`;
  }).join("");
  const dataPoints = AXES.map((axis, index) => point(cx, cy, radius * gradeIndex(axes[axis]) / 17, index).map(value => value.toFixed(2)).join(",")).join(" ");
  const dots = AXES.map((axis, index) => {
    const [x, y] = point(cx, cy, radius * gradeIndex(axes[axis]) / 17, index);
    return `<circle cx="${x}" cy="${y}" r="4.5" class="dot"/>`;
  }).join("");
  const levels = showLevelMarks ? GRADES.map((grade, index) => `<text x="${cx + 9}" y="${cy - radius * index / 17 + 5}" class="level">${grade}</text>`).join("") : "";
  const style = `<style>.radar-svg{overflow:visible}.minor,.major{fill:none;stroke:#d6a448}.minor{stroke-width:.7;stroke-opacity:.22}.major{stroke-width:1.2;stroke-opacity:.48}.spoke{stroke:#d6a448;stroke-width:1;stroke-opacity:.35}.shape{fill:#d6a448;fill-opacity:.21;stroke:#f1d488;stroke-width:3}.dot{fill:#f1d488;stroke:#5b3f16;stroke-width:1.3}.axis{font-family:'Source Han Serif SC','Noto Serif SC','Microsoft YaHei',serif;font-size:${axisFont}px;font-weight:700;fill:#dfc27b}.grade{font-size:${gradeFont}px;font-weight:800;fill:#f1d488}.level{font-family:'Microsoft YaHei',sans-serif;font-size:14px;fill:#dfc27b}</style>`;
  const svg = content => `<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" class="radar-svg" role="img" aria-label="八轴十八级雷达图">${style}${content}</svg>`;
  return { precise: svg(`${rings}${spokes}<polygon points="${dataPoints}" class="shape"/>${dots}${labels}${levels}`), radar: svg(`${rings}${spokes}<polygon points="${dataPoints}" class="shape"/>${dots}`), text: svg(`${labels}${levels}`) };
}

export function radarSvg(axes, options = {}) { return radarLayers(axes, options).precise; }

export function radarDebugHtml(data) {
  const rows = AXES.map(axis => `<div>${axis}<b>${data.axes[axis]}</b></div>`).join("");
  return `<!doctype html><meta charset="utf-8"><style>body{margin:0;width:1920px;height:1080px;background:#0f0905;color:#dfc27b;font-family:'Noto Serif SC','Microsoft YaHei',serif}.title{position:absolute;left:90px;top:72px;font-size:52px;font-weight:800;color:#f1d488}.note{position:absolute;left:94px;top:154px;font-size:24px}.legend{position:absolute;left:106px;top:270px;font-size:25px;line-height:1.85}.legend b{display:inline-block;margin-left:22px;color:#f1d488}.radar{position:absolute;left:610px;top:145px}.scale{position:absolute;left:96px;bottom:66px;display:flex;gap:10px}.scale span{width:82px;text-align:center;border-bottom:4px solid #d6a448;padding:12px 0;color:#dfc27b}</style><div class="title">${data.name}｜八轴十八级雷达校验图</div><div class="note">半径 = levelIndex / 17 × R；E- 为 0，S+ 为 17。</div><div class="legend">${rows}</div><div class="radar">${radarSvg(data.axes,{width:800,height:800,cx:400,cy:400,radius:255,labelRadius:320,axisFont:26,gradeFont:28,showLevelMarks:true})}</div><div class="scale">${GRADES.map((grade,index)=>`<span>${index}<br>${grade}</span>`).join("")}</div>`;
}
