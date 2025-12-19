import torch
from transformers import AutoTokenizer, AutoModelForImageTextToText
from peft import PeftModel
import os

# Configuration
MODEL_ID = "mistralai/Ministral-3-14B-Instruct-2512"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ADAPTER_PATH = os.path.join(SCRIPT_DIR, "checkpoints", "final_adapter")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "hub", "Ministral-3-14B-ORA")

def main():
    print(f"Loading Base Model: {MODEL_ID}...")
    # Load in BF16 (Native) - Do NOT use 4-bit for merging if possible, but 14B fits in 24GB BF16? 
    # 14B * 2 bytes = 28GB. It might be tight on 32GB VRAM if loaded fully.
    # We should merge on CPU or use device_map="auto" (which might shard).
    # Ideally for merging we want full precision.
    # Let's try CPU offload if needed.
    
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
        
        # Sanitize config to remove native FP8 settings
        from transformers import AutoConfig
        config = AutoConfig.from_pretrained(MODEL_ID, trust_remote_code=True)
        if hasattr(config, "quantization_config"):
            del config.quantization_config
            
        # Load base model in BF16
        model = AutoModelForImageTextToText.from_pretrained(
            MODEL_ID,
            config=config,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            trust_remote_code=True,
            low_cpu_mem_usage=True
        )
    except Exception as e:
        print(f"Error loading base model: {e}")
        return

    print(f"Loading LoRA Adapter from {ADAPTER_PATH}...")
    model = PeftModel.from_pretrained(model, ADAPTER_PATH)

    print("Merging adapter into base model...")
    model = model.merge_and_unload()

    print(f"Saving merged model to {OUTPUT_DIR}...")
    model.save_pretrained(OUTPUT_DIR, safe_serialization=True)
    tokenizer.save_pretrained(OUTPUT_DIR)
    
    print("Done. You can now serve this model with vLLM.")

if __name__ == "__main__":
    main()
