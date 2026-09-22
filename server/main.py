from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="loom")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

ROOT = Path(__file__).resolve().parent.parent


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/automations")
def list_automations():
    base = ROOT / "src" / "automation"
    if not base.exists():
        return []
    out = []
    for d in sorted(
        p for p in base.iterdir() if p.is_dir() and not p.name.startswith("_")
    ):
        plan = d / "plan.md"
        wf = d / "workflow.json"
        out.append(
            {
                "id": d.name,
                "name": d.name,
                "hasPlan": plan.exists(),
                "hasWorkflow": wf.exists(),
            }
        )
    return out
