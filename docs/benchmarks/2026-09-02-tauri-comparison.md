# BatchRename 2.0 Rust/Tauri 性能对比

测试环境与 Python 基线相同：Windows 11、同一工作区、Node.js 24.19.0、Rust 1.98.0 stable-msvc。数据为单层空文件，名称均匹配普通文本规则；计时不含生成测试文件，Rust 为开发构建。

| 项目数 | Python 扫描 | Rust 扫描 | Python 预览 | Rust 预览 |
| ---: | ---: | ---: | ---: | ---: |
| 1,000 | 15.028 ms | 5.108 ms | 13.331 ms | 11.913 ms |
| 10,000 | 71.869 ms | 33.876 ms | 152.991 ms | 118.815 ms |

执行 `tests/performance/run-benchmarks.ps1` 可复跑 Rust 场景。发布门禁不仅关注速度：扫描支持取消，前端仅读取首批 100 条，完整候选保留在后端；任何性能优化都不得绕过冲突检查、逐项写档或撤回预检。
