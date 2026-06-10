import os
import modal
from pydantic import BaseModel
from typing import List, Dict



class ChatLibrary(BaseModel):
    messages: List[Dict[str, str]]

# Create the Modal app
app = modal.App("nemotron-chess-backend")

# Setup persistent volume for caching the 20GB weights file
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
REPO_ID = "unsloth/NVIDIA-Nemotron-3-Nano-Omni-30B-A3B-Reasoning-GGUF"
FILENAME = "NVIDIA-Nemotron-3-Nano-Omni-30B-A3B-Reasoning-UD-IQ3_S.gguf"

@app.cls(
    image=image,
    gpu="A10G",                  # Downsized from A100 to save ~60% hourly cost
    volumes={CACHE_DIR: volume},
    scaledown_window=60,   # Shuts down the GPU after 60 seconds of inactivity
    timeout=300,
)
class NemotronServer:
    @modal.enter()
    def load_model(self):
        from huggingface_hub import hf_hub_download
        from llama_cpp import Llama

        print("Checking/Downloading model weights...")
        model_path = hf_hub_download(
            repo_id=REPO_ID,
            filename=FILENAME,
            cache_dir=CACHE_DIR,
        )
        
        print("Initializing engine on GPU...")
        # We set n_ctx to 2048 to save memory space for faster KV-caching during games
        self.llm = Llama(
            model_path=model_path,
            n_gpu_layers=-1, 
            n_ctx=2048,      
            verbose=False
        )

    @modal.method()
    def chat_generation(self, messages: list):
        # Accepts raw structured conversation states directly from your Gradio app
        response = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=450,
            temperature=0.8,
        )
        return response["choices"][0]["message"]["content"]

# 2. The Serverless Web Entrypoint
# This creates a public secure URL that your Gradio Space can access via standard requests
@app.function(image=image)
@modal.fastapi_endpoint(method="POST")
def api(payload: ChatLibrary): # Use the Pydantic model here
    # FastAPI automatically validates and parses the JSON body into payload.messages
    server = NemotronServer()
    ai_response = server.chat_generation.remote(payload.messages)
    return {"response": ai_response}