export function esc(value) {
  return String(value).replace(/[&<>'"]/g, character => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", "'":"&#39;", '"':"&quot;" })[character]);
}

export function assertEmperor(data) {
  for (const key of ["id", "name", "subtitle", "years", "portrait", "axes", "cards"]) {
    if (!data[key]) throw new Error(`缺少人物字段：${key}`);
  }
  if (data.cards.length !== 8) throw new Error("评分依据页必须有八张轴卡片");
  if (typeof data.portrait !== "string" && !data.portrait.src) throw new Error("portrait 必须是路径或包含 src 的对象");
}
