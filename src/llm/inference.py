"""
Lokaler Gemma-4-Inference-Wrapper via HuggingFace Transformers.
Lädt das Modell einmalig in GPU-Speicher und hält es warm.
"""
import os
import torch
from typing import Generator, Iterator
from loguru import logger
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline, TextIteratorStreamer
from threading import Thread


MODEL_ID = os.getenv("LLM_MODEL", "google/gemma-4-E4B-it")
MAX_NEW_TOKENS = int(os.getenv("LLM_MAX_TOKENS", 256))


class GemmaInference:
    def __init__(self, model_id: str = None):
        self.model_id = model_id or MODEL_ID
        self.model = None
        self.tokenizer = None
        self.pipe = None
        self._load()

    def _load(self):
        logger.info(f"Lade {self.model_id} mit 4-bit Quantisierung auf GPU...")
        from transformers import BitsAndBytesConfig

        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
        )
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_id)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            quantization_config=quant_config,
            device_map="cuda",
        )
        self.pipe = pipeline(
            "text-generation",
            model=self.model,
            tokenizer=self.tokenizer,
        )
        vram = torch.cuda.memory_allocated() / 1e9
        logger.success(f"Modell geladen (4-bit). VRAM belegt: {vram:.1f} GB")

    def _build_prompt(self, messages: list) -> str:
        return self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

    def chat(self, messages: list, max_new_tokens: int = None, temperature: float = 0.7) -> str:
        """Vollständige Antwort generieren (blockierend)."""
        result = self.pipe(
            self._build_prompt(messages),
            max_new_tokens=max_new_tokens or MAX_NEW_TOKENS,
            do_sample=temperature > 0,
            temperature=temperature,
            top_p=0.9,
            return_full_text=False,
        )
        return result[0]["generated_text"].strip()

    def chat_stream(self, messages: list, max_new_tokens: int = None, temperature: float = 0.7) -> Iterator[str]:
        """
        Antwort als Stream generieren — Token für Token.
        Yield: jeweils ein neues Textstück.
        Für FastAPI: als Server-Sent Events oder WebSocket nutzbar.
        """
        streamer = TextIteratorStreamer(
            self.tokenizer,
            skip_prompt=True,
            skip_special_tokens=True,
        )
        inputs = self.tokenizer(
            self._build_prompt(messages),
            return_tensors="pt",
        ).to(self.model.device)

        gen_kwargs = {
            **inputs,
            "max_new_tokens": max_new_tokens or MAX_NEW_TOKENS,
            "do_sample": temperature > 0,
            "temperature": temperature,
            "top_p": 0.9,
            "streamer": streamer,
        }

        # Generierung in separatem Thread damit Stream sofort beginnt
        thread = Thread(target=self.model.generate, kwargs=gen_kwargs)
        thread.start()

        for token in streamer:
            yield token

        thread.join()
