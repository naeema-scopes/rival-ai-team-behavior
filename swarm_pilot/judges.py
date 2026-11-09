"""Judge configuration shared by all coding scripts.

A judge is "model@effort" or "model@effort@Provider" (provider pinned, no fallbacks).
Phase 2 default (decided by the team): Claude Haiku 5.5 + DeepSeek V4.1 Flash (pinned to DeepInfra, fp8), both at 'high'.
"""
PHASE2 = "anthropic/claude-haiku-5.5@high,deepseek/deepseek-v4.1-flash@high@DeepInfra"


def parse(spec: str):
    out = []
    for item in spec.split(","):
        parts = item.strip().split("@")
        out.append(dict(model=parts[0], effort=parts[1] if len(parts) > 1 and parts[1] else None,
                        provider=[parts[2]] if len(parts) > 2 and parts[2] else None))
    return out
