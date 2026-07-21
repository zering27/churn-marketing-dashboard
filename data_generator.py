"""
电信客户流失与营销数据生成器
基于 IBM Telco Customer Churn 数据集的特征分布，生成贴近真实业务场景的合成数据。
包含：客户基础信息、订阅服务、合同与付费、月费与 tenure、流失标签，以及营销活动数据。
"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(20260721)

N_CUSTOMERS = 7043


def _build_customers():
    cid = [f"CUST-{10000 + i:05d}" for i in range(N_CUSTOMERS)]
    gender = rng.choice(["Male", "Female"], N_CUSTOMERS, p=[0.505, 0.495])
    senior = rng.choice([0, 1], N_CUSTOMERS, p=[0.84, 0.16])
    partner = rng.choice(["Yes", "No"], N_CUSTOMERS, p=[0.48, 0.52])
    dependents = rng.choice(["Yes", "No"], N_CUSTOMERS, p=[0.30, 0.70])

    tenure = _gen_tenure(N_CUSTOMERS, senior, partner, dependents)
    phone = rng.choice(["Yes", "No"], N_CUSTOMERS, p=[0.90, 0.10])
    multi = np.where(
        phone == "Yes",
        rng.choice(["Yes", "No", "No phone service"], N_CUSTOMERS, p=[0.42, 0.48, 0.10]),
        "No phone service",
    )
    internet = rng.choice(
        ["DSL", "Fiber optic", "No"], N_CUSTOMERS, p=[0.34, 0.44, 0.22]
    )
    sec, backup, protect, support, stv, smovie = _gen_addons(internet)
    contract = _gen_contract(tenure)
    paperless = rng.choice(["Yes", "No"], N_CUSTOMERS, p=[0.59, 0.41])
    payment = _gen_payment(contract, paperless)
    monthly = _gen_monthly(internet, contract, sec, backup, protect, support, stv, smovie)
    total = tenure * monthly * rng.uniform(0.92, 1.05, N_CUSTOMERS)

    churn_prob = _churn_logits(
        tenure, monthly, contract, internet, payment, senior, support, sec
    )
    churn = np.where(rng.random(N_CUSTOMERS) < churn_prob, "Yes", "No")

    df = pd.DataFrame(
        {
            "customerID": cid,
            "gender": gender,
            "SeniorCitizen": senior,
            "Partner": partner,
            "Dependents": dependents,
            "tenure": tenure,
            "PhoneService": phone,
            "MultipleLines": multi,
            "InternetService": internet,
            "OnlineSecurity": sec,
            "OnlineBackup": backup,
            "DeviceProtection": protect,
            "TechSupport": support,
            "StreamingTV": stv,
            "StreamingMovies": smovie,
            "Contract": contract,
            "PaperlessBilling": paperless,
            "PaymentMethod": payment,
            "MonthlyCharges": np.round(monthly, 2),
            "TotalCharges": np.round(total, 2),
            "Churn": churn,
        }
    )
    # 注册渠道与首次接触时间，用于营销归因
    df["signupChannel"] = rng.choice(
        ["官网", "应用商店", "线下门店", "电话外呼", "转介绍"], N_CUSTOMERS,
        p=[0.28, 0.22, 0.20, 0.16, 0.14],
    )
    df["acquisitionCost"] = np.round(
        df["signupChannel"].map(
            {"官网": 45, "应用商店": 38, "线下门店": 120, "电话外呼": 95, "转介绍": 25}
        ).astype(float)
        * rng.uniform(0.8, 1.3, N_CUSTOMERS),
        2,
    )
    return df


def _gen_tenure(n, senior, partner, dependents):
    base = rng.beta(1.6, 2.8, n) * 72
    base = np.where(partner == "Yes", base * 1.15, base)
    base = np.where(dependents == "Yes", base * 1.20, base)
    base = np.where(senior == 1, base * 0.9, base)
    return np.clip(base.astype(int), 1, 72)


def _gen_addons(internet):
    no_net = internet == "No"
    labels = ["Yes", "No", "No internet service"]
    def col(p_yes):
        out = rng.choice(labels, N_CUSTOMERS, p=[p_yes, 1 - p_yes - 0.22, 0.22])
        out = np.where(no_net, "No internet service", out)
        return out
    return col(0.29), col(0.34), col(0.34), col(0.29), col(0.38), col(0.39)


def _gen_contract(tenure):
    p_long = np.clip(tenure / 72, 0, 0.85)
    p_two = p_long * 0.55
    p_one = p_long * 0.45
    p_month = 1 - p_two - p_one
    u = rng.random(N_CUSTOMERS)
    return np.where(
        u < p_month, "Month-to-month",
        np.where(u < p_month + p_one, "One year", "Two year"),
    )


def _gen_payment(contract, paperless):
    base = rng.choice(
        ["Electronic check", "Mailed check", "Bank transfer (automatic)", "Credit card (automatic)"],
        N_CUSTOMERS, p=[0.34, 0.23, 0.22, 0.21],
    )
    # 长期合同更倾向自动付款
    auto = (contract != "Month-to-month")
    swap = auto & (rng.random(N_CUSTOMERS) < 0.55)
    base = np.where(
        swap & (base == "Electronic check"),
        rng.choice(["Bank transfer (automatic)", "Credit card (automatic)"], N_CUSTOMERS),
        base,
    )
    return base


def _gen_monthly(internet, contract, sec, backup, protect, support, stv, smovie):
    base = np.where(internet == "Fiber optic", 70.0, np.where(internet == "DSL", 45.0, 20.0))
    base = base + (sec == "Yes") * 3.5 + (backup == "Yes") * 3.2 + (protect == "Yes") * 3.0
    base = base + (support == "Yes") * 4.0 + (stv == "Yes") * 8.5 + (smovie == "Yes") * 8.5
    base = base + np.where(contract == "Month-to-month", 4.0, np.where(contract == "One year", -2.0, -5.0))
    base = base + rng.normal(0, 3.5, N_CUSTOMERS)
    return np.clip(base, 18.0, 120.0)


def _churn_logits(tenure, monthly, contract, internet, payment, senior, support, sec):
    z = -0.6
    z = z - tenure / 18.0
    z = z + (monthly - 60) / 25.0
    z = z + np.where(contract == "Month-to-month", 1.4, np.where(contract == "One year", -0.3, -1.2))
    z = z + np.where(internet == "Fiber optic", 0.7, np.where(internet == "DSL", -0.1, -0.6))
    z = z + np.where(payment == "Electronic check", 0.8, -0.2)
    z = z + senior * 0.3
    z = z + np.where(support == "Yes", -0.5, 0.2)
    z = z + np.where(sec == "Yes", -0.4, 0.1)
    return 1 / (1 + np.exp(-z))


def _build_campaigns(customers):
    """生成营销活动效果数据，用于营销 ROI 与归因分析。"""
    campaigns = []
    names = [
        ("新用户首充立减", "折扣", "应用商店"),
        ("老用户带宽免费升级", "增值服务", "官网"),
        ("合约续约送礼", "折扣", "电话外呼"),
        ("家庭套餐拼团", "套餐", "线下门店"),
        ("流失挽回专享券", "挽回", "短信"),
        ("会员日流量包", "增值服务", "官网"),
        ("推荐有礼双倍返", "裂变", "转介绍"),
        ("节日特惠季卡", "折扣", "应用商店"),
    ]
    cid = 1
    for cname, ctype, channel in names:
        audience = rng.integers(800, 2600)
        reach = int(audience * rng.uniform(0.55, 0.92))
        # 不同类型活动转化率差异
        base_cv = {"折扣": 0.14, "增值服务": 0.09, "套餐": 0.11, "挽回": 0.22,
                   "裂变": 0.06, "短信": 0.07}.get(ctype, 0.10)
        convert = int(reach * rng.uniform(base_cv * 0.7, base_cv * 1.4))
        cost_per = round(rng.uniform(8, 60), 2)
        cost = round(reach * cost_per * 0.3 + convert * cost_per, 2)
        revenue = round(convert * rng.uniform(120, 480), 2)
        campaigns.append(
            {
                "campaignId": f"CMP-2026-{cid:03d}",
                "campaignName": cname,
                "campaignType": ctype,
                "channel": channel,
                "audienceSize": int(audience),
                "reachCount": reach,
                "convertCount": convert,
                "conversionRate": round(convert / reach, 4),
                "cost": cost,
                "revenue": revenue,
                "roi": round((revenue - cost) / cost, 3) if cost > 0 else 0,
            }
        )
        cid += 1
    return pd.DataFrame(campaigns)


def generate_all():
    customers = _build_customers()
    campaigns = _build_campaigns(customers)
    return customers, campaigns


if __name__ == "__main__":
    c, camp = generate_all()
    out = "data"
    import os
    os.makedirs(out, exist_ok=True)
    c.to_csv(f"{out}/customers.csv", index=False)
    camp.to_csv(f"{out}/campaigns.csv", index=False)
    print(f"客户数据 {len(c)} 条，流失率 {round((c.Churn=='Yes').mean()*100,1)}%")
    print(f"营销活动 {len(camp)} 条，平均 ROI {round(camp.roi.mean(),2)}")
