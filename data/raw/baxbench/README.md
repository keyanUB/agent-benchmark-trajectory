# Local BaxBench Data

This directory is for local BaxBench assets used to generate and evaluate new
agent trajectories.

Current layout:

```text
dataset/      # Hugging Face task-spec dataset
evaluator/    # BaxBench evaluator/codebase checkout or archive
runs/         # generated solutions and evaluation outputs
agent_logs/   # normalized or raw agent step logs
```

Downloaded task dataset:

- Source: `https://huggingface.co/datasets/LogicStar/BaxBench`
- Local file: `dataset/test-00000-of-00001.parquet`
- Split: `test`
- Rows: 392

The evaluator/tests are published separately at:

```text
https://github.com/logic-star-ai/baxbench
```

