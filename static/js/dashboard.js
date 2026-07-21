/* ===== 客户流失与营销分析仪表盘 · ECharts 交互层 ===== */

const PALETTE = ["#58a6ff", "#3fb950", "#d29922", "#f85149", "#bc8cff", "#39d0d8", "#ff7b72", "#7ee787"];
const AXIS = { color: "#8b949e", fontSize: 11 };
const SPLIT = { lineStyle: { color: "#21262d" } };
const TOOLTIP = {
  backgroundColor: "rgba(22,27,34,.95)", borderColor: "#2a3441",
  textStyle: { color: "#e6edf3", fontSize: 12 },
};

// 全局缓存数据
let DATA = {};
const charts = {};

function init(id) {
  const c = echarts.init(document.getElementById(id), null, { renderer: "canvas" });
  charts[id] = c;
  return c;
}
window.addEventListener("resize", () => Object.values(charts).forEach(c => c.resize()));

const fmt = {
  money: v => "¥" + Math.round(v).toLocaleString(),
  pct: v => v.toFixed(1) + "%",
  num: v => v.toLocaleString(),
};

/* ===== 数据加载 ===== */
async function loadAll() {
  const urls = {
    overview: "/api/overview", model: "/api/model", dimensions: "/api/dimensions",
    survival: "/api/survival", segments: "/api/segments", ltv: "/api/ltv",
    campaigns: "/api/campaigns", channels: "/api/channels", highRisk: "/api/high-risk?limit=30",
    retention: "/api/retention?budget=50",
  };
  const entries = await Promise.all(
    Object.entries(urls).map(async ([k, u]) => {
      const res = await fetch(u);
      return [k, await res.json()];
    })
  );
  DATA = Object.fromEntries(entries);
  renderAll();
}

/* ===== KPI ===== */
function renderKPI() {
  const o = DATA.overview;
  document.getElementById("kpi-total").textContent = fmt.num(o.totalCustomers);
  document.getElementById("kpi-total-d").textContent = `平均 tenure ${o.avgTenure} 月`;
  document.getElementById("kpi-churn").textContent = fmt.pct(o.churnRate);
  document.getElementById("kpi-churn-d").textContent = `已流失 ${Math.round(o.totalCustomers * o.churnRate / 100)} 人`;
  document.getElementById("kpi-auc").textContent = o.modelAuc.toFixed(3);
  document.getElementById("kpi-ltv").textContent = fmt.money(o.avgLtv);
  document.getElementById("kpi-ltv-d").textContent = `中位数 ${fmt.money(DATA.ltv.summary.medianLtv)}`;
  document.getElementById("kpi-risk").textContent = fmt.num(o.highRiskCount);
  document.getElementById("kpi-risk-d").textContent = `占比 ${fmt.pct(o.highRiskRate)}`;
  document.getElementById("kpi-rev").textContent = fmt.money(o.totalRevenue);
  document.getElementById("kpi-rev-d").textContent = `人均月费 ¥${o.avgMonthly}`;
}

/* ===== 维度流失分析（柱/饼切换 + 维度筛选）===== */
let dimMode = "bar";
let currentDim = "Contract";

async function renderDimChart() {
  const res = await (await fetch(`/api/churn-by-dimension?dim=${currentDim}`)).json();
  DATA.dimData = res;
  const c = init("chartDim");
  if (dimMode === "bar") {
    c.setOption({
      color: PALETTE,
      tooltip: { ...TOOLTIP, trigger: "axis", axisPointer: { type: "shadow" } },
      legend: { data: ["流失率%", "客户数"], textStyle: { color: "#8b949e", fontSize: 11 }, top: 0 },
      grid: { left: 50, right: 50, bottom: 60, top: 40 },
      xAxis: { type: "category", data: res.map(r => r[currentDim]), axisLabel: AXIS, axisLine: { lineStyle: { color: "#2a3441" } } },
      yAxis: [
        { type: "value", name: "流失率%", axisLabel: AXIS, splitLine: SPLIT },
        { type: "value", name: "客户数", axisLabel: AXIS, splitLine: { show: false } },
      ],
      series: [
        { name: "流失率%", type: "bar", data: res.map(r => r.churnRate), barWidth: "40%",
          itemStyle: { borderRadius: [4, 4, 0, 0], color: p => PALETTE[p.dataIndex % PALETTE.length] },
          label: { show: true, position: "top", formatter: "{c}%", fontSize: 11, color: "#e6edf3" } },
        { name: "客户数", type: "line", yAxisIndex: 1, data: res.map(r => r.total),
          smooth: true, lineStyle: { width: 2, color: "#bc8cff" }, itemStyle: { color: "#bc8cff" } },
      ],
    }, true);
  } else {
    c.setOption({
      color: PALETTE,
      tooltip: { ...TOOLTIP, trigger: "item", formatter: "{b}: {c} 人 ({d}%)" },
      legend: { bottom: 0, textStyle: { color: "#8b949e", fontSize: 11 }, type: "scroll" },
      series: [{
        type: "pie", radius: ["38%", "65%"], center: ["50%", "45%"],
        data: res.map(r => ({ name: String(r[currentDim]), value: r.total })),
        label: { color: "#e6edf3", fontSize: 11, formatter: "{b}\n{d}%" },
        itemStyle: { borderColor: "#161b22", borderWidth: 2 },
      }],
    }, true);
  }
}

