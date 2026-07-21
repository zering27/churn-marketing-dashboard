"""
构建脚本：运行全部分析，导出为静态 JSON 供自包含 HTML 使用。
复用项目的 data_generator 和 analysis 模块。
"""
import sys
import os
import json

# 使用相对路径，兼容 clone 后的目录结构
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from data_generator import generate_all
from analysis import ChurnMarketingAnalyzer

import warnings
warnings.filterwarnings("ignore")

print("正在生成数据并训练模型...")
customers, campaigns = generate_all()
az = ChurnMarketingAnalyzer(customers, campaigns)
print(f"模型 AUC = {az.metrics['auc']}")


def safe(o):
    if isinstance(o, dict):
        return {k: safe(v) for k, v in o.items()}
    if isinstance(o, list):
        return [safe(v) for v in o]
    import numpy as np
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return safe(o.tolist())
    return o


DIMENSIONS = [
    {"key": "Contract", "label": "合同类型"},
    {"key": "InternetService", "label": "上网方式"},
    {"key": "PaymentMethod", "label": "付费方式"},
    {"key": "signupChannel", "label": "获客渠道"},
    {"key": "segmentName", "label": "客户分群"},
    {"key": "riskTier", "label": "风险等级"},
    {"key": "gender", "label": "性别"},
    {"key": "SeniorCitizen", "label": "是否老年"},
    {"key": "Partner", "label": "是否有伴侣"},
    {"key": "Dependents", "label": "是否有家属"},
    {"key": "PaperlessBilling", "label": "电子账单"},
    {"key": "OnlineSecurity", "label": "在线安全"},
    {"key": "TechSupport", "label": "技术支持"},
]

churn_by_dim = {}
for d in DIMENSIONS:
    churn_by_dim[d["key"]] = safe(az.churn_by_dimension(d["key"]))

retention_by_budget = {}
for b in range(20, 210, 10):
    retention_by_budget[str(b)] = safe(az.retention_simulator(b))

import pandas as pd
d = az.df
ltv_bins = [-1000, 0, 100, 300, 600, 100000]
ltv_labels = ["负价值", "0-100", "100-300", "300-600", "600+"]
d2 = pd.cut(d["ltv"], bins=ltv_bins, labels=ltv_labels)
ltv_dist = d2.value_counts().sort_index()
ltv_by_seg = d.groupby("segmentName").agg(
    avgLtv=("ltv", "mean"),
    count=("customerID", "size"),
    positiveRate=("ltv", lambda x: (x > 0).mean()),
).reset_index()
ltv_by_seg["avgLtv"] = ltv_by_seg["avgLtv"].round(2)
ltv_by_seg["positiveRate"] = (ltv_by_seg["positiveRate"] * 100).round(2)

scatter_data = []
for seg_name in az.df["segmentName"].unique():
    sub = az.df[az.df["segmentName"] == seg_name]
    sample = sub.sample(min(150, len(sub)), random_state=42)
    for _, row in sample.iterrows():
        scatter_data.append([int(row["tenure"]), round(float(row["MonthlyCharges"]), 2), seg_name])

high_risk = safe(az.high_risk_customers(30))

ALL_DATA = {
    "overview": safe(az.overview()),
    "model": safe({
        "metrics": az.metrics,
        "featureImportance": az.feature_importance,
        "riskDistribution": az.risk_distribution(),
    }),
    "dimensions": DIMENSIONS,
    "churnByDim": churn_by_dim,
    "survival": safe({
        "overall": az.km_overall,
        "byContract": az.km_by_contract,
        "hazard": az.hazard_by_tenure,
    }),
    "segments": safe(az.segment_summary),
    "ltv": safe({
        "summary": az.ltv_summary,
        "distribution": [{"bin": k, "count": int(v)} for k, v in ltv_dist.items()],
        "bySegment": ltv_by_seg.to_dict("records"),
    }),
    "campaigns": safe(az.campaign_analysis()),
    "channels": safe(az.channel_quality()),
    "highRisk": high_risk,
    "retention": retention_by_budget,
    "scatter": scatter_data,
}

# 输出到 dist 目录
dist_dir = os.path.join(BASE_DIR, "dist")
os.makedirs(dist_dir, exist_ok=True)
out_path = os.path.join(dist_dir, "data.js")
with open(out_path, "w", encoding="utf-8") as f:
    f.write("/* 预计算的分析数据，由 build_static.py 生成 */\n")
    f.write("var REPORT_DATA = ")
    json.dump(ALL_DATA, f, ensure_ascii=False, separators=(",", ":"))
    f.write(";\n")

size_kb = os.path.getsize(out_path) / 1024
print(f"数据已导出: {out_path} ({size_kb:.1f} KB)")
print(f"维度数: {len(DIMENSIONS)} | 挽留档位: {len(retention_by_budget)} | 散点: {len(scatter_data)} | 高风险: {len(high_risk)}")
