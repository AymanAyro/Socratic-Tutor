from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from eval_harness.run_eval import run_classifier_eval

router = APIRouter(prefix="/eval", tags=["eval"])


class EvalClassifierBody(BaseModel):
    dataset_path: str | None = None
    prompt_version: str = "v1.0.0"


@router.post("/classifier")
async def run_classifier_eval_endpoint(
    body: EvalClassifierBody,
):
    base = Path(__file__).resolve().parent.parent / "eval_harness" / "datasets"
    name = body.dataset_path or "classifier_v1.jsonl"
    path = Path(name)
    if not path.is_absolute():
        path = base / Path(name).name
    if not path.exists():
        path = base / "classifier_v1.jsonl"
    return await run_classifier_eval(path, body.prompt_version)