/* ===== 特征重要性 ===== */
function renderFeature() {
  const fi = DATA.model.featureImportance.slice(0, 10).reverse();
  const c = init("chartFeature");
  c.setOption({
    tooltip: { ...TOOLTIP, trigger: "axis", axisPointer: { type: "shadow" } },
    grid: { left: 110, right: 40, top: 10, bottom: 20 },
    xAxis: { type: "value", axisLabel: AXIS, splitLine: SPLIT, max: fi[fi.length - 1].importance * 1.1 },
    yAxis: { type: "category", data: fi.map(f => f.feature), axisLabel: AXIS },
    series: [{
      type: "bar", data: fi.map(f => f.importance), barWidth: "55%",
      itemStyle: {
        borderRadius: [0, 4, 4, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: "#1f6feb" }, { offset: 1, color: "#58a6ff" },
        ]),
      },
      label: { show: true, position: "right", formatter: p => (p.value * 100).toFixed(1) + "%", fontSize: 11, color: "#8b949e" },
    }],
  });
}

/* ===== 风险分布 ===== */
function renderRiskDist() {
  const d = DATA.model.riskDistribution;
  const c = init("chartRisk");
  c.setOption({
    color: ["#58a6ff"],
    tooltip: { ...TOOLTIP, trigger: "axis" },
    grid: { left: 45, right: 25, top: 20, bottom: 35 },
    xAxis: { type: "category", data: d.map(r => r.bin), axisLabel: { ...AXIS, rotate: 30 } },
    yAxis: { type: "value", axisLabel: AXIS, splitLine: SPLIT },
    series: [{
      type: "bar", data: d.map(r => r.count), barWidth: "70%",
      itemStyle: {
        borderRadius: [4, 4, 0, 0],
        color: p => {
          const i = p.dataIndex;
          if (i >= 7) return "#f85149";
          if (i >= 5) return "#d29922";
          return "#3fb950";
        },
      },
    }],
  });
}

/* ===== 模型评估 ===== */
function renderMetrics() {
  const m = DATA.model.metrics;
  const c = init("chartMetrics");
  c.setOption({
    tooltip: { ...TOOLTIP },
    radar: {
      indicator: [
        { name: "AUC", max: 1 }, { name: "准确率", max: 1 },
        { name: "精确率", max: 1 }, { name: "召回率", max: 1 }, { name: "F1", max: 1 },
      ],
      shape: "polygon", radius: "65%",
      axisName: { color: "#8b949e", fontSize: 11 },
      splitLine: { lineStyle: { color: "#2a3441" } },
      splitArea: { areaStyle: { color: ["rgba(88,166,255,.03)", "rgba(88,166,255,.06)"] } },
    },
    series: [{
      type: "radar",
      data: [{
        value: [m.auc, m.accuracy, m.precision, m.recall, m.f1],
        name: "模型表现",
        areaStyle: { color: "rgba(88,166,255,.25)" },
        lineStyle: { color: "#58a6ff", width: 2 },
        itemStyle: { color: "#58a6ff" },
      }],
    }],
    graphic: [{
      type: "text", left: "center", bottom: 8,
      style: { text: `TP:${m.tp}  FP:${m.fp}  TN:${m.tn}  FN:${m.fn}`, fill: "#6e7681", fontSize: 11 },
    }],
  });
}

