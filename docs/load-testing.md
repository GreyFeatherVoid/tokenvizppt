# tokenvizPPT 压测说明

更新时间：2026-05-16

项目内置了一个轻量压测脚本：

```bash
python scripts/load_test.py --help
```

建议使用项目 Conda 环境运行：

```bash
conda activate tokenvizppt
python scripts/load_test.py --base-url https://ppt.forgespark.org --mode health --concurrency 50 --requests 1000
```

## 模式说明

### health

只请求 `/api/health`，用于测入口层吞吐，不调用大模型。

```bash
python scripts/load_test.py \
  --base-url https://ppt.forgespark.org \
  --mode health \
  --concurrency 50 \
  --requests 1000
```

### session

每个 flow 会执行：

1. 创建项目。
2. 读取项目详情。
3. 读取项目列表。
4. 删除项目。

它用于测试 API、PostgreSQL 和本地文件写入链路，不调用大模型。

```bash
python scripts/load_test.py \
  --base-url https://ppt.forgespark.org \
  --mode session \
  --concurrency 20 \
  --requests 200 \
  --page-count 1
```

### generation

会创建项目并启动真实 PPT 生成任务，会真实调用大模型，也会触发积分或匿名额度逻辑。为了避免误操作，必须显式添加 `--unsafe-real-generation`。

只测试入队速度，不等待生成完成：

```bash
python scripts/load_test.py \
  --base-url https://ppt.forgespark.org \
  --mode generation \
  --concurrency 2 \
  --requests 4 \
  --page-count 1 \
  --unsafe-real-generation
```

等待每个生成任务完成：

```bash
python scripts/load_test.py \
  --base-url https://ppt.forgespark.org \
  --mode generation \
  --concurrency 2 \
  --requests 4 \
  --page-count 1 \
  --unsafe-real-generation \
  --poll-generation \
  --poll-timeout 900
```

如果开启了登录和积分，建议使用带足够积分的测试账号 Cookie：

```bash
python scripts/load_test.py \
  --base-url https://ppt.forgespark.org \
  --mode generation \
  --concurrency 2 \
  --requests 4 \
  --page-count 1 \
  --cookie 'tokenvizppt_session=YOUR_SESSION_COOKIE' \
  --unsafe-real-generation \
  --poll-generation
```

## 本次初步结果

2026-05-16 已完成以下压测。

### 不调用大模型

| 入口 | 模式 | 并发 | 请求数 | 成功率 | 吞吐 | p95 延迟 |
| --- | --- | --- | --- | --- | --- | --- |
| `http://127.0.0.1:6001` | health | 20 | 200 | 100% | 398.69 req/s | 0.106s |
| `http://127.0.0.1:6001` | health | 50 | 1000 | 100% | 145.08 req/s | 1.039s |
| `https://ppt.forgespark.org` | health | 50 | 1000 | 100% | 136.21 req/s | 1.036s |
| `http://127.0.0.1:6001` | session | 10 | 100 | 100% | 15.70 flow/s | 3.498s |
| `http://127.0.0.1:6001` | session | 20 | 200 | 100% | 26.71 flow/s | 0.895s |
| `https://ppt.forgespark.org` | session | 20 | 200 | 100% | 28.93 flow/s | 0.812s |
| `http://127.0.0.1:6001` | session | 50 | 500 | 100% | 27.44 flow/s | 3.054s |

### 真实 PPT 生成

使用登录态 Cookie，关闭 AI 生图，每个任务生成 1 页 PPT，并等待任务完成：

| 入口 | 模式 | 并发 | 任务数 | 页数/任务 | 成功率 | 总耗时 | 平均耗时 | p95 耗时 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `https://ppt.forgespark.org` | generation | 2 | 4 | 1 | 100% | 119.19s | 56.559s | 62.743s |
| `https://ppt.forgespark.org` | generation | 4 | 8 | 1 | 100% | 253.76s | 96.463s | 130.624s |
| `https://ppt.forgespark.org` | generation | 8 | 16 | 1 | 100% | 453.02s | 174.244s | 243.418s |
| `https://ppt.forgespark.org` | generation, worker concurrency 8 | 8 | 16 | 1 | 100% | 197.88s | 78.040s | 144.955s |

结论：

- 轻请求和普通项目 CRUD 不是当前主要瓶颈。
- 当前真实生成在 8 并发、16 个 1 页任务下全部成功。
- 将 Celery worker 从默认 2 个子进程调到 `--concurrency=8` 后，同样的 8 并发 16 任务总耗时从 453.02s 降到 197.88s，平均耗时从 174.244s 降到 78.040s，p95 从 243.418s 降到 144.955s。
- 对外推广初期，可以允许多个用户排队；当前 8 个运行中生成任务是可行的，但仍然必须展示排队/生成状态。
- 后续还需要测试 3 页、5 页和导出任务，因为它们比 1 页任务更接近真实使用。
