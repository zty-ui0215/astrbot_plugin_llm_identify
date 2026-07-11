# 社区可信参考库 Submodule

插件通过 Git Submodule 固定社区共建仓库：

- 仓库：`https://github.com/zty-ui0215/astrbot_llm_identify_trusted_references`
- 插件内路径：`llm_identify/data/trusted_references`
- 运行时数据路径：`llm_identify/data/trusted_references/data/accepted`

## 首次获取

推荐在克隆插件时同时初始化 Submodule：

```bash
git clone --recurse-submodules <plugin-repository-url>
```

已经克隆插件但目录为空时，执行：

```bash
git submodule update --init --recursive
```

## 更新社区库

```bash
git submodule update --remote llm_identify/data/trusted_references
```

更新后，主仓库会显示 Submodule gitlink 发生变化。审核新数据后，需要在主仓库提交新的 gitlink，插件发布版本才会固定到该社区库版本。

## 加载规则

插件默认先加载内置 `trusted_reference_corpus.json`，再加载社区 Submodule 中的 `data/accepted/**/*.json`。

- `data/candidates/` 永远不会进入检测数据库。
- `accepted/` 支持标准 corpus row、完整 corpus 文档和审核后保留候选包结构的 JSON。
- 社区记录在加载前仍会经过插件的可信语料校验。
- Submodule 未初始化、目录缺失或数据不合法时，社区源会跳过或降级，内置数据库继续可用。
- 插件运行时不自动执行 `git pull`，因此不会产生静默联网或未经审核的数据更新。

## 发布检查

发布插件前执行：

```bash
git submodule status
python -m unittest tests.test_trusted_corpus tests.test_corpus_validation_review
```

打包工具必须包含已检出的 Submodule 内容；只下载主仓库源码但不初始化 Submodule 时，插件将仅使用内置可信参考库。
