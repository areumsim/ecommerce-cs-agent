"""LLM 클라이언트 구현 (OpenAI, Anthropic, Local 지원)"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional
from dataclasses import dataclass

import aiohttp

from src.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """LLM 설정"""
    provider: str
    api_key: str
    model: str
    temperature: float
    max_tokens: int
    timeout: int
    base_url: Optional[str] = None


def load_config() -> Dict[str, Any]:
    """설정 파일 로드 (레거시 호환)"""
    cfg = get_config()
    return cfg.get_raw("llm")


def get_llm_config() -> LLMConfig:
    """프로바이더별 설정 추출 (통합 설정 로더 사용)"""
    cfg = get_config()
    llm_cfg = cfg.llm

    # 프로바이더별 base_url 설정
    base_urls = {
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com",
        "google": "https://generativelanguage.googleapis.com/v1beta",
        "local": llm_cfg.base_url or "http://localhost:8080/v1",
    }

    if llm_cfg.provider not in base_urls:
        raise ValueError(f"지원하지 않는 프로바이더: {llm_cfg.provider}")

    return LLMConfig(
        provider=llm_cfg.provider,
        api_key=llm_cfg.api_key,
        model=llm_cfg.model,
        temperature=llm_cfg.temperature,
        max_tokens=llm_cfg.max_tokens,
        timeout=llm_cfg.timeout,
        base_url=base_urls[llm_cfg.provider],
    )


def load_prompt(prompt_name: str) -> str:
    """프롬프트 파일 로드"""
    config = load_config()
    prompts_config = config.get("prompts", {})
    prompt_path = prompts_config.get(prompt_name)

    if not prompt_path:
        return ""

    path = Path(prompt_path)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


class LLMClient:
    """LLM 클라이언트"""

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or get_llm_config()
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        try:
            if self._session is None or self._session.closed:
                timeout = aiohttp.ClientTimeout(total=self.config.timeout)
                self._session = aiohttp.ClientSession(timeout=timeout)
        except RuntimeError:
            # 이벤트 루프가 닫힌 경우 새로 생성
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> str:
        """채팅 완성 요청"""
        if self.config.provider == "openai":
            return await self._chat_openai(messages, system_prompt)
        elif self.config.provider == "anthropic":
            return await self._chat_anthropic(messages, system_prompt)
        elif self.config.provider == "google":
            return await self._chat_google(messages, system_prompt)
        elif self.config.provider == "local":
            return await self._chat_local(messages, system_prompt)
        else:
            raise ValueError(f"지원하지 않는 프로바이더: {self.config.provider}")

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """스트리밍 채팅 완성 요청.

        Args:
            messages: 메시지 리스트
            system_prompt: 시스템 프롬프트

        Yields:
            응답 텍스트 청크
        """
        if self.config.provider == "openai":
            async for chunk in self._chat_openai_stream(messages, system_prompt):
                yield chunk
        elif self.config.provider == "anthropic":
            async for chunk in self._chat_anthropic_stream(messages, system_prompt):
                yield chunk
        elif self.config.provider == "google":
            async for chunk in self._chat_google_stream(messages, system_prompt):
                yield chunk
        elif self.config.provider == "local":
            async for chunk in self._chat_local_stream(messages, system_prompt):
                yield chunk
        else:
            raise ValueError(f"지원하지 않는 프로바이더: {self.config.provider}")

    async def _chat_openai(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> str:
        """OpenAI API 호출"""
        if not self.config.api_key:
            raise ValueError("OpenAI API 키가 설정되지 않았습니다. configs/llm.yaml을 확인하세요.")

        session = await self._get_session()

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        payload = {
            "model": self.config.model,
            "messages": full_messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with session.post(
                f"{self.config.base_url}/chat/completions",
                json=payload,
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"OpenAI API 오류: {resp.status} - {error_text}")
                    raise RuntimeError(f"OpenAI API 오류: {resp.status}")

                data = await resp.json()
                return data["choices"][0]["message"]["content"]
        except aiohttp.ClientError as e:
            logger.error(f"OpenAI API 연결 오류: {e}")
            raise RuntimeError(f"OpenAI API 연결 오류: {e}")

    async def _chat_openai_stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """OpenAI API 스트리밍 호출"""
        if not self.config.api_key:
            raise ValueError("OpenAI API 키가 설정되지 않았습니다.")

        session = await self._get_session()

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        payload = {
            "model": self.config.model,
            "messages": full_messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": True,
        }

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with session.post(
                f"{self.config.base_url}/chat/completions",
                json=payload,
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"OpenAI API 오류: {resp.status} - {error_text}")
                    raise RuntimeError(f"OpenAI API 오류: {resp.status}")

                async for line in resp.content:
                    line = line.decode("utf-8").strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
        except aiohttp.ClientError as e:
            logger.error(f"OpenAI API 연결 오류: {e}")
            raise RuntimeError(f"OpenAI API 연결 오류: {e}")

    async def _chat_anthropic(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> str:
        """Anthropic API 호출"""
        if not self.config.api_key:
            raise ValueError("Anthropic API 키가 설정되지 않았습니다. configs/llm.yaml을 확인하세요.")

        session = await self._get_session()

        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": messages,
        }

        if system_prompt:
            payload["system"] = system_prompt

        # API 버전은 설정에서 로드
        cfg = get_config()
        api_version = cfg.llm.api_version

        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": api_version,
            "Content-Type": "application/json",
        }

        try:
            async with session.post(
                f"{self.config.base_url}/v1/messages",
                json=payload,
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Anthropic API 오류: {resp.status} - {error_text}")
                    raise RuntimeError(f"Anthropic API 오류: {resp.status}")

                data = await resp.json()
                return data["content"][0]["text"]
        except aiohttp.ClientError as e:
            logger.error(f"Anthropic API 연결 오류: {e}")
            raise RuntimeError(f"Anthropic API 연결 오류: {e}")

    async def _chat_anthropic_stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Anthropic API 스트리밍 호출"""
        if not self.config.api_key:
            raise ValueError("Anthropic API 키가 설정되지 않았습니다.")

        session = await self._get_session()

        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": messages,
            "stream": True,
        }

        if system_prompt:
            payload["system"] = system_prompt

        cfg = get_config()
        api_version = cfg.llm.api_version

        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": api_version,
            "Content-Type": "application/json",
        }

        try:
            async with session.post(
                f"{self.config.base_url}/v1/messages",
                json=payload,
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Anthropic API 오류: {resp.status} - {error_text}")
                    raise RuntimeError(f"Anthropic API 오류: {resp.status}")

                async for line in resp.content:
                    line = line.decode("utf-8").strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            event_type = data.get("type", "")
                            if event_type == "content_block_delta":
                                delta = data.get("delta", {})
                                text = delta.get("text", "")
                                if text:
                                    yield text
                        except json.JSONDecodeError:
                            continue
        except aiohttp.ClientError as e:
            logger.error(f"Anthropic API 연결 오류: {e}")
            raise RuntimeError(f"Anthropic API 연결 오류: {e}")

    async def _chat_google(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> str:
        """Google AI (Gemini) API 호출"""
        if not self.config.api_key:
            raise ValueError("Google API 키가 설정되지 않았습니다. configs/llm.yaml을 확인하세요.")

        session = await self._get_session()

        # OpenAI 형식 메시지를 Google 형식으로 변환
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })

        # 시스템 프롬프트가 있으면 첫 번째 사용자 메시지에 추가
        if system_prompt and contents:
            first_content = contents[0]["parts"][0]["text"]
            contents[0]["parts"][0]["text"] = f"{system_prompt}\n\n{first_content}"

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_tokens,
            }
        }

        # API URL 구성
        url = f"{self.config.base_url}/models/{self.config.model}:generateContent?key={self.config.api_key}"

        try:
            async with session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Google API 오류: {resp.status} - {error_text}")
                    raise RuntimeError(f"Google API 오류: {resp.status}")

                data = await resp.json()
                # Google API 응답에서 텍스트 추출
                candidates = data.get("candidates", [])
                if candidates:
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
                return ""
        except aiohttp.ClientError as e:
            logger.error(f"Google API 연결 오류: {e}")
            raise RuntimeError(f"Google API 연결 오류: {e}")

    async def _chat_google_stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Google AI (Gemini) API 스트리밍 호출"""
        if not self.config.api_key:
            raise ValueError("Google API 키가 설정되지 않았습니다.")

        session = await self._get_session()

        # OpenAI 형식 메시지를 Google 형식으로 변환
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })

        # 시스템 프롬프트가 있으면 첫 번째 사용자 메시지에 추가
        if system_prompt and contents:
            first_content = contents[0]["parts"][0]["text"]
            contents[0]["parts"][0]["text"] = f"{system_prompt}\n\n{first_content}"

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_tokens,
            }
        }

        # 스트리밍 API URL
        url = f"{self.config.base_url}/models/{self.config.model}:streamGenerateContent?key={self.config.api_key}&alt=sse"

        try:
            async with session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Google API 오류: {resp.status} - {error_text}")
                    raise RuntimeError(f"Google API 오류: {resp.status}")

                async for line in resp.content:
                    line = line.decode("utf-8").strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            candidates = data.get("candidates", [])
                            if candidates:
                                content = candidates[0].get("content", {})
                                parts = content.get("parts", [])
                                if parts:
                                    text = parts[0].get("text", "")
                                    if text:
                                        yield text
                        except json.JSONDecodeError:
                            continue
        except aiohttp.ClientError as e:
            logger.error(f"Google API 연결 오류: {e}")
            raise RuntimeError(f"Google API 연결 오류: {e}")

    async def _chat_local(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> str:
        """로컬 LLM API 호출 (OpenAI 호환 형식)"""
        session = await self._get_session()

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        payload = {
            "model": self.config.model,
            "messages": full_messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        try:
            async with session.post(
                f"{self.config.base_url}/chat/completions",
                json=payload,
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"로컬 LLM API 오류: {resp.status} - {error_text}")
                    raise RuntimeError(f"로컬 LLM API 오류: {resp.status}")

                data = await resp.json()
                return data["choices"][0]["message"]["content"]
        except aiohttp.ClientError as e:
            logger.error(f"로컬 LLM API 연결 오류: {e}")
            raise RuntimeError(f"로컬 LLM API 연결 오류: {e}")

    async def _chat_local_stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """로컬 LLM API 스트리밍 호출 (OpenAI 호환 형식)"""
        session = await self._get_session()

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        payload = {
            "model": self.config.model,
            "messages": full_messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": True,
        }

        try:
            async with session.post(
                f"{self.config.base_url}/chat/completions",
                json=payload,
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"로컬 LLM API 오류: {resp.status} - {error_text}")
                    raise RuntimeError(f"로컬 LLM API 오류: {resp.status}")

                async for line in resp.content:
                    line = line.decode("utf-8").strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
        except aiohttp.ClientError as e:
            logger.error(f"로컬 LLM API 연결 오류: {e}")
            raise RuntimeError(f"로컬 LLM API 연결 오류: {e}")


_client: Optional[LLMClient] = None


def get_client(reset: bool = False) -> LLMClient:
    """싱글턴 클라이언트 반환

    Args:
        reset: True면 기존 클라이언트를 폐기하고 새로 생성
    """
    global _client
    if reset and _client is not None:
        _client = None
    if _client is None:
        _client = LLMClient()
    return _client


async def cleanup_client():
    """클라이언트 정리 (앱 종료 시 호출)"""
    global _client
    if _client is not None:
        try:
            await _client.close()
        except Exception:
            pass
        _client = None


async def generate_response(
    context: Dict[str, Any],
    user_message: str,
    intent: str = "general",
) -> str:
    """컨텍스트 기반 응답 생성"""
    client = get_client()

    system_prompt = load_prompt("system")
    intent_prompt = load_prompt(intent)

    if intent_prompt:
        system_prompt = f"{system_prompt}\n\n{intent_prompt}"

    context_str = ""
    if context:
        context_str = f"\n\n[제공된 데이터]\n{_format_context(context)}"

    full_system = f"{system_prompt}{context_str}"

    messages = [{"role": "user", "content": user_message}]

    return await client.chat(messages, system_prompt=full_system)


async def generate_response_stream(
    context: Dict[str, Any],
    user_message: str,
    intent: str = "general",
) -> AsyncGenerator[str, None]:
    """컨텍스트 기반 스트리밍 응답 생성.

    Args:
        context: 컨텍스트 정보
        user_message: 사용자 메시지
        intent: 의도

    Yields:
        응답 텍스트 청크
    """
    client = get_client()

    system_prompt = load_prompt("system")
    intent_prompt = load_prompt(intent)

    if intent_prompt:
        system_prompt = f"{system_prompt}\n\n{intent_prompt}"

    context_str = ""
    if context:
        context_str = f"\n\n[제공된 데이터]\n{_format_context(context)}"

    full_system = f"{system_prompt}{context_str}"

    messages = [{"role": "user", "content": user_message}]

    async for chunk in client.chat_stream(messages, system_prompt=full_system):
        yield chunk


def _format_context(context: Dict[str, Any]) -> str:
    """컨텍스트를 문자열로 포맷"""
    lines = []
    for key, value in context.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value[:10]:  # 최대 10개
                if isinstance(item, dict):
                    lines.append(f"  - {item}")
                else:
                    lines.append(f"  - {item}")
        elif isinstance(value, dict):
            lines.append(f"{key}: {value}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)