/* ===== 生存曲线 ===== */
let survMode = "all";
function renderSurvival() {
  const c = init("chartSurvival");
  let series = [];
  if (survMode === "all") {
    const s = DATA.survival.overall;
    series = [{
      name: "整体生存率", type: "line", data: s.time.map((t, i) => [t, s.survival[i]]),
      smooth: true, symbol: "none", lineStyle: { width: 3, color: "#58a6ff" },
      areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: "rgba(88,166,255,.25)" }, { offset: 1, color: "rgba(88,166,255,0)" },
      ]) },
    }];
  } else {
    const colors = { "Month-to-month": "#f85149", "One year": "#d29922", "Two year": "#3fb950" };
    series = Object.entries(DATA.survival.byContract).map(([g, s]) => ({
      name: g, type: "line", data: s.time.map((t, i) => [t, s.survival[i]]),
      smooth: true, symbol: "none", lineStyle: { width: 2.5, color: colors[g] || "#58a6ff" },
    }));
  }
  c.setOption({
    color: PALETTE,
    tooltip: { ...TOOLTIP, trigger: "axis", formatter: p => `第 ${p[0].value[0]} 月<br/>` + p.map(x => `${x.marker} ${x.seriesName}: ${(x.value[1] * 100).toFixed(1)}%`).join("<br/>") },
    legend: { textStyle: { color: "#8b949e", fontSize: 11 }, top: 0 },
    grid: { left: 45, right: 25, top: 40, bottom: 40 },
    xAxis: { type: "value", name: "tenure(月)", axisLabel: AXIS, splitLine: SPLIT, max: 72 },
    yAxis: { type: "value", name: "生存率", axisLabel: { ...AXIS, formatter: v => (v * 100) + "%" }, splitLine: SPLIT, max: 1, min: 0 },
    series,
  }, true);
}

/* ===== 风险曲线 ===== */
function renderHazard() {
  const h = DATA.survival.hazard;
  const c = init("chartHazard");
  c.setOption({
    color: ["#f85149"],
    tooltip: { ...TOOLTIP, trigger: "axis", formatter: p => `${p[0].name}<br/>流失率: ${p[0].value}%<br/>客户数: ${h[p[0].dataIndex].count}` },
    grid: { left: 45, right: 25, top: 20, bottom: 45 },
    xAxis: { type: "category", data: h.map(r => r.tenureBin), axisLabel: { ...AXIS, rotate: 35 } },
    yAxis: [{ type: "value", name: "流失率%", axisLabel: AXIS, splitLine: SPLIT }],
    series: [{
      type: "bar", data: h.map(r => (r.churnRate * 100).toFixed(1) * 1), barWidth: "60%",
      itemStyle: {
        borderRadius: [4, 4, 0, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: "#f85149" }, { offset: 1, color: "rgba(248,81,73,.2)" },
        ]),
      },
      label: { show: true, position: "top", formatter: "{c}%", fontSize: 10, color: "#e6edf3" },
    }],
  });
}

/* ===== 分群散点 ===== */
async function renderScatter() {
  // 从高风险接口已有 segment，这里用分群摘要 + 采样数据
  const segs = DATA.segments;
  const c = init("chartScatter");
  // 生成各分群的代表散点（用摘要的均值+抖动）
  const series = segs.map((s, i) => {
    const count = Math.min(s.count, 120);
    const pts = [];
    for (let j = 0; j < count; j++) {
      const t = Math.max(1, s.avgTenure + (Math.random() - 0.5) * s.avgTenure * 0.8);
      const m = Math.max(15, s.avgMonthly + (Math.random() - 0.5) * s.avgMonthly * 0.5);
      pts.push([Math.round(t), +m.toFixed(2), s.segmentName]);
    }
    return {
      name: s.segmentName, type: "scatter", data: pts,
      symbolSize: 8, itemStyle: { color: PALETTE[i], opacity: 0.7 },
    };
  });
  c.setOption({
    color: PALETTE,
    tooltip: { ...TOOLTIP, formatter: p => `${p.data[2]}<br/>tenure: ${p.data[0]}月<br/>月费: ¥${p.data[1]}` },
    legend: { textStyle: { color: "#8b949e", fontSize: 11 }, top: 0 },
    grid: { left: 50, right: 25, top: 40, bottom: 40 },
    xAxis: { type: "value", name: "tenure(月)", axisLabel: AXIS, splitLine: SPLIT, max: 72 },
    yAxis: { type: "value", name: "月费(¥)", axisLabel: AXIS, splitLine: SPLIT },
    series,
  });
}

