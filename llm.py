# """Chat model factory. Provider and model come from .env."""
# import os


# def get_llm():
#     provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
#     model = os.getenv("LLM_MODEL")
#     if provider == "openai":
#         if not model:
#             raise RuntimeError("Set LLM_MODEL in .env when LLM_PROVIDER=openai")
#         from langchain_openai import ChatOpenAI
#         return ChatOpenAI(model=model, temperature=0, max_tokens=800)  # needs OPENAI_API_KEY
#     from langchain_anthropic import ChatAnthropic
#     return ChatAnthropic(model=model or "claude-sonnet-5-5", temperature=0, max_tokens=800)  # needs ANTHROPIC_API_KEY



"""Chat model factory. Provider and model come from .env."""
import os

from dotenv import load_dotenv

load_dotenv()


def get_llm():
    provider = os.getenv("LLM_PROVIDER", "openai").lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        model = os.getenv("LLM_MODEL", "Qwen/Qwen3.5-4B")
        base_url = os.getenv("LLM_BASE_URL")
        api_key = os.getenv("LLM_API_KEY")

        if not base_url:
            raise RuntimeError("Set LLM_BASE_URL in .env")

        if not api_key:
            raise RuntimeError("Set LLM_API_KEY in .env")

        return ChatOpenAI(
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=0,
            max_tokens=800,
            timeout=120,
            max_retries=2,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}}
        )

    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")
