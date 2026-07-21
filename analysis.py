"""
客户流失与营销分析核心模块
包含：流失预测（随机森林 + 风险评分）、生存分析（Kaplan-Meier + Cox 近似）、
客户分群（RFM + KMeans）、营销活动效果、客户生命周期价值 LTV。
所有分析在初始化时一次性完成，供 Flask 接口直接取用。
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.cluster import KMeans
from sklearn.metrics import roc_auc_score, confusion_matrix

CAT_COLS = [
    "gender", "Partner", "Dependents", "PhoneService", "MultipleLines",
    "InternetService", "OnlineSecurity", "OnlineBackup", "DeviceProtection",
    "TechSupport", "StreamingTV", "StreamingMovies", "Contract",
    "PaperlessBilling", "PaymentMethod", "signupChannel",
]
NUM_COLS = ["SeniorCitizen", "tenure", "MonthlyCharges", "TotalCharges", "acquisitionCost"]


class ChurnMarketingAnalyzer:
    def __init__(self, customers, campaigns):
        self.df = customers.copy()
        self.camp = campaigns.copy()
        self.encoders = {}
        self._preprocess()
        self._train_model()
        self._score_customers()
        self._segment()
        self._survival()
        self._ltv()

    # ---------- 预处理 ----------
    def _preprocess(self):
        d = self.df
        d["ChurnFlag"] = (d["Churn"] == "Yes").astype(int)
        self.ml = d.copy()
        for c in CAT_COLS:
            le = LabelEncoder()
            self.ml[c] = le.fit_transform(self.ml[c].astype(str))
            self.encoders[c] = le
        self.features = NUM_COLS + CAT_COLS

    # ---------- 流失预测 ----------
    def _train_model(self):
        X = self.ml[self.features]
        y = self.ml["ChurnFlag"]
        self.model = RandomForestClassifier(
            n_estimators=300, max_depth=10, min_samples_leaf=20,
            class_weight="balanced", random_state=42, n_jobs=-1,
        )
        self.model.fit(X, y)
        self.proba = self.model.predict_proba(X)[:, 1]
        self.pred = (self.proba >= 0.5).astype(int)
        self.auc = roc_auc_score(y, self.proba)
        tn, fp, fn, tp = confusion_matrix(y, self.pred).ravel()
        self.metrics = {
            "auc": round(float(self.auc), 4),
            "accuracy": round(float((tp + tn) / (tp + tn + fp + fn)), 4),
            "precision": round(float(tp / (tp + fp)) if (tp + fp) else 0, 4),
            "recall": round(float(tp / (tp + fn)) if (tp + fn) else 0, 4),
            "f1": round(float(2 * tp / (2 * tp + fp + fn)) if (2 * tp + fp + fn) else 0, 4),
            "tp": int(tp), "fp": int(fp), "tn": int(tn), "fn": int(fn),
        }

    def _score_customers(self):
        self.df["churnRisk"] = np.round(self.proba, 4)
        self.df["riskTier"] = pd.cut(
            self.proba,
            bins=[0, 0.3, 0.55, 1.01],
            labels=["低风险", "中风险", "高风险"],
        )
        importances = self.model.feature_importances_
        self.feature_importance = sorted(
            [
                {"feature": f, "importance": round(float(i), 5)}
                for f, i in zip(self.features, importances)
            ],
            key=lambda x: -x["importance"],
        )

    # ---------- 客户分群 ----------
    def _segment(self):
        d = self.df
        # RFM 简化版：R=tenure(留存越久越好，反向) F=月费 M=总消费
        rfm = pd.DataFrame({
            "tenure": d["tenure"].astype(float),
            "monthly": d["MonthlyCharges"].astype(float),
            "total": d["TotalCharges"].astype(float),
        })
        # 用 min-max 归一化避免大数值溢出
        rfm_scaled = (rfm - rfm.min()) / (rfm.max() - rfm.min() + 1e-6)
        km = KMeans(n_clusters=4, n_init=10, random_state=42)
        d["segment"] = km.fit_predict(rfm_scaled)
        seg_summary = (
            d.groupby("segment")
            .agg(
                count=("customerID", "size"),
                avgTenure=("tenure", "mean"),
                avgMonthly=("MonthlyCharges", "mean"),
                avgTotal=("TotalCharges", "mean"),
                churnRate=("ChurnFlag", "mean"),
            )
            .reset_index()
        )
        seg_summary["avgTenure"] = seg_summary["avgTenure"].round(1)
        seg_summary["avgMonthly"] = seg_summary["avgMonthly"].round(2)
        seg_summary["avgTotal"] = seg_summary["avgTotal"].round(2)
        seg_summary["churnRate"] = (seg_summary["churnRate"] * 100).round(2)
        # 命名分群（按综合价值排序后命名）
        seg_summary = seg_summary.sort_values("avgTotal", ascending=False).reset_index(drop=True)
        rank_names = ["高价值忠诚", "中等潜力", "稳定低消", "新客待培育"]
        seg_summary["segmentName"] = rank_names[: len(seg_summary)]
        name_map = dict(zip(seg_summary["segment"], seg_summary["segmentName"]))
        d["segmentName"] = d["segment"].map(name_map)
        self.segment_summary = seg_summary.to_dict("records")

    # ---------- 生存分析（手写 Kaplan-Meier + Cox 近似）----------
    def _survival(self):
        d = self.df
        # Kaplan-Meier 整体曲线
        self.km_overall = self._kaplan_meier(d["tenure"].values, d["ChurnFlag"].values)
        # 按合同类型分组的生存曲线
        self.km_by_contract = {}
        for g, sub in d.groupby("Contract"):
            self.km_by_contract[g] = self._kaplan_meier(
                sub["tenure"].values, sub["ChurnFlag"].values
            )
        # Cox 近似：用 tenure 段上的风险率近似
        self.hazard_by_tenure = self._hazard_curve(d)

    @staticmethod
    def _kaplan_meier(time, event):
        time = np.asarray(time, dtype=float)
        event = np.asarray(event, dtype=float)
        order = np.argsort(time)
        time, event = time[order], event[order]
        unique_t = np.unique(time)
        n_at_risk = np.array([np.sum(time >= t) for t in unique_t])
        d_event = np.array([np.sum((time == t) & (event == 1)) for t in unique_t])
        surv = np.cumprod(1 - d_event / np.maximum(n_at_risk, 1))
        return {
            "time": unique_t.astype(int).tolist(),
            "survival": np.round(surv, 4).tolist(),
            "atRisk": n_at_risk.tolist(),
            "events": d_event.tolist(),
        }

    @staticmethod
    def _hazard_curve(d):
        bins = np.arange(0, 73, 6)
        out = []
        for i in range(len(bins) - 1):
            lo, hi = bins[i], bins[i + 1]
            mask = (d["tenure"] >= lo) & (d["tenure"] < hi)
            sub = d[mask]
            if len(sub) == 0:
                continue
            out.append({
                "tenureBin": f"{lo}-{hi}月",
                "churnRate": round(float(sub["ChurnFlag"].mean()), 4),
                "count": int(len(sub)),
                "avgMonthly": round(float(sub["MonthlyCharges"].mean()), 2),
            })
        return out

    # ---------- LTV ----------
    def _ltv(self):
        d = self.df
        # LTV = 月费 * 预期留存月数(用 1/流失率近似) - 获客成本
        d["expectedLifeMonths"] = np.where(
            d["churnRisk"] > 0.01,
            np.clip(1 / d["churnRisk"], 1, 60),
            60,
        )
        d["ltv"] = np.round(
            d["MonthlyCharges"] * d["expectedLifeMonths"] * 0.85 - d["acquisitionCost"], 2
        )
        self.ltv_summary = {
            "avgLtv": round(float(d["ltv"].mean()), 2),
            "medianLtv": round(float(d["ltv"].median()), 2),
            "totalLtv": round(float(d["ltv"].sum()), 2),
            "positiveRate": round(float((d["ltv"] > 0).mean()), 4),
        }

    # ---------- 维度聚合（前端按维度筛选流失率）----------
    def churn_by_dimension(self, dim):
        d = self.df
        if dim not in d.columns:
            return []
        g = d.groupby(dim).agg(
            total=("customerID", "size"),
            churned=("ChurnFlag", "sum"),
            churnRate=("ChurnFlag", "mean"),
            avgMonthly=("MonthlyCharges", "mean"),
            avgRisk=("churnRisk", "mean"),
        ).reset_index()
        g["churnRate"] = (g["churnRate"] * 100).round(2)
        g["avgMonthly"] = g["avgMonthly"].round(2)
        g["avgRisk"] = (g["avgRisk"] * 100).round(2)
        return g.to_dict("records")

    # ---------- 风险分布 ----------
    def risk_distribution(self):
        d = self.df
        bins = np.linspace(0, 1, 11)
        labels = [f"{int(bins[i]*100)}-{int(bins[i+1]*100)}%" for i in range(len(bins) - 1)]
        d2 = pd.cut(d["churnRisk"], bins=bins, labels=labels, include_lowest=True)
        g = d2.value_counts().sort_index()
        return [{"bin": k, "count": int(v)} for k, v in g.items()]

    # ---------- 营销活动分析 ----------
    def campaign_analysis(self):
        c = self.camp.copy()
        by_type = c.groupby("campaignType").agg(
            campaigns=("campaignId", "size"),
            totalReach=("reachCount", "sum"),
            totalConvert=("convertCount", "sum"),
            totalCost=("cost", "sum"),
            totalRevenue=("revenue", "sum"),
            avgRoi=("roi", "mean"),
            avgCv=("conversionRate", "mean"),
        ).reset_index()
        by_type["avgRoi"] = by_type["avgRoi"].round(3)
        by_type["avgCv"] = (by_type["avgCv"] * 100).round(2)
        return {
            "campaigns": c.to_dict("records"),
            "byType": by_type.to_dict("records"),
            "byChannel": c.groupby("channel").agg(
                totalReach=("reachCount", "sum"),
                totalConvert=("convertCount", "sum"),
                totalCost=("cost", "sum"),
                totalRevenue=("revenue", "sum"),
            ).reset_index().to_dict("records"),
            "totals": {
                "reach": int(c["reachCount"].sum()),
                "convert": int(c["convertCount"].sum()),
                "cost": round(float(c["cost"].sum()), 2),
                "revenue": round(float(c["revenue"].sum()), 2),
                "overallRoi": round(float((c["revenue"].sum() - c["cost"].sum()) / c["cost"].sum()), 3),
            },
        }

    # ---------- 概览 KPI ----------
    def overview(self):
        d = self.df
        return {
            "totalCustomers": int(len(d)),
            "churnRate": round(float(d["ChurnFlag"].mean() * 100), 2),
            "avgTenure": round(float(d["tenure"].mean()), 1),
            "avgMonthly": round(float(d["MonthlyCharges"].mean()), 2),
            "totalRevenue": round(float(d["MonthlyCharges"].sum()), 2),
            "highRiskCount": int((d["riskTier"] == "高风险").sum()),
            "highRiskRate": round(float((d["riskTier"] == "高风险").mean() * 100), 2),
            "modelAuc": self.metrics["auc"],
            "avgLtv": self.ltv_summary["avgLtv"],
            "acquisitionCost": round(float(d["acquisitionCost"].mean()), 2),
        }

    # ---------- 高风险客户列表 ----------
    def high_risk_customers(self, limit=50):
        d = self.df.sort_values("churnRisk", ascending=False).head(limit)
        cols = [
            "customerID", "gender", "tenure", "Contract", "MonthlyCharges",
            "InternetService", "PaymentMethod", "churnRisk", "riskTier",
            "segmentName", "ltv", "signupChannel",
        ]
        return d[cols].to_dict("records")

    # ---------- 阈值模拟：不同挽留投入下的可挽回客户与收益 ----------
    def retention_simulator(self, budget_per_customer=50):
        d = self.df
        high = d[d["riskTier"] == "高风险"].copy()
        # 挽留成功率与风险分正相关，投入越高成功率越高
        high["retainProb"] = np.clip(high["churnRisk"] * 0.5 + budget_per_customer / 300, 0.05, 0.65)
        # 挽留收益 = 保住的未来 12 个月收入（扣除服务成本 15%）
        high["savedRevenue"] = high["MonthlyCharges"] * 12 * 0.85
        high["retainCost"] = budget_per_customer
        high["retainBenefit"] = high["savedRevenue"] * high["retainProb"]
        high["netGain"] = high["retainBenefit"] - high["retainCost"]
        worth = high[high["netGain"] > 0]
        return {
            "budgetPerCustomer": budget_per_customer,
            "highRiskTotal": int(len(high)),
            "worthRetaining": int(len(worth)),
            "totalCost": round(float(worth["retainCost"].sum()), 2),
            "totalBenefit": round(float(worth["retainBenefit"].sum()), 2),
            "netGain": round(float(worth["netGain"].sum()), 2),
            "avgRetainProb": round(float(high["retainProb"].mean()), 4),
            "avgSavedRevenue": round(float(high["savedRevenue"].mean()), 2),
        }

    # ---------- 渠道获客质量 ----------
    def channel_quality(self):
        d = self.df
        g = d.groupby("signupChannel").agg(
            customers=("customerID", "size"),
            avgAcqCost=("acquisitionCost", "mean"),
            avgTenure=("tenure", "mean"),
            churnRate=("ChurnFlag", "mean"),
            avgMonthly=("MonthlyCharges", "mean"),
            avgLtv=("ltv", "mean"),
        ).reset_index()
        g["churnRate"] = (g["churnRate"] * 100).round(2)
        g["avgAcqCost"] = g["avgAcqCost"].round(2)
        g["avgTenure"] = g["avgTenure"].round(1)
        g["avgMonthly"] = g["avgMonthly"].round(2)
        g["avgLtv"] = g["avgLtv"].round(2)
        return g.to_dict("records")