/* ===== 分群对比雷达 ===== */
function renderSegment() {
  const segs = DATA.segments;
  const c = init("chartSegment");
  // 归一化各指标到 0-100
  const maxT = Math.max(...segs.map(s => s.avgTenure));
  const maxM = Math.max(...segs.map(s => s.avgMonthly));
  const maxTotal = Math.max(...segs.map(s => s.avgTotal));
  c.setOption({
    color: PALETTE,
    tooltip: { ...TOOLTIP },
    legend: { textStyle: { color: "#8b949e", fontSize: 11 }, bottom: 0, type: "scroll" },
    radar: {
      indicator: [
        { name: "tenure", max: 100 }, { name: "月费", max: 100 },
        { name: "总消费", max: 100 }, { name: "流失率", max: 100 }, { name: "规模", max: 100 },
      ],
      shape: "polygon", radius: "60%", center: ["50%", "48%"],
      axisName: { color: "#8b949e", fontSize: 11 },
      splitLine: { lineStyle: { color: "#2a3441" } },
    },
    series: [{
      type: "radar",
      data: segs.map((s, i) => ({
        name: s.segmentName,
        value: [
          +(s.avgTenure / maxT * 100).toFixed(0),
          +(s.avgMonthly / maxM * 100).toFixed(0),
          +(s.avgTotal / maxTotal * 100).toFixed(0),
          +s.churnRate.toFixed(0),
          +(s.count / Math.max(...segs.map(x => x.count)) * 100).toFixed(0),
        ],
        areaStyle: { opacity: 0.15 },
      })),
    }],
  });
}

/* ===== 营销活动（指标切换）===== */
let campMetric = "roi";
function renderCampaign() {
  const camps = DATA.campaigns.campaigns;
  const labelMap = { roi: "ROI", conversionRate: "转化率%", revenue: "收入(¥)" };
  const valFn = { roi: r => r.roi, conversionRate: r => +(r.conversionRate * 100).toFixed(2), revenue: r => r.revenue };
  const c = init("chartCampaign");
  c.setOption({
    color: ["#58a6ff"],
    tooltip: { ...TOOLTIP, trigger: "axis", axisPointer: { type: "shadow" },
      formatter: p => `${p[0].name}<br/>${labelMap[campMetric]}: ${p[0].value}${campMetric === "roi" ? "" : campMetric === "conversionRate" ? "%" : ""}` },
    grid: { left: 55, right: 25, top: 20, bottom: 70 },
    xAxis: { type: "category", data: camps.map(r => r.campaignName), axisLabel: { ...AXIS, rotate: 30 }, axisLine: { lineStyle: { color: "#2a3441" } } },
    yAxis: { type: "value", axisLabel: AXIS, splitLine: SPLIT },
    series: [{
      type: "bar", data: camps.map(r => valFn[campMetric](r)), barWidth: "50%",
      itemStyle: {
        borderRadius: [4, 4, 0, 0],
        color: p => {
          const v = p.value;
          if (campMetric === "roi") return v >= 1.5 ? "#3fb950" : v >= 0.5 ? "#d29922" : "#f85149";
          return PALETTE[p.dataIndex % PALETTE.length];
        },
      },
      label: { show: true, position: "top", fontSize: 11, color: "#e6edf3",
        formatter: p => campMetric === "roi" ? p.value.toFixed(2) : campMetric === "conversionRate" ? p.value + "%" : "¥" + p.value.toLocaleString() },
    }],
  }, true);
}

/* ===== 渠道质量 ===== */
function renderChannel() {
  const ch = DATA.channels;
  const c = init("chartChannel");
  c.setOption({
    color: PALETTE,
    tooltip: { ...TOOLTIP, trigger: "axis", axisPointer: { type: "shadow" } },
    legend: { textStyle: { color: "#8b949e", fontSize: 11 }, top: 0 },
    grid: { left: 55, right: 60, top: 40, bottom: 40 },
    xAxis: { type: "category", data: ch.map(r => r.signupChannel), axisLabel: AXIS },
    yAxis: [
      { type: "value", name: "金额/月", axisLabel: AXIS, splitLine: SPLIT },
      { type: "value", name: "流失率%", axisLabel: AXIS, splitLine: { show: false } },
    ],
    series: [
      { name: "平均LTV", type: "bar", data: ch.map(r => r.avgLtv), barWidth: "25%", itemStyle: { color: "#58a6ff", borderRadius: [4,4,0,0] } },
      { name: "获客成本", type: "bar", data: ch.map(r => r.avgAcqCost), barWidth: "25%", itemStyle: { color: "#d29922", borderRadius: [4,4,0,0] } },
      { name: "流失率%", type: "line", yAxisIndex: 1, data: ch.map(r => r.churnRate), smooth: true, lineStyle: { width: 2, color: "#f85149" }, itemStyle: { color: "#f85149" } },
    ],
  });
}

