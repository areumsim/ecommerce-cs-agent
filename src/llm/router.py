from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.config import get_config
from .client import LLMClient, LLMConfig, load_prompt


def _provider_cfg(provider: str) -> Dict[str, Any]:
    raw = get_config().get_raw("llm") or {}
    return raw.get(provider, {})


def _build_llm_config(provider: str) -> LLMConfig:
    llm = get_config().llm
    pcfg = _provider_cfg(provider)

    base_urls = {
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com",
        "google": "https://generativelanguage.googleapis.com",
        "local": pcfg.get("base_url") or getattr(llm, 'base_url', None) or "http://localhost:8080/v1",
    }

    api_key = pcfg.get("api_key", "")
    model = pcfg.get("model", llm.model)
    temperature = pcfg.get("temperature", llm.temperature)
    max_tokens = pcfg.get("max_tokens", llm.max_tokens)
    timeout = pcfg.get("timeout", llm.timeout)

    return LLMConfig(
        provider=provider,
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        base_url=base_urls.get(provider),
    )


def _select_provider(intent: str) -> str:
    raw = get_config().get_raw("llm") or {}
    routing = raw.get("routing", {})
    if not routing or not routing.get("enabled", False):
        return get_config().llm.provider

    rules = routing.get("rules", [])
    for r in rules:
        when = r.get("when", {})
        intents = when.get("intents", [])
        if intents and intent in intents:
            return r.get("provider") or get_config().llm.provider

    fb = routing.get("fallback", {})
    return fb.get("provider") or get_config().llm.provider


def _provider_available(cfg: LLMConfig) -> bool:
    if cfg.provider in ("openai", "anthropic", "google"):
        return bool(cfg.api_key)
    if cfg.provider == "local":
        return bool(cfg.base_url)
    return True


async def generate_routed_response(
    context: Dict[str, Any],
    user_message: str,
    intent: str,
) -> str:
    raw = get_config().get_raw("llm") or {}
    routing = raw.get("routing", {})

    # 선택 provider + fallback 체인 순서대로 시도
    first = _select_provider(intent)
    fb_chain = (routing.get("fallback", {}) or {}).get("chain", [])
    providers: List[str] = [first] + [p for p in fb_chain if p != first]

    last_err: Optional[Exception] = None

    # 공통 프롬프트 구성
    system_prompt = load_prompt("system")
    intent_prompt = load_prompt(intent)
    if intent_prompt:
        system_prompt = f"{system_prompt}

{intent_prompt}"

    # 간단 컨텍스트 플래튼
    ctx_lines: List[str] = []
    for k, v in (context or {}).items():
        ctx_lines.append(f"{k}: {v}")
    context_str = "

[제공된 데이터]
" + "
".join(ctx_lines) if ctx_lines else ""
    full_system = f"{system_prompt}{context_str}"
    messages = [{"role": "user", "content": user_message}]

    for prov in providers:
        cfg = _build_llm_config(prov)
        if not _provider_available(cfg):
            last_err = RuntimeError(f"provider not available: {prov}")
            continue
        client = LLMClient(cfg)
        try:
            return await client.chat(messages, system_prompt=full_system)
        except Exception as e:
            last_err = e
        finally:
            try:
                await client.close()
            except Exception:
                pass
            # 다음 provider로 폴백
            continue

    raise RuntimeError(f"LLM routing failed: {last_err}")
