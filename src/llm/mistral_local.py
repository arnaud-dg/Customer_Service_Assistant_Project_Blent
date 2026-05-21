"""Backend LLM local : HuggingFacePipeline + ChatHuggingFace (LangChain)."""

from __future__ import annotations
import os
from typing import Any


def get_local_llm(model_id: str, device_map: str = "auto", max_new_tokens: int = 512) -> Any:
    """Retourne un BaseChatModel LangChain wrappant un pipeline HuggingFace local."""
    from langchain_huggingface import ChatHuggingFace, HuggingFacePipeline  # type: ignore[import-not-found]

    hf_token = os.getenv("HF_TOKEN")
    pipeline = HuggingFacePipeline.from_model_id(
        model_id=model_id,
        task="text-generation",
        model_kwargs={
            "device_map": device_map,
            "torch_dtype": "auto",
            "token": hf_token,
        },
        device=None,
        pipeline_kwargs={"max_new_tokens": max_new_tokens},
    )
    return ChatHuggingFace(llm=pipeline)
