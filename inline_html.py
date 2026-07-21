"""
把 echarts.min.js、data.js、charts.js 全部内联到单个 HTML 文件中。
运行前需先执行 build_static.py 生成 data.js，并确保有 HTML 模板。
"""
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 尝试找到 HTML 模板：优先用 static-report 目录下的，否则用项目根目录
HTML_IN = os.path.join(BASE_DIR, "dist", "churn-marking-dashboard.html")
if not os.path.exists(HTML_IN):
    HTML_IN = os.path.join(BASE_DIR, "churn-marking-dashboard.html")
if not os.path.exists(HTML_IN):
    print("错误：找不到 HTML 模板文件")
    sys.exit(1)

HTML_OUT = os.path.join(BASE_DIR, "dist", "客户流失与营销分析仪表盘.html")

with open(HTML_IN, "r", encoding="utf-8") as f:
    html = f.read()

def read_js(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

# 查找 JS 文件
echarts_path = os.path.join(BASE_DIR, "_shared", "js", "echarts.min.js")
data_path = os.path.join(BASE_DIR, "dist", "data.js")
charts_path = os.path.join(BASE_DIR, "dist", "charts.js")

# 兼容不同目录结构
if not os.path.exists(echarts_path):
    echarts_path = os.path.join(BASE_DIR, "assets", "js", "echarts.min.js")
if not os.path.exists(data_path):
    data_path = os.path.join(BASE_DIR, "assets", "data.js")
if not os.path.exists(charts_path):
    charts_path = os.path.join(BASE_DIR, "assets", "charts.js")

for name, path in [("echarts", echarts_path), ("data", data_path), ("charts", charts_path)]:
    if not os.path.exists(path):
        print(f"错误：找不到 {name} 文件: {path}")
        sys.exit(1)

echarts_js = read_js(echarts_path)
data_js = read_js(data_path)
charts_js = read_js(charts_path)

# 替换外部引用为内联
replacements = [
    ('<script src="./_shared/js/echarts.min.js"></script>', f'<script>\n{echarts_js}\n</script>'),
    ('<script src="./assets/js/echarts.min.js"></script>', f'<script>\n{echarts_js}\n</script>'),
    ('<script src="./assets/data.js"></script>', f'<script>\n{data_js}\n</script>'),
    ('<script src="./dist/data.js"></script>', f'<script>\n{data_js}\n</script>'),
    ('<script src="./assets/charts.js"></script>', f'<script>\n{charts_js}\n</script>'),
    ('<script src="./dist/charts.js"></script>', f'<script>\n{charts_js}\n</script>'),
]

for old, new in replacements:
    html = html.replace(old, new)

remaining = re.findall(r'<script\s+src=', html)
if remaining:
    print(f"警告：仍有 {len(remaining)} 个外部 script 引用未替换")
else:
    print("所有 JS 已内联，无外部依赖")

os.makedirs(os.path.dirname(HTML_OUT), exist_ok=True)
with open(HTML_OUT, "w", encoding="utf-8") as f:
    f.write(html)

size_kb = os.path.getsize(HTML_OUT) / 1024
print(f"单文件已生成: {HTML_OUT}")
print(f"文件大小: {size_kb:.0f} KB ({size_kb/1024:.1f} MB)")
