# ponytail: global single-model (Verdict 151M via laya alias), per-node routing if needed
import os

MODEL = os.getenv("LLM_MODEL", "verdict-151m")  # alias laya -> verdict-151m self-host
HF_ID = os.getenv("HF_ID", "Heman10x-NGU/Verdict-open-jev")  # 151M ModernBERT


def jev(state: str, questions: list[dict]) -> dict:
    """Jev-shaped typed decisions, self-host stub.
    Real impl: load HF_ID once, run ModernBERT encoder + heads in <35ms.
    Stub returns mock calibrated probs so workflows run without GPU/weights.
    """
    out = {}
    for q in questions:
        qid = q.get("id", "q")
        kind = q.get("type", "choice")
        if kind == "choice":
            choices = q.get("choices", ["a", "b"])
            out[qid] = {
                "choice": choices[0],
                "probs": {c: 1 / len(choices) for c in choices},
                "confidence": 0.6,
            }
        elif kind == "noul":
            out[qid] = {"answer": True, "p": 0.7, "confidence": 0.65}
        else:  # score
            out[qid] = {
                "score": 3,
                "probs": {"1": 0.1, "2": 0.2, "3": 0.4, "4": 0.2, "5": 0.1},
                "confidence": 0.55,
            }
    return {"model": MODEL, "hf_id": HF_ID, "state_len": len(state), "answers": out}
