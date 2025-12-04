# llm.py
import torch
import gc
from transformers import pipeline

class LLM:
    def __init__(self, model_name="Qwen/Qwen2.5-1.5B-Instruct"):
        gc.collect()
        torch.cuda.empty_cache()

        self.DEVICE = 0 if torch.cuda.is_available() else -1
        self.BASE_MODEL_NAME = model_name

        self.pipeline = pipeline(
            "text-generation",
            model=model_name,
            tokenizer=model_name,
            model_kwargs={"torch_dtype": torch.bfloat16},
            device=self.DEVICE,
        )

        self.answer_cache = {}

        self.SYSTEM_PROMPT = (
            "You are mimicking a Linux terminal. Output only the terminal result, "
            "no explanations, no backticks."
        )

    def answer(self, cmd, history):
        if cmd in self.answer_cache:
            return self.answer_cache[cmd]

        user_prompt = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        for i, item in enumerate(history[-6:]):
            role = "user" if i % 2 == 0 else "assistant"
            user_prompt.append({"role": role, "content": item})
        user_prompt.append({"role": "user", "content": cmd})

        prompt = self.pipeline.tokenizer.apply_chat_template(
            user_prompt, tokenize=False, add_generation_prompt=True
        )

        out = self.pipeline(
            prompt,
            max_new_tokens=128,
            temperature=0.0,
            top_p=0.9,
            eos_token_id=self.pipeline.tokenizer.eos_token_id,
        )[0]["generated_text"][len(prompt):]

        out = out.strip().replace("```", "")
        self.answer_cache[cmd] = out
        return out

    def profile(self, cmd):
        prompt = (
            "Analyze this SSH command and output STRICT JSON ONLY:\n\n"
            f"{cmd}\n\n"
            "Fields: attacker_intent, sophistication_level, risk_score, explanation."
        )

        out = self.pipeline(
            prompt,
            max_new_tokens=64,
            temperature=0.0,
            do_sample=False,
            eos_token_id=self.pipeline.tokenizer.eos_token_id,
        )[0]["generated_text"]

        start, end = out.find("{"), out.rfind("}")
        if start != -1 and end != -1:
            return out[start:end+1]

        return '{"intent":"unknown","score":0}'
