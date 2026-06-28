# concrete_floor_design

《水工钢筋混凝土课程设计：整体式单向板肋形楼盖设计与辅助计算程序开发》矩阵刚度法 Streamlit 平台。

本程序用于辅助完成板、次梁、主梁的荷载计算、内力计算、配筋计算、构造校核、图形展示和半自动计算书导出。程序结果不能替代课程设计手算、教材系数表和教师要求的人工复核。

## 功能清单

- 首页 / 项目说明：展示计算流程图和答辩演示路线。
- 基本参数输入：统一输入楼盖尺寸、结构布置、材料、荷载、截面尺寸，保存到 `st.session_state`。
- 结构布置与截面尺寸初估：板厚、次梁、主梁截面经验范围和合理性判断。
- 板、次梁、主梁均采用 Euler-Bernoulli 梁单元矩阵刚度法。
- 支持最多 8 跨、逐跨跨度、节点支承、E、毛截面惯性矩、刚度折减系数、手动活载跨和主梁集中力位置。
- 板支座反力传给次梁，次梁支座反力按实际位置作为主梁集中力。
- 荷载自动传递总览：展示 `kN/m2 → kN/m → kN` 的传递公式和单位说明。
- 最不利内力与包络图：枚举逐跨活载组合，每个工况重新组装刚度方程。
- 逐控制截面配筋：支座边缘、跨中、真实极值点及集中力两侧分别设计。
- 控制截面示意图：编号与内力表、配筋表一致，可导出 PNG。
- 抵抗弯矩图：估算 `Mu` 并与设计弯矩图叠加。
- 智能校核与错误提示：分错误、警告、提示三级显示。
- 结果导出：支持 Excel、Word、Markdown 和各类 PNG 图片导出。
- 测试算例与手算对比：保留课程设计示例数据和误差说明。
- 程序说明与已知不足：集中说明公式、适用范围和需人工复核内容。

## 项目结构

```text
单向板肋形楼盖计算程序/
├── app.py
├── calculations/
│   ├── common.py
│   ├── loads.py
│   ├── section_estimation.py
│   ├── slab.py
│   ├── secondary_beam.py
│   ├── main_beam.py
│   ├── rebar.py
│   ├── internal_force.py
│   ├── matrix_stiffness.py
│   ├── structural_models.py
│   ├── load_cases.py
│   ├── control_sections.py
│   ├── force_envelope.py
│   ├── section_design.py
│   ├── project_analysis.py
│   ├── envelope.py
│   ├── moment_capacity.py
│   └── checks.py
├── charts/
│   ├── plot_moment.py
│   ├── plot_shear.py
│   ├── plot_control_sections.py
│   ├── plot_force_envelope.py
│   └── plot_resisting_moment.py
├── export/
│   ├── export_excel.py
│   ├── export_word.py
│   └── export_report.py
├── docs/
│   ├── 程序说明书.md
│   ├── 测试算例与手算对比.md
│   ├── 公式与适用范围.md
│   └── 已知不足与后续改进.md
├── tests/
├── requirements.txt
├── .gitignore
├── run_mac.command
├── install_mac.command
├── run_win.bat
└── install_win.bat
```

## 安装依赖

Windows 第一次使用双击 `install_win.bat`，之后双击 `run_win.bat`。

macOS 第一次使用双击 `install_mac.command`，之后双击 `run_mac.command`。

macOS：

```bash
python3 -m pip install -r requirements.txt
```

Windows：

```bat
python -m pip install -r requirements.txt
```

也可以直接双击 `install_mac.command` 或 `install_win.bat`。

## 启动方法

macOS：

```bash
python3 -m streamlit run app.py
```

或双击 `run_mac.command`。

Windows：

```bat
python -m streamlit run app.py
```

或双击 `run_win.bat`。

启动后访问：

```text
http://localhost:8501
```



## 使用流程

1. 进入“基本参数输入”，检查楼盖尺寸、材料强度、荷载和截面尺寸。
2. 查看“结构布置与截面尺寸初估”，确认板厚、次梁、主梁截面是否合理。
3. 依次查看“板计算模块”“次梁计算模块”“主梁计算模块”。
4. 用“荷载自动传递总览”说明板到次梁、次梁到主梁的荷载来源。
5. 查看“最不利内力与包络图模块”和“抵抗弯矩图模块”作为答辩加分展示。
6. 查看“智能校核与错误提示”，修正错误并记录需人工复核内容。
7. 在“结果导出与半自动计算书”导出 Excel、Word 或 Markdown。
8. 各图形页面可单独导出 PNG。

## 测试方法

```bash
python -m pytest tests
```

测试覆盖课程设计示例荷载、矩阵组装、简支/固端基准、集中力剪力跃变、多跨对称性、总体平衡、活载包络、逐截面配筋、图形编号和计算书导出。

部署前建议本地自测：

```bash
streamlit run app.py
python -m pytest tests
```

确认首页可以打开，板、次梁、主梁基础计算页正常显示，Excel、Word、Markdown 和 PNG 导出按钮可以生成下载文件。

## 常见问题

- 页面报错“参数暂不能完成计算”：通常是有效高度大于构件高度、梁高小于板厚、跨度为 0 或材料强度为 0。
- Word 导出失败：当前 Word 导出使用标准库生成 `.docx`，不依赖本地 Word/WPS 软件；若下载失败，请先确认依赖安装和页面计算是否正常。
- Excel 导出失败：请先安装依赖，确认 `openpyxl` 已安装。
- 图片中文字体显示异常：不同电脑字体不同，不影响数值；可安装中文字体或在系统中启用常用中文字体。
- PDF 导出：当前支持 Word/Excel/PNG 导出，PDF 可由 Word 另存为 PDF。

## 分析边界和人工复核

正式内力来自矩阵刚度法；旧经验系数模块仅保留作手算参考，不参与正式设计链路。斜截面箍筋估算、最小配筋默认值、纵筋截断和锚固仍需按采用规范人工复核。

当前版本按同一全局工况逐级完成板支承线 → 次梁 → 主梁交点传力，板反力会除以板带宽度后再传给次梁。支座中心与真实支座边缘分别进入控制表；次梁采用 30m 方向图，主梁采用 18m 方向图。正式逐线映射目前只支持规则等跨楼盖，不规则布置会明确报错。梁配筋和抗剪中的课程近似参数集中在 `calculations/specification_parameters.py`，所有未完成规范逐条确认的结果均提示人工复核。