/* ===== 漏斗 ===== */
function renderFunnel() {
  const t = DATA.campaigns.totals;
  const c = init("chartFunnel");
  c.setOption({
    color: ["#58a6ff", "#bc8cff", "#3fb950"],
    tooltip: { ...TOOLTIP, formatter: "{b}: {c} ({d}%)" },
    series: [{
      type: "funnel", left: "15%", right: "15%", top: 20, bottom: 20,
      minSize: "30%", sort: "descending", gap: 4,
      label: { color: "#e6edf3", fontSize: 12, formatter: "{b}\n{c}" },
      itemStyle: { borderColor: "#161b22", borderWidth: 1 },
      data: [
        { value: t.reach, name: "触达人数" },
        { value: t.convert, name: "转化人数" },
        { value: Math.round(t.revenue / 400), name: "等效订单" },
      ],
    }],
  });
}

/* ===== 活动类型聚合 ===== */
function renderCampType() {
  const bt = DATA.campaigns.byType;
  const c = init("chartCampType");
  c.setOption({
    color: PALETTE,
    tooltip: { ...TOOLTIP, trigger: "axis", axisPointer: { type: "shadow" } },
    legend: { textStyle: { color: "#8b949e", fontSize: 11 }, top: 0 },
    grid: { left: 55, right: 25, top: 40, bottom: 35 },
    xAxis: { type: "category", data: bt.map(r => r.campaignType), axisLabel: AXIS },
    yAxis: { type: "value", axisLabel: AXIS, splitLine: SPLIT },
    series: [
      { name: "投入", type: "bar", data: bt.map(r => +r.totalCost.toFixed(0)), itemStyle: { color: "#d29922", borderRadius: [4,4,0,0] } },
      { name: "收入", type: "bar", data: bt.map(r => +r.totalRevenue.toFixed(0)), itemStyle: { color: "#3fb950", borderRadius: [4,4,0,0] } },
    ],
  });
}

/* ===== LTV 分布 ===== */
function renderLtvDist() {
  const d = DATA.ltv.distribution;
  const c = init("chartLtvDist");
  c.setOption({
    color: ["#58a6ff"],
    tooltip: { ...TOOLTIP, trigger: "axis" },
    grid: { left: 45, right: 25, top: 20, bottom: 35 },
    xAxis: { type: "category", data: d.map(r => r.bin), axisLabel: AXIS },
    yAxis: { type: "value", axisLabel: AXIS, splitLine: SPLIT },
    series: [{
      type: "bar", data: d.map(r => r.count), barWidth: "55%",
      itemStyle: {
        borderRadius: [4, 4, 0, 0],
        color: p => p.dataIndex === 0 ? "#f85149" : "#3fb950",
      },
      label: { show: true, position: "top", fontSize: 11, color: "#8b949e" },
    }],
  });
}

/* ===== LTV 分群 ===== */
function renderLtvSeg() {
  const s = DATA.ltv.bySegment;
  const c = init("chartLtvSeg");
  c.setOption({
    color: ["#58a6ff", "#bc8cff"],
    tooltip: { ...TOOLTIP, trigger: "axis", axisPointer: { type: "shadow" } },
    legend: { textStyle: { color: "#8b949e", fontSize: 11 }, top: 0 },
    grid: { left: 55, right: 55, top: 40, bottom: 70 },
    xAxis: { type: "category", data: s.map(r => r.segmentName), axisLabel: { ...AXIS, rotate: 20 } },
    yAxis: [
      { type: "value", name: "LTV(¥)", axisLabel: AXIS, splitLine: SPLIT },
      { type: "value", name: "正价值占比%", axisLabel: AXIS, splitLine: { show: false } },
    ],
    series: [
      { name: "平均LTV", type: "bar", data: s.map(r => r.avgLtv), barWidth: "40%",
        itemStyle: { color: "#58a6ff", borderRadius: [4,4,0,0] },
        label: { show: true, position: "top", formatter: "¥{c}", fontSize: 11, color: "#e6edf3" } },
      { name: "正价值占比%", type: "line", yAxisIndex: 1, data: s.map(r => r.positiveRate),
        smooth: true, lineStyle: { width: 2, color: "#bc8cff" }, itemStyle: { color: "#bc8cff" } },
    ],
  });
}

