# 皇帝人物卡批量生产规范 v3：AI 完整成图

## 决策

正式路线采用“AI 完整成图 + 本地结构参考与人工校验”。不采用“AI 成片局部去字/净化 + 本地透明覆字”的路线：局部编辑耗时不稳定，且透明层不能无损替换 AI 已绘制的文字、雷达或卡片内容。

```text
人物 JSON
  → Codex 结构稿、雷达校验图、完整出图指令
  → GPT 网页版生成 page1 / page2 完整成图
  → 本地/人工校验
  → 通过，或仅重出错误页面
```

## 分工

### Codex

- 读取唯一人物 JSON，输出 `page1_base.png`、`page2_base.png` 和 `radar_debug.png`；
- 生成含人物、八轴、档位、卡片正文的完整 AI 出图指令；
- 校验 JSON、八轴顺序和 18 级雷达映射；
- 提供人工核对清单。

### GPT 网页版

一次生成完整页面：肖像、背景、金箔、墨迹、宫阙、边饰、漂亮字体、装饰线、雷达、八轴卡片、图标和全部正文。它是正式视觉输出，不再由本地脚本替换其中任何视觉层。

## 版式族与主题包

每个人选择 `layout` 与 `theme`。主题改变美术语言；布局改变构图；二者都不得改变八轴语义与 JSON 数据。

| layout | 构图 |
| --- | --- |
| `left_portrait_radar_right` | 左肖像、右雷达、第二页双栏八卡片 |
| `center_portrait_side_panels` | 中央肖像、两侧信息、底部卡片 |
| `full_scene_side_rail` | 全幅场景、侧栏雷达、独立卡片区 |

| theme | 视觉关键词 |
| --- | --- |
| `black_gold_epic` | 黑金、朱砂、金箔、宫阙、墨迹 |
| `azure_restoration` | 青金、晨光、云台、典籍、清朗 |
| `vermilion_prosperity` | 朱砂、鎏金、宫城、旌旗、暖色辉光 |
| `ochre_turbulence` | 苍黄、尘土、残卷、军旗、粗粝笔触 |
| `indigo_civil_rule` | 深青、纸本、舆图、印章、冷金细线 |

同一主题内的八轴图标保持固定语义和风格；不同主题可换整套风格，但不能临时混用。

## JSON 合同

```json
{
  "id": "zhuyuanzhang",
  "theme": "black_gold_epic",
  "layout": "left_portrait_radar_right",
  "productionMode": "ai_full_card"
}
```

人物姓名、标题、时间、标签、八轴、卡片正文和档位都以同一 JSON 为唯一事实来源。任何更新先改 JSON，再重建结构稿和 AI 出图指令。

## 单人物 SOP

1. 更新 JSON 的人物信息、八轴、卡片、`theme`、`layout`。
2. 执行：

   ```bash
   node scripts/render-base.js data/emperors/<id>.json
   node scripts/build-ai-brief.js data/emperors/<id>.json
   ```

3. 将两张结构稿、`radar_debug.png` 与 `ai-production-brief.md` 上传给 GPT 网页版。
4. 要求 GPT 输出两张 1920×1080 完整成图；同一人物的两页须保持肖像、主题、边饰和字体风格一致。
5. 将结果保存为 `output/<id>/ai/page1_ai.png`、`page2_ai.png`。
6. 对照 AI 出图指令人工逐项核对：

   - 姓名、副标题、年份、大标题、标签；
   - 八轴名称、八个档位和雷达点位；
   - 八张卡片的轴名、正文、档位；
   - 图标语义、卡片数量、页面尺寸和无乱码。

7. 任一信息错误时，仅重出对应页面；不做局部去字、局部净化或本地覆字。

## 批量前门槛

用朱元璋、刘秀、李世民完成三组双页成图。其中至少使用两种主题和两种布局。三组均通过人工校对后，再按同一 SOP 批量生产。

## 已停用的实验路径

`render-overlay.js`、`compose-final.js` 与相关 overlay 验收脚本可保留作技术实验，但不得作为正式生成命令或交付依据。
