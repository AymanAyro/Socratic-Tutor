"""Classifier prompt evaluation harness."""

import argparse
import asyncio
import json
import uuid
from collections import defaultdict
from pathlib import Path

from Engine.UnderstandingClassifier import UnderstandingClassifier
from database import AsyncSessionLocal


async def run_classifier_eval(dataset_path: Path, prompt_version: str) -> dict:
    results: list[dict] = []
    async with AsyncSessionLocal() as db:
        clf = UnderstandingClassifier(db, redis=None)
        with dataset_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                sample = json.loads(line)
                concept_name = sample.get("concept", "")
                answer = sample.get("student_answer", "")
                expected = sample.get("expected_state", "")
                cid = uuid.uuid4()
                pred = await clf.classify(cid, concept_name, answer, uuid.uuid4())
                results.append(
                    {
                        "expected": expected,
                        "predicted": pred.state,
                        "confidence": pred.confidence,
                    }
                )
        await db.commit()

    acc = (
        sum(1 for r in results if r["expected"] == r["predicted"]) / len(results)
        if results
        else 0.0
    )
    tp_fp_fn: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    labels = {r["expected"] for r in results} | {r["predicted"] for r in results}
    for r in results:
        exp, pred = r["expected"], r["predicted"]
        for lb in labels:
            if pred == lb:
                if exp == lb:
                    tp_fp_fn[lb]["tp"] += 1
                else:
                    tp_fp_fn[lb]["fp"] += 1
            elif exp == lb:
                tp_fp_fn[lb]["fn"] += 1
    f1_per_state: dict[str, float] = {}
    for lb, v in tp_fp_fn.items():
        p_denom = v["tp"] + v["fp"]
        r_denom = v["tp"] + v["fn"]
        prec = v["tp"] / p_denom if p_denom else 0.0
        rec = v["tp"] / r_denom if r_denom else 0.0
        f1_per_state[lb] = (
            2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        )
    return {
        "accuracy": acc,
        "f1_per_state": f1_per_state,
        "prompt_version": prompt_version,
        "samples": len(results),
    }


async def main_async(args: argparse.Namespace) -> None:
    path = Path(args.dataset)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / "datasets" / path.name
    if not path.exists():
        path = Path(args.dataset)
    report = await run_classifier_eval(path, args.prompt_version)
    print(json.dumps(report, indent=2))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default="classifier_v1.jsonl")
    p.add_argument("--prompt_version", default="v1.0.0")
    args = p.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
