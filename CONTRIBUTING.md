# Contributing

Reproducible bug reports, capture-quality examples, documentation improvements, and focused pull requests are welcome. Start with the [English usage guide](docs/USAGE.en.md), [validation summary](docs/VALIDATION.en.md), [architecture notes (中文)](docs/ARCHITECTURE.md), and [attribution boundaries](docs/REFERENCES.md).

## Development setup

```bash
python -m venv .venv
# Activate the virtual environment for your operating system, then:
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build
```

Changes to a backend or to OpenCV/PyCOLMAP parameters need tests that actually call the affected implementation, not only mocked return values. Optional PyCOLMAP checks run with `python -m pytest -m optional`; missing dependencies are explicitly skipped. Full browser acceptance requires Playwright and Chromium; see the validation documentation.

## Review checklist

Explain the problem, solution, executed checks, and known limits. Preserve pose conventions, bidirectional export tracks, and read-only source inputs. Do not silently change calibration units, output types, or success/failure definitions. Describe new heuristic thresholds as diagnostics, not success probabilities. New exporters need format checks or an independent reader test.

Document algorithm and data sources. Contributions must be authorized and compatible with the project's MIT license; third-party components retain their licenses. Never remove upstream copyright by renaming code. Update `docs/REFERENCES.md`, `docs/references.bib`, and `THIRD_PARTY_NOTICES.md` as applicable.

Keep private photos, access tokens, local databases, large videos, and datasets without explicit redistribution permission out of commits. Prefer the deterministic synthetic fixtures in `demo.py`. Real-world benchmarks need a separate download step with source, version, terms, and checksums. Screenshots must identify actual implemented behavior rather than present a design mockup as a running result.

Prefer readability and verifiability over line count. Explain new dependencies, installation requirements, licenses, and necessity. Preserve the default CPU path without model-weight downloads. Performance claims need hardware, datasets, repeated trials, and complete timing boundaries; one synthetic scene does not establish general superiority.

## 中文说明

欢迎可复现问题、许可明确的采集案例和小范围改进。请保留位姿约定、轨迹一致性、只读输入和明确的输出边界；新增后端必须有实际调用测试。提交前执行测试与构建，说明跳过项。代码、算法、图片与数据均需授权和出处，不能删除上游版权。不要提交用户照片、令牌、数据库或未获再分发授权的数据集。详见 [架构](docs/ARCHITECTURE.md)、[验证记录](docs/VALIDATION.md) 与 [引用说明](docs/REFERENCES.md)。
