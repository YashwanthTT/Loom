# ponytail: mocked until Playwright/Browserbase key; same interface as real Stagehand
def stagehand(url: str, goal: str, extract: bool = True) -> dict:
    """Browserbase Stagehand stub — replace with: from stagehand import Stagehand"""
    return {
        "url": url,
        "goal": goal,
        "mock": True,
        "extracted": {"title": "mock", "price": None},
        "note": "add STAGEHAND_API_KEY + pip install stagehand to enable real act/extract/observe",
    }
