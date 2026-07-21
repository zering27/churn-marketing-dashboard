# 客户流失与营销分析仪表盘

> 基于电信客户数据，融合流失预测、生存分析、客户分群、营销 ROI 归因、LTV 估算、挽留模拟的一站式分析仪表盘。

**零依赖单文件版**：`dist/` 目录下的 HTML 文件双击即可打开，无需安装任何环境。

**开发者版**：Flask 后端 + ECharts 前端，支持实时数据生成与模型训练。

## 功能亮点

### 流失预测
- 随机森林（300 棵树，class_weight 平衡）训练流失二分类模型，AUC 0.925
- 输出 AUC、准确率、精确率、召回率、F1 五项指标
- 特征重要性排序（Gini 重要性）
- 客户流失风险评分与三级风险分层（低 / 中 / 高）

### 生存分析
- 手写 Kaplan-Meier 估计器（无 lifelines 依赖）
- 整体生存曲线 + 按合同类型分组切换
- 各 tenure 段流失风险曲线

### 客户分群
- RFM 简化特征（tenure / 月费 / 总消费）+ KMeans 聚类
- 四类客户：高价值忠诚、中等潜力、稳定低消、新客待培育
- 散点图 + 雷达图多维度对比

### 营销效果
- 8 类营销活动 ROI / 转化率 / 收入三指标可切换
- 获客渠道质量对比（LTV、获客成本、流失率）
- 营销漏斗（触达 → 转化 → 等效订单）
- 活动类型投入产出聚合

### LTV 与挽留模拟
- 客户生命周期价值 = 月费 × 预期留存月数 × 0.85 − 获客成本
- LTV 分布与分群对比
- 挽留模拟器：拖动滑块调整单人挽留投入，实时计算净收益

## 两种使用方式

### 方式一：直接打开（推荐体验）

`dist/` 目录下的单文件 HTML 已内联全部资源（ECharts 库 + 预计算数据 + 交互逻辑），双击即可在浏览器打开，所有图表和交互均可正常使用。

### 方式二：本地运行（推荐开发）

```bash
git clone https://github.com/zering27/churn-marketing-dashboard.git
cd churn-marketing-dashboard
pip install -r requirements.txt
python app.py
```

浏览器打开 `http://127.0.0.1:5050`

### 构建单文件版本

如需从源码重新构建单文件 HTML：

```bash
python build_static.py    # 生成预计算数据
python inline_html.py     # 内联到单个 HTML
```

## 交互说明

- **维度筛选**：流失率图表可切换 13 个分析维度（合同、上网方式、付费方式、获客渠道、分群等）
- **图表切换**：柱状 / 饼图一键切换；生存曲线整体 / 分组切换；营销指标 ROI / 转化率 / 收入切换
- **挽留模拟**：拖动滑块调整单人挽留预算，高风险客户名单与净收益实时刷新

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Flask、pandas、scikit-learn |
| 可视化 | ECharts 5.5（16 个交互图表） |
| 数据 | 内置合成数据生成器（7043 客户，基于 IBM Telco 分布） |

## 项目结构

```
churn-marketing-dashboard/
├── app.py                # Flask 后端 + 12 个 API
├── analysis.py           # 分析核心：预测、生存、分群、LTV、挽留
├── data_generator.py     # 合成数据生成器（客户 + 营销活动）
├── build_static.py       # 构建静态数据脚本
├── inline_html.py        # 单文件内联脚本
├── requirements.txt
├── LICENSE
├── dist/                 # 预构建的单文件版本（双击即用）
│   └── 客户流失与营销分析仪表盘.html
├── templates/
│   └── index.html        # 仪表盘页面
└── static/
    ├── css/style.css     # 暗色主题样式
    └── js/dashboard.js   # ECharts 交互逻辑
```

## 数据说明

数据由 `data_generator.py` 基于真实电信客户流失数据集的特征分布合成生成，包含合理的特征相关性与流失逻辑：

- 月付合同流失率约 50%，两年合同仅 4%
- 光纤用户流失率高于 DSL 和无网络用户
- 电子支票付费方式流失率最高
- tenure 越长流失率越低

固定随机种子（20260721），每次生成结果一致。

## License

[MIT](LICENSE)
