# concrete_floor_design

《水工钢筋混凝土课程设计：整体式单向板肋形楼盖设计与辅助计算程序开发》 Streamlit 平台。

本程序用于辅助完成板、次梁、主梁的荷载计算、内力计算、配筋计算、构造校核、图形展示和半自动计算书导出。

## 功能清单

- 首页 / 项目说明：展示计算流程图和答辩演示路线。
- 基本参数输入：统一输入楼盖尺寸、结构布置、材料、荷载、截面尺寸，保存到 `st.session_state`。
- 结构布置与截面尺寸初估：板厚、次梁、主梁截面经验范围和合理性判断。
- 板计算模块：恒载、活载、设计荷载、控制弯矩、所需钢筋面积和板筋推荐。
- 次梁计算模块：自动接收板荷载，计算线荷载、自重、粉刷、弯矩、剪力、纵筋和箍筋。
- 主梁计算模块：自动接收次梁荷载，计算集中荷载、自重、粉刷、弯矩、剪力、纵筋和箍筋。
- 荷载自动传递总览：展示 `kN/m2 → kN/m → kN` 的传递公式和单位说明。
- 最不利内力与包络图：支持全跨、奇数跨、偶数跨、单跨、相邻跨活载的简化包络。
- 配筋方案推荐与超配率提示：输出是否满足、超配率和“偏保守”提示。
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
│   ├── envelope.py
│   ├── moment_capacity.py
│   └── checks.py
├── charts/
│   ├── plot_moment.py
│   ├── plot_shear.py
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

测试覆盖课程设计示例荷载、板/次梁/主梁计算、荷载传递、截面初估、包络、抵抗弯矩和计算书文本导出。

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

## 简化方法和人工复核

本程序中的内力包络、斜截面箍筋估算、抵抗弯矩图、纵筋截断和锚固位置均为课程设计辅助方法。最终计算书应按教材、规范和教师要求人工复核。
