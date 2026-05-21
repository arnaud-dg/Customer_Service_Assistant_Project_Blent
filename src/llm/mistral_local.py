"""Backend LLM local : Ministral via pipeline HuggingFace + ChatHuggingFace (LangChain)."""

from __future__ import annotations
import os
from typing import Any


def get_local_llm(model_id: str, device_map: str = "auto", max_new_tokens: int = 512) -> Any:
    """Retourne un BaseChatModel LangChain wrappant un pipeline HuggingFace local.

    HuggingFacePipeline.from_model_id utilise AutoModelForCausalLM qui ne connaît pas
    Mistral3Config — on charge le modèle explicitement puis on crée le pipeline à la main.
    """
    from langchain_huggingface import ChatHuggingFace, HuggingFacePipeline  # type: ignore[import-not-found]
    from transformers import (  # type: ignore[import-not-found]
        Mistral3ForConditionalGeneration,
        MistralCommonBackend,
        pipeline as hf_pipeline,
    )

    hf_token = os.getenv("HF_TOKEN")

    tokenizer = MistralCommonBackend.from_pretrained(model_id, token=hf_token)
    model = Mistral3ForConditionalGeneration.from_pretrained(
        model_id,
        device_map=device_map,
        torch_dtype="auto",
        token=hf_token,
    )
    pipe = hf_pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        max_new_tokens=max_new_tokens,
    )
    return ChatHuggingFace(llm=HuggingFacePipeline(pipeline=pipe))
