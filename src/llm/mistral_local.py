"""Backend LLM local : Ministral-3-14B quantisé FP8 - HuggingFace Transformers.

Modèle local sous la forme d'un `BaseChatModel` LangChain ; à activer lors
du déploiement sur cloudbox virtuel.
"""

from __future__ import annotations
import os
from typing import Any
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field, PrivateAttr

class MistralLocalChat(BaseChatModel):
    """Wrapper LangChain autour de `Mistral3ForConditionalGeneration` quantisé FP8."""

    model_id: str = Field(...)
    device_map: str = Field(default="auto")
    max_new_tokens: int = Field(default=512)
    temperature: float = Field(default=0.0)

    _model: Any = PrivateAttr(default=None)
    _tokenizer: Any = PrivateAttr(default=None)

    def model_post_init(self, __context: Any) -> None:  # noqa: D401
        """Charge le modèle et le tokenizer"""
        # Imports locaux pour ne pas exiger torch/transformers si le backend n'est pas utilisé
        from transformers import (  # type: ignore[import-not-found]
            FineGrainedFP8Config,
            Mistral3ForConditionalGeneration,
            MistralCommonBackend,
        )

        hf_token = os.getenv("HF_TOKEN")
        # Chargement tokenizer
        self._tokenizer = MistralCommonBackend.from_pretrained(self.model_id, token=hf_token)
        # Chargement modèle FP8 natif — ~14 Go de VRAM pour un 14B
        self._model = Mistral3ForConditionalGeneration.from_pretrained(
            self.model_id,
            device_map=self.device_map,
            quantization_config=FineGrainedFP8Config(),
            token=hf_token,
        )

    @property
    def _llm_type(self) -> str:
        return "mistral-local-fp8"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Génère une réponse à partir d'une liste de messages LangChain."""
        # Conversion des messages LangChain → format chat HF
        chat_messages = [
            {"role": _role_for(m), "content": m.content if isinstance(m.content, str) else str(m.content)}
            for m in messages
        ]

        inputs = self._tokenizer.apply_chat_template(
            chat_messages,
            add_generation_prompt=True,
            return_tensors="pt",
        ).to(self._model.device)

        outputs = self._model.generate(
            inputs,
            max_new_tokens=kwargs.get("max_new_tokens", self.max_new_tokens),
            temperature=kwargs.get("temperature", self.temperature),
            do_sample=self.temperature > 0,
        )

        # On ne décode que les tokens nouvellement générés
        generated = outputs[0, inputs.shape[-1]:]
        text_out = self._tokenizer.decode(generated, skip_special_tokens=True)

        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text_out))])

def _role_for(message: BaseMessage) -> str:
    """Mappe les types de message LangChain vers les rôles de chat HF."""
    mapping = {"human": "user", "ai": "assistant", "system": "system"}
    return mapping.get(message.type, "user")