/* ===== 挽留模拟器 ===== */
async function updateSimulator(budget) {
  const r = await (await fetch(`/api/retention?budget=${budget}`)).json();
  document.getElementById("sim-count").textContent = fmt.num(r.highRiskTotal);
  document.getElementById("sim-worth").textContent = fmt.num(r.worthRetaining);
  document.getElementById("sim-gain").textContent = fmt.money(r.netGain);
  document.getElementById("sim-prob").textContent = fmt.pct(r.avgRetainProb * 100);
}

/* ===== 高风险客户表 ===== */
function renderRiskTable() {
  const rows = DATA.highRisk;
  const tb = document.getElementById("riskTbody");
  tb.innerHTML = rows.map(r => {
    const tier = r.riskTier;
    const tag = tier === "高风险" ? "tag-red" : tier === "中风险" ? "tag-orange" : "tag-green";
    return `<tr>
      <td>${r.customerID}</td><td>${r.gender}</td><td>${r.tenure}</td>
      <td>${r.Contract}</td><td>¥${r.MonthlyCharges}</td><td>${r.InternetService}</td>
      <td style="font-size:11px">${r.PaymentMethod}</td>
      <td><span style="color:#f85149;font-weight:600">${(r.churnRisk * 100).toFixed(1)}%</span></td>
      <td><span class="tag ${tag}">${r.riskTier}</span></td>
      <td style="font-size:11px">${r.segmentName}</td>
      <td>¥${Math.round(r.ltv)}</td><td style="font-size:11px">${r.signupChannel}</td>
    </tr>`;
  }).join("");
}

/* ===== 主渲染 ===== */
function renderAll() {
  renderKPI();
  renderFeature();
  renderRiskDist();
  renderMetrics();
  renderSurvival();
  renderHazard();
  renderScatter();
  renderSegment();
  renderCampaign();
  renderChannel();
  renderFunnel();
  renderCampType();
  renderLtvDist();
  renderLtvSeg();
  renderRiskTable();
  renderDimChart();
}

/* ===== 事件绑定 ===== */
function bindEvents() {
  // 维度下拉
  const sel = document.getElementById("dimSelect");
  DATA.dimensions.forEach(d => {
    const opt = document.createElement("option");
    opt.value = d.key; opt.textContent = d.label;
    sel.appendChild(opt);
  });
  sel.addEventListener("change", e => { currentDim = e.target.value; renderDimChart(); });
  // 图表切换
  document.getElementById("dimBar").addEventListener("click", () => {
    dimMode = "bar"; setActive("dimBar", "dimPie"); renderDimChart();
  });
  document.getElementById("dimPie").addEventListener("click", () => {
    dimMode = "pie"; setActive("dimPie", "dimBar"); renderDimChart();
  });
  // 生存曲线切换
  document.getElementById("survAll").addEventListener("click", () => {
    survMode = "all"; setActive("survAll", "survContract"); renderSurvival();
  });
  document.getElementById("survContract").addEventListener("click", () => {
    survMode = "contract"; setActive("survContract", "survAll"); renderSurvival();
  });
  // 营销指标切换
  const mBtns = { roi: "mRoi", conversionRate: "mCv", revenue: "mRev" };
  Object.entries(mBtns).forEach(([k, id]) => {
    document.getElementById(id).addEventListener("click", () => {
      campMetric = k;
      ["mRoi", "mCv", "mRev"].forEach(x => document.getElementById(x).classList.remove("active"));
      document.getElementById(id).classList.add("active");
      renderCampaign();
    });
  });
  // 挽留模拟器
  const slider = document.getElementById("budgetSlider");
  slider.addEventListener("input", e => {
    document.getElementById("budgetVal").textContent = "¥" + e.target.value;
    updateSimulator(+e.target.value);
  });
}

function setActive(on, off) {
  document.getElementById(on).classList.add("active");
  document.getElementById(off).classList.remove("active");
}

/* ===== 启动 ===== */
(async () => {
  await loadAll();
  bindEvents();
  updateSimulator(50);
})();
