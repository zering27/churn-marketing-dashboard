"""
客户流失与营销分析仪表盘 —— Flask 后端
启动：python app.py  然后访问 http://127.0.0.1:5050
"""
import os
import numpy as np
from flask import Flask, jsonify, render_template, request

from data_generator import generate_all
from analysis import ChurnMarketingAnalyzer

app = Flask(__name__, static_folder="static", template_folder="templates")

# 启动时生成数据并完成全部分析
print("正在生成数据并训练模型...")
_customers, _campaigns = generate_all()
analyzer = ChurnMarketingAnalyzer(_customers, _campaigns)
print(f"模型训练完成，AUC = {analyzer.metrics['auc']}")


def _safe(o):
    """递归把 numpy 类型转成原生类型，方便 jsonify。"""
    if isinstance(o, dict):
        return {k: _safe(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_safe(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return _safe(o.tolist())
    return o


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/overview")
def api_overview():
    return jsonify(_safe(analyzer.overview()))


@app.route("/api/model")
def api_model():
    return jsonify(_safe({
        "metrics": analyzer.metrics,
        "featureImportance": analyzer.feature_importance,
        "riskDistribution": analyzer.risk_distribution(),
    }))


@app.route("/api/churn-by-dimension")
def api_churn_by_dimension():
    dim = request.args.get("dim", "Contract")
    return jsonify(_safe(analyzer.churn_by_dimension(dim)))


@app.route("/api/dimensions")
def api_dimensions():
    return jsonify([
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
    ])


@app.route("/api/survival")
def api_survival():
    return jsonify(_safe({
        "overall": analyzer.km_overall,
        "byContract": analyzer.km_by_contract,
        "hazard": analyzer.hazard_by_tenure,
    }))


@app.route("/api/segments")
def api_segments():
    return jsonify(_safe(analyzer.segment_summary))


@app.route("/api/ltv")
def api_ltv():
    d = analyzer.df
    # LTV 分群分布
    ltv_bins = [-1000, 0, 100, 300, 600, 100000]
    ltv_labels = ["负价值", "0-100", "100-300", "300-600", "600+"]
    d2 = pd.cut(d["ltv"], bins=ltv_bins, labels=ltv_labels)
    dist = d2.value_counts().sort_index()
    return jsonify(_safe({
        "summary": analyzer.ltv_summary,
        "distribution": [{"bin": k, "count": int(v)} for k, v in dist.items()],
        "bySegment": d.groupby("segmentName").agg(
            avgLtv=("ltv", "mean"),
            count=("customerID", "size"),
            positiveRate=("ltv", lambda x: (x > 0).mean()),
        ).reset_index().assign(
            avgLtv=lambda x: x["avgLtv"].round(2),
            positiveRate=lambda x: (x["positiveRate"] * 100).round(2),
        ).to_dict("records"),
    }))


@app.route("/api/campaigns")
def api_campaigns():
    return jsonify(_safe(analyzer.campaign_analysis()))


@app.route("/api/channels")
def api_channels():
    return jsonify(_safe(analyzer.channel_quality()))


@app.route("/api/high-risk")
def api_high_risk():
    limit = request.args.get("limit", 50, type=int)
    return jsonify(_safe(analyzer.high_risk_customers(limit)))


@app.route("/api/retention")
def api_retention():
    budget = request.args.get("budget", 50, type=int)
    return jsonify(_safe(analyzer.retention_simulator(budget)))


# 引入 pandas 别名（LTV 接口用到）
import pandas as pd  # noqa: E402

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=False)
