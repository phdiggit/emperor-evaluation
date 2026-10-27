"use strict";

// Display vocabulary only. Scores and judgments come from the formal records.
globalThis.SecondItemDisplay = Object.freeze({
  grades: Object.freeze({G0:"E", G1:"D", G2:"C", G3:"B", G4:"A", G5:"S"}),
  stateGrades: Object.freeze({1:"E", 2:"D", 3:"C", 4:"B", 5:"A", 6:"S"}),
  handoffGrades: Object.freeze({0:"E", 1:"D", 2:"C", 3:"B", 4:"A", 5:"S"}),
  lossText: Object.freeze({
    0:"现有证据尚不足以确认应单独计入的较差状态", 1:"已证独立损害，按证据范围作有限修正",
    2:"出现明显低谷", 3:"出现严重低谷",
  }),
  methodMax: Object.freeze({"A制度建设":100, "B1官僚治理":100, "B2反馈与约束":80}),
  financeMax: Object.freeze({"C1民生":80, "C2经济财政":35, "C3社会安全":60}),
  labels: Object.freeze({
    "A制度建设":"制度建设", "B1官僚治理":"官僚治理", "B2反馈与约束":"反馈与约束",
    "C1民生":"民生", "C2经济财政":"经济财政", "C3社会安全":"社会安全",
    "C4恢复与成本":"恢复与额外代价",
    "D1继任行政连续性":"行政连续性", "D3政权交接稳定":"交接稳定",
  }),
});
