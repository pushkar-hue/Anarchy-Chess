import os
import modal
from pydantic import BaseModel
from typing import List, Dict, Optional

class ChatLibrary(BaseModel):
    messages: List[Dict[str, str]]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 512

# Create the Modal app
app = modal.App("gemma-chess-backend")

# Setup persistent volume for caching the weights file
volume = modal.Volume.from_name("model-cache-v2", create_if_missing=True)
CACHE_DIR = "/models"

# 1. Optimized Build Image
image = (
    modal.Image.from_registry("nvidia/cuda:12.2.2-devel-ubuntu22.04", add_python="3.10")
    .pip_install("huggingface_hub", "pydantic", "fastapi[standard]")
    .env({
        "CMAKE_ARGS": "-DGGML_CUDA=on",
        "CC": "gcc",
        "CXX": "g++"
    })
    .pip_install("llama-cpp-python")
)

# Official Google Gemma 4 26B 4-bit GGUF Repo
REPO_ID = "google/gemma-4-26B-A4B-it-qat-q4_0-gguf"
FILENAME = "gemma-4-26B_q4_0-it.gguf"

@app.cls(
    image=image,
    gpu="A10G",                  # Safely downsized to 24GB VRAM!
    volumes={CACHE_DIR: volume},
    scaledown_window=60,   
    timeout=1800,
    secrets=[modal.Secret.from_name("huggingface")]
)
class GemmaServer:
    @modal.enter()
    def load_model(self):
        from huggingface_hub import hf_hub_download
        from llama_cpp import Llama

        token = os.environ["HF_TOKEN"]

        print("Checking/Downloading model weights...")
        model_path = hf_hub_download(
            repo_id=REPO_ID,
            filename=FILENAME,
            cache_dir=CACHE_DIR,
            token=token, # Required for gated Google models
        )
        
        print("Initializing engine on GPU...")
        self.llm = Llama(
            model_path=model_path,
            n_gpu_layers=-1, # Offload 100% of the math to the A10G
            n_ctx=4096,      # Context window large enough for chess history
            verbose=False
        )

    @modal.method()
    def chat_generation(self, messages: list, temperature: float, max_tokens: int):
        # llama-cpp-python automatically applies the Gemma chat template
        response = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response["choices"][0]["message"]["content"]

# 2. The Serverless Web Entrypoint
@app.function(image=image, timeout=1800)
@modal.fastapi_endpoint(method="POST")
def api(payload: ChatLibrary): 
    server = GemmaServer()
    ai_response = server.chat_generation.remote(
        payload.messages, 
        payload.temperature, 
        payload.max_tokens
    )
    return {"response": ai_response}