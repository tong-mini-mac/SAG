import os
import json
from abc import ABC, abstractmethod
from google import genai
from google.genai import types

class BaseLLMClient(ABC):
    """Abstract base class for all LLM providers."""
    @abstractmethod
    def call(self, prompt, system_instruction=None, json_mode=False):
        pass

class MissingApiKeyProvider(BaseLLMClient):
    """Placeholder when no key is set so the UI and watchdog can start."""

    def call(self, prompt, system_instruction=None, json_mode=False):
        raise RuntimeError(
            "AI API key is not set. Open System Config in the sidebar, or set "
            "GEMINI_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY in config/.env."
        )

class GeminiProvider(BaseLLMClient):
    def __init__(self, api_key, model="gemini-2.5-flash"):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def call(self, prompt, system_instruction=None, json_mode=False):
        from .Utils import safe_ai_call
        def _call():
            config = types.GenerateContentConfig(
                temperature=0.2,
                system_instruction=system_instruction
            )
            if json_mode:
                config.response_mime_type = "application/json"
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config
            )
            return response.text
        return safe_ai_call(_call)

class OpenAIProvider(BaseLLMClient):
    def __init__(self, api_key, model="gpt-4o"):
        import openai
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model

    def call(self, prompt, system_instruction=None, json_mode=False):
        from .Utils import safe_ai_call
        def _call():
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})
            
            kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                **kwargs
            )
            return response.choices[0].message.content
        return safe_ai_call(_call)

class AnthropicProvider(BaseLLMClient):
    def __init__(self, api_key, model="claude-3-5-sonnet-20240620"):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def call(self, prompt, system_instruction=None, json_mode=False):
        from .Utils import safe_ai_call
        def _call():
            messages = [{"role": "user", "content": prompt}]
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_instruction if system_instruction else "",
                messages=messages,
                temperature=0.2
            )
            return response.content[0].text
        return safe_ai_call(_call)

class LLMFactory:
    @staticmethod
    def get_client(provider_name, api_key, model=None):
        if not api_key:
            return MissingApiKeyProvider()
        if provider_name.lower() == "google":
            return GeminiProvider(api_key, model or "gemini-2.5-flash")
        elif provider_name.lower() == "openai":
            return OpenAIProvider(api_key, model or "gpt-4o")
        elif provider_name.lower() == "anthropic":
            return AnthropicProvider(api_key, model or "claude-3-5-sonnet-20240620")
        else:
            raise ValueError(f"Unsupported provider: {provider_name}")
