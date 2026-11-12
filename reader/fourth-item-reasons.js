"use strict";
(() => {
  function paragraphs(text, prose) {
    return text.split(/\n\n+/).map(block => {
      if (block.length < 180) return prose(block);
      const sentences = block.match(/[^。！？]*[。！？]+|[^。！？]+$/gu) || [];
      const groups = [];
      let paragraph = "";
      for (const sentence of sentences) {
        if (paragraph && paragraph.length + sentence.length > 140) {
          groups.push(paragraph);
          paragraph = "";
        }
        paragraph += sentence;
      }
      if (paragraph) groups.push(paragraph);
      return groups.map(prose).join("");
    }).join("");
  }

  // Match the current formal prose before adding headings. If it changes, retain the full text.
  const topics = [
    [["玉海明确论孟已刊石立太学", "太学刻石与经籍传播"], ["本纪初禁野史与后续李光案处分", "国史资料与私史写作受损"]],
    [["帝敕徐勉选学士", "百科类书的编成与传抄"], ["本纪有武帝造通史", "武帝《通史》的编成与保存"], ["本人制涅盘", "佛经义记与讲说"], ["吴均已成书被帝命焚", "吴均史稿遭焚"]],
    [["字典、诗集、律历和测绘", "各项知识工程的计入范围"], ["南山集只计", "《南山集》禁毁"], ["已有《字汇》", "字书编订与刊行"], ["继承胡震亨", "唐诗校订与补辑"], ["1708—1718年实测", "实测舆图"], ["故宫藏康熙内府本", "数学知识汇编"]],
    [["牛弘搜书方案", "四部典籍的搜集、校补与保存"], ["开皇本人组织译场", "佛典翻译、审核与复制"], ["开皇十三年直接禁", "纬候图谶与私史受限"]],
    [["杜尔伯特牧地协商", "杜尔伯特、土尔扈特的参与"], ["部分汉军获自选出旗", "部分汉军出旗入民籍"], ["分奴造成的损害另计", "准噶尔部众遭搜剿与分奴"], ["除特定例外扩大佥妻", "佥妻与家属去留"], ["1742年白契身份追认", "白契身份追认与良籍追降"]],
    [["复为民的直接资格转换", "复民籍及居处限制"], ["明确宫禁退出", "宫禁人员退出"], ["任用资格有实际蒙古文官履历", "蒙古文官任用"], ["原强迁3级中位撤回", "强迁与流民著籍"], ["本人颁定律本文", "婚配资格限制"]],
    [["奉敕编纂、本人窗口书成及御览使用", "《太平御览》编纂与使用"], ["本人窗口表进及雕板", "《太平广记》刊刻与收板"], ["奉敕于雍熙四年完成", "《文苑英华》编成与传播"], ["本人出内府法书", "内府法书摹刻拓赐"]],
    [["前代已有公共图像", "佛教设施及公开传授受损"], ["继承邓渊体例未成", "国书编成、刻石与编修受阻"]],
    [["流寓与本地群体在中枢", "流寓与本地群体共同任事"], ["陆逊讨费栈时", "东三郡与丹阳山民重编"], ["夷洲数千居民", "夷洲居民被带离"], ["交州招抚带来", "交州招抚的采用范围"]],
  ];

  function decision(text, prose) {
    const sections = topics.find(([[first]]) => text.startsWith(first));
    if (!sections) return paragraphs(text, prose);
    const offsets = sections.map(([start]) => text.indexOf(start));
    if (offsets.some((offset, index) => index && offset <= offsets[index - 1])) return paragraphs(text, prose);
    return sections.map(([, title], index) =>
      `<section class="fourth-reason-topic"><h4>${title}</h4>${paragraphs(text.slice(offsets[index], offsets[index + 1]), prose)}</section>`
    ).join("");
  }
  globalThis.FourthItemReasons = Object.freeze({decision});
})();
