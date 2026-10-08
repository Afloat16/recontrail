<div align="center">

# ReconTrail

### 先检查照片，再重建三维，把结果与依据一起交付。

**本地优先、CPU 可用的摄影测量工作台：照片质检、稀疏三维重建、标定双目与离线交互报告。**

[![Tests and package](https://github.com/Afloat16/recontrail/actions/workflows/ci.yml/badge.svg)](https://github.com/Afloat16/recontrail/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e.svg)](LICENSE)

[English](README.md) · **简体中文**

[快速开始](#快速开始) · [体验示例](#没有照片也能先体验) · [使用指南](docs/USAGE.md) · [验证记录](docs/VALIDATION.md) · [贡献指南](CONTRIBUTING.md)

</div>

---

## 为什么做 ReconTrail？

三维重建不应该只留下一个难以判断好坏的模型。你还需要知道照片是否可用、哪些相机成功注册、错误可能来自哪里，以及怎样把结果交给他人审阅。

ReconTrail 将这些步骤连成一条简单流程：

```text
照片或视频 → 采集质量检查 → 稀疏重建 → 检查与导出
已标定双目照片 ──────────→ 稠密可见表面 → 检查与导出
```

**先看输入，再投入计算。** 检查清晰度、曝光、纹理、完全重复照片和几何连通性。对质量问题给出提示，而不是随意删掉可能有用的视角。

**普通 CPU 即可起步。** 默认流程不需要显卡、账号、云端服务或模型权重。首次安装依赖需要网络；照片处理在本地执行。

**结果可检查，也便于交付。** 输出点云、相机、诊断、参数、输入指纹及自包含 HTML 报告，离线打开即可查看，不要求收件人安装重建工具链。

本项目适合小规模采集实验、多视图几何教学、正式重建前的照片检查与初步几何结果分享。它补充现有重建工具，并不替代完整摄影测量套件或专业测绘软件。

## 已支持的工作流

| 工作流 | 输入 | 输出 | 明确边界 |
|---|---|---|---|
| **照片检查** | 同一静态场景的重叠照片 | 每图诊断与几何连通性报告 | 启发式诊断，不是成功概率 |
| **照片重建** | 多视角照片；可选标定内参 | 彩色稀疏 PLY、相机、COLMAP 文本、离线报告 | 任意尺度的稀疏几何，**不是稠密网格** |
| **标定双目** | 左右图像和可靠标定 | 稠密彩色点、开放表面 PLY 与 OBJ | 尺度来自基线；不补洞、不生成 UV 图集 |
| **视频准备** | 本地视频 | 各时间窗口内较清晰的帧 | 抽帧不保证视角有效 |
| **可选 COLMAP 后端** | 多视角照片 | 统一诊断与交付格式 | 可选 PyCOLMAP 4.2.x；见验证边界 |

网页工作台提供照片检查与稀疏重建；标定双目和视频抽帧通过命令行使用。当前网页和报告包含中英文标签。


## 快速开始

需要 **Python 3.10+**，建议使用独立虚拟环境。

```bash
git clone https://github.com/Afloat16/recontrail.git
cd recontrail
python -m venv .venv
```

Linux/macOS 激活环境：

```bash
source .venv/bin/activate
```

Windows PowerShell 激活环境：

```powershell
.venv\Scripts\Activate.ps1
```

然后安装并启动：

```bash
python -m pip install .
python -m recontrail serve
```

使用终端输出的**完整本地链接**打开工作台，选择同一静态场景的重叠照片，开始处理，完成后保存离线报告和 PLY。不要分享链接中的访问令牌。

以上命令从仓库安装，不假定已发布 PyPI 包。`start.sh` 和 `start.bat` 提供便捷启动方式；目标平台验证与安装包验证范围见验证记录。

### 没有照片也能先体验

```bash
python -m recontrail demo -o ../recontrail-demo --run
```

打开 `../recontrail-demo/result/report.html`。示例会生成原创多深度纹理场景，真实执行匹配、相机估计、三角化与优化。真值位姿仅用于测试核对，**不输入重建流程**。

## 常用命令

```bash
# 检查照片和连通性
python -m recontrail check ./photos -o ../capture-check

# 默认 CPU 稀疏重建
python -m recontrail run ./photos -o ../capture-result

# 使用共享相机标定
python -m recontrail run ./photos -o ../calibrated-result --intrinsics camera.json

# 输入、配置与完成产物均验证一致时复用
python -m recontrail run ./photos -o ../calibrated-result --intrinsics camera.json --resume

# 视频抽帧后按序列重建
python -m recontrail video ./capture.mp4 -o ../sampled --interval 0.75
python -m recontrail run ../sampled/images -o ../video-result --pairing sequence

# 有可靠标定的稠密双目
python -m recontrail stereo left.png right.png --calibration stereo.json -o ../stereo-result --max-depth 15

# 检查环境与可选后端
python -m recontrail doctor
```

输入、输出目录必须分离，不能互相包含。`check` 与 `run` 使用不同输出目录。`--resume` 表示经校验的完成结果复用或相同配置重试，不是中间优化状态断点续算。

相机与双目标定格式、拍摄建议、可选后端说明见 [使用指南](docs/USAGE.md) 和 [`examples/`](examples/)。

## 输出内容

```text
result/
├── report.html          # 自包含交互报告，无 CDN
├── cloud.ply            # 最终保留的全部点；双目可含面
├── cameras.json         # 相机变换与中心
├── metrics.json         # 注册、误差、尺度与优化状态
├── audit.json           # 采集诊断与匹配图
├── provenance.json      # 配置、标定、依赖版本与输入哈希
├── complete.json        # 完成产物 SHA-256 清单
├── sparse/0/*.txt       # 照片模式：COLMAP 文本模型
├── images/*.png         # 照片模式：标准化的注册图像
├── image_mapping.json   # 照片模式：标准名称与源名称对应关系
└── mesh.obj             # 双目模式：带顶点色的开放表面
```

报告最多预览 14,000 点，PLY 保留全部**最终点**。lite 后端默认最终优化预算为 2,500 个长轨迹点；优化被接受后保留该子集并再次过滤，可用 `--ba-points` 调整。它们不代表保留了全部初始候选点。

照片位姿约定为 `X_camera = R @ X_world + t`。COLMAP 导出遵循 [官方文本格式](https://colmap.github.io/format.html)；轨迹双向一致性已在项目内测试，独立 PyCOLMAP 导入属于可选测试。

## 验证与适用边界

已记录的本地 CPU 验证为 **57 项通过、2 项可选 PyCOLMAP 测试跳过**；上传前复跑得到相同统计。首页 CI 徽章链接实际工作流状态，不使用写死的通过标记。

| 已记录的合成示例 | 结果 |
|---|---:|
| 注册照片 | 8 / 8 |
| 最终稀疏点 | 1,199 |
| 中位重投影误差 | 0.174 像素 |
| 95 分位重投影误差 | 0.498 像素 |
| 双目彩色点 | 53,735 |
| 双目三角面 | 104,790 |

这些数据来自自建合成场景，**不是真实世界精度基准**。低重投影误差不意味着物体尺寸准确。执行环境、独立真值核对、HTTP/工作进程测试、浏览器覆盖和待验证项目详见 [验证记录](docs/VALIDATION.md)。

lite 使用固定内参，只处理一个连通模型；焦距估算仅方便预览，不是相机自标定。反光透明、弱纹理、重复图案、运动、纯旋转、滚动快门和视差不足都可能导致失败。本版不支持鱼眼、多片段自动对齐、地理配准、封闭网格或 UV 贴图。双目需要零斜切针孔标定，校正后的视差方向应主要为水平。

## 隐私与安全

工作台为**单用户、仅本机监听**服务，提供能力令牌、Host/Origin 检查、上传限制、明确的产物下载白名单和单个可取消工作进程。输入指纹、项目锁与输出校验避免静默复用错误结果或覆盖其他项目。

不要将服务暴露到互联网。原生图像与视频解码器未沙箱化，请使用可信采集文件并更新依赖。报告与导出可能包含场景几何和源文件名，分享前请检查。详见 [SECURITY.md](SECURITY.md)。

## 开发与贡献

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build

# 可选后端和独立 COLMAP 读取测试
python -m pip install -e ".[colmap]"
python -m pytest -q -m optional
```

可从 [架构](docs/ARCHITECTURE.md)、[路线图](docs/ROADMAP.md)、[贡献指南](CONTRIBUTING.md) 与 [Issues](https://github.com/Afloat16/recontrail/issues) 开始。欢迎可复现失败案例、许可明确的真实测试照片、文档改进与平台验证。

## 许可与引用

ReconTrail 原创源码采用 [MIT](LICENSE) 许可。OpenCV、NumPy、SciPy、Pillow、filelock 与可选 PyCOLMAP 保持各自许可。标准方法归功于原作者；未捆绑调研项目源码实现或模型权重。

详见 [第三方声明](THIRD_PARTY_NOTICES.md)、[参考来源及对应模块](docs/REFERENCES.md)、[BibTeX](docs/references.bib) 与 [`CITATION.cff`](CITATION.cff)。[调研记录](docs/RESEARCH.md) 说明与 COLMAP、Meshroom、Open3D、OpenMVG、OpenMVS、WebODM、Nerfstudio、VGGT 和 DUSt3R 的比较与取舍。

---

**这个流程对你有帮助？** 欢迎 Star 收藏仓库，运行内置示例，并在 Issue 中分享可复现结果或失败案例。
