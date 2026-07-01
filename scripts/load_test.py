#!/usr/bin/env python3
"""Small async load tester for tokenvizPPT.

Default modes avoid LLM calls. The generation mode is intentionally gated behind
--unsafe-real-generation because it starts real backend generation jobs.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import statistics
import sys
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class Sample:
    ok: bool
    elapsed: float
    status: str
    detail: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run tokenvizPPT load tests.")
    parser.add_argument("--base-url", default="http://127.0.0.1:6001")
    parser.add_argument(
        "--mode",
        choices=["health", "session", "generation"],
        default="health",
        help="health and session do not call the LLM. generation starts real jobs.",
    )
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--page-count", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--poll-timeout", type=float, default=600)
    parser.add_argument("--poll-interval", type=float, default=2)
    parser.add_argument("--cookie", default="", help="Optional Cookie header, e.g. name=value")
    parser.add_argument("--topic-prefix", default="Load test")
    parser.add_argument(
        "--unsafe-real-generation",
        action="store_true",
        help="Required for generation mode because it consumes real model/API resources.",
    )
    parser.add_argument(
        "--poll-generation",
        action="store_true",
        help="In generation mode, wait until each run completes, fails, or times out.",
    )
    return parser.parse_args()


async def run_health(client: httpx.AsyncClient, index: int, args: argparse.Namespace) -> Sample:
    del index, args
    started = time.perf_counter()
    try:
        response = await client.get("/api/health")
        elapsed = time.perf_counter() - started
        return Sample(response.status_code == 200, elapsed, str(response.status_code), response.text[:160])
    except Exception as exc:  # noqa: BLE001 - report load-test failures without hiding type.
        return Sample(False, time.perf_counter() - started, "exception", repr(exc))


async def run_session(client: httpx.AsyncClient, index: int, args: argparse.Namespace) -> Sample:
    started = time.perf_counter()
    session_id = ""
    try:
        create = await client.post(
            "/api/sessions",
            json={
                "topic": f"{args.topic_prefix} #{index}",
                "brief": "Short synthetic request for session load testing.",
                "page_count": max(1, min(args.page_count, 40)),
                "style_id": "executive",
                "style_prompt": "",
                "enable_ai_images": False,
                "output_language": "auto",
            },
        )
        if create.status_code >= 400:
            return Sample(False, time.perf_counter() - started, f"create:{create.status_code}", create.text[:240])
        session_id = create.json()["session_id"]

        detail = await client.get(f"/api/sessions/{session_id}")
        if detail.status_code >= 400:
            return Sample(False, time.perf_counter() - started, f"detail:{detail.status_code}", detail.text[:240])

        listing = await client.get("/api/sessions?limit=5")
        if listing.status_code >= 400:
            return Sample(False, time.perf_counter() - started, f"list:{listing.status_code}", listing.text[:240])

        delete = await client.delete(f"/api/sessions/{session_id}")
        if delete.status_code >= 400:
            return Sample(False, time.perf_counter() - started, f"delete:{delete.status_code}", delete.text[:240])

        return Sample(True, time.perf_counter() - started, "200")
    except Exception as exc:  # noqa: BLE001
        return Sample(False, time.perf_counter() - started, "exception", repr(exc))


async def run_generation(client: httpx.AsyncClient, index: int, args: argparse.Namespace) -> Sample:
    if not args.unsafe_real_generation:
        return Sample(False, 0, "blocked", "generation mode requires --unsafe-real-generation")

    started = time.perf_counter()
    try:
        create = await client.post(
            "/api/sessions",
            json={
                "topic": f"{args.topic_prefix} generation #{index}",
                "brief": "Create a concise deck for load testing. Keep it simple.",
                "page_count": max(1, min(args.page_count, 40)),
                "style_id": "executive",
                "style_prompt": "",
                "enable_ai_images": False,
                "output_language": "auto",
            },
        )
        if create.status_code >= 400:
            return Sample(False, time.perf_counter() - started, f"create:{create.status_code}", create.text[:240])
        session_id = create.json()["session_id"]

        generation = await client.post(
            "/api/generation/start",
            json={
                "session_id": session_id,
                "prompt": "Generate a concise presentation for a synthetic load test.",
            },
        )
        if generation.status_code >= 400:
            return Sample(
                False,
                time.perf_counter() - started,
                f"start:{generation.status_code}",
                generation.text[:240],
            )

        run_id = generation.json()["run_id"]
        if not args.poll_generation:
            return Sample(True, time.perf_counter() - started, "queued", run_id)

        deadline = time.perf_counter() + args.poll_timeout
        while time.perf_counter() < deadline:
            state = await client.get(f"/api/generation/{run_id}/state")
            if state.status_code >= 400:
                return Sample(False, time.perf_counter() - started, f"state:{state.status_code}", state.text[:240])
            payload = state.json()
            status = payload.get("status", "unknown")
            if status == "completed":
                return Sample(True, time.perf_counter() - started, "completed", run_id)
            if status == "failed":
                return Sample(False, time.perf_counter() - started, "failed", str(payload.get("error", ""))[:240])
            await asyncio.sleep(args.poll_interval)

        return Sample(False, time.perf_counter() - started, "timeout", run_id)
    except Exception as exc:  # noqa: BLE001
        return Sample(False, time.perf_counter() - started, "exception", repr(exc))


async def worker(
    name: int,
    queue: asyncio.Queue[int],
    client: httpx.AsyncClient,
    args: argparse.Namespace,
    results: list[Sample],
) -> None:
    mode_runner = {
        "health": run_health,
        "session": run_session,
        "generation": run_generation,
    }[args.mode]
    while True:
        try:
            index = queue.get_nowait()
        except asyncio.QueueEmpty:
            return
        sample = await mode_runner(client, index, args)
        results.append(sample)
        queue.task_done()
        if (index + 1) % 25 == 0:
            print(f"[load] completed {index + 1} requests", flush=True)
    del name


async def run(args: argparse.Namespace) -> list[Sample]:
    if args.concurrency < 1:
        raise SystemExit("--concurrency must be >= 1")
    if args.requests < 1:
        raise SystemExit("--requests must be >= 1")
    if args.mode == "generation" and not args.unsafe_real_generation:
        raise SystemExit("generation mode requires --unsafe-real-generation")

    headers: dict[str, str] = {}
    if args.cookie:
        headers["Cookie"] = args.cookie

    limits = httpx.Limits(max_connections=max(args.concurrency + 5, 20), max_keepalive_connections=args.concurrency + 5)
    timeout = httpx.Timeout(args.timeout)
    async with httpx.AsyncClient(
        base_url=args.base_url.rstrip("/"),
        headers=headers,
        limits=limits,
        timeout=timeout,
    ) as client:
        queue: asyncio.Queue[int] = asyncio.Queue()
        for index in range(args.requests):
            queue.put_nowait(index)

        results: list[Sample] = []
        workers = [
            asyncio.create_task(worker(worker_id, queue, client, args, results))
            for worker_id in range(args.concurrency)
        ]
        await asyncio.gather(*workers)
        return results


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = math.ceil((p / 100) * len(ordered)) - 1
    return ordered[max(0, min(rank, len(ordered) - 1))]


def print_report(args: argparse.Namespace, results: list[Sample], wall_time: float) -> None:
    latencies = [item.elapsed for item in results]
    ok_count = sum(1 for item in results if item.ok)
    failed_count = len(results) - ok_count
    status_counts = Counter(item.status for item in results)
    failures = [item for item in results if not item.ok][:8]

    print("\n=== tokenvizPPT load test report ===")
    print(f"base_url:      {args.base_url}")
    print(f"mode:          {args.mode}")
    print(f"concurrency:   {args.concurrency}")
    print(f"requests:      {args.requests}")
    print(f"wall_time:     {wall_time:.2f}s")
    print(f"throughput:    {len(results) / wall_time:.2f} req/s" if wall_time > 0 else "throughput:    n/a")
    print(f"ok/failed:     {ok_count}/{failed_count}")
    print(f"status_counts: {dict(status_counts)}")
    if latencies:
        print(f"latency avg:   {statistics.mean(latencies):.3f}s")
        print(f"latency p50:   {percentile(latencies, 50):.3f}s")
        print(f"latency p90:   {percentile(latencies, 90):.3f}s")
        print(f"latency p95:   {percentile(latencies, 95):.3f}s")
        print(f"latency p99:   {percentile(latencies, 99):.3f}s")
        print(f"latency max:   {max(latencies):.3f}s")
    if failures:
        print("\nSample failures:")
        for sample in failures:
            print(f"- {sample.status}: {sample.detail}")


def main() -> int:
    args = parse_args()
    started = time.perf_counter()
    try:
        results = asyncio.run(run(args))
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    wall_time = time.perf_counter() - started
    print_report(args, results, wall_time)
    return 0 if all(item.ok for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
