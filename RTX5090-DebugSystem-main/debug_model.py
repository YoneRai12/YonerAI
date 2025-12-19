import torch
from transformers import AutoTokenizer, AutoModelForImageTextToText, BitsAndBytesConfig, AutoConfig
from peft import PeftModel
import os

MODEL_ID = "mistralai/Ministral-3-14B-Instruct-2512"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ADAPTER_PATH = os.path.join(SCRIPT_DIR, "checkpoints", "final_adapter")

def main():
    print("=== DEBUG START ===")
    
    # 1. Load Tokenizer
    print("Loading Tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    # Check special tokens
    print(f"BOS: {tokenizer.bos_token} ({tokenizer.bos_token_id})")
    print(f"EOS: {tokenizer.eos_token} ({tokenizer.eos_token_id})")
    
    # Check ChatML tokens
    text = "<|im_start|>user\nHello<|im_end|>"
    tokens = tokenizer(text)["input_ids"]
    print(f"Tokenized ChatML: {tokens}")
    print(f"Decoded: {tokenizer.decode(tokens)}")

    # 2. Load Base Model (Native - No BitsAndBytes)
    print("\nLoading Base Model (Native)...")
    
    # Do NOT strip config. Let Transformers handle the native FP8/BF16.
    # The RTX 5090 has 32GB VRAM. 
    # 14B Params @ FP8 = ~14GB. @ BF16 = ~28GB.
    # It should fit natively.
    
    try:
        model = AutoModelForImageTextToText.from_pretrained(
            MODEL_ID,
            device_map="auto",
            trust_remote_code=True,
            torch_dtype=torch.bfloat16 # Try standard BF16 first (libraries usually handle FP8->BF16 on-the-fly)
        )
    except Exception as e:
        print(f"\n[ERROR] Native Load Failed: {e}")
        # Fallback to try forcing standard config if FP8 fails
        print("Retrying with forced config override (Danger Zone)...")
        config = AutoConfig.from_pretrained(MODEL_ID, trust_remote_code=True)
        if hasattr(config, "quantization_config"):
            del config.quantization_config
        model = AutoModelForImageTextToText.from_pretrained(
            MODEL_ID,
            config=config,
            device_map="auto",
            trust_remote_code=True,
            torch_dtype=torch.bfloat16
        )
    
    # 3. Test Base Model Generation
    print("\n[Test 1] Base Model Output (Should be intelligible English/Japanese)")
    prompt = "Describe the purpose of AI."
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    if "token_type_ids" in inputs: del inputs["token_type_ids"]
    
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=20, pad_token_id=tokenizer.eos_token_id)
    print("Base Output:", tokenizer.decode(out[0], skip_special_tokens=False))
    
    # 4. Load Adapter
    print(f"\nLoading Adapter from {ADAPTER_PATH}...")
    try:
        model = PeftModel.from_pretrained(model, ADAPTER_PATH)
        print("Adapter Loaded.")
    except Exception as e:
        print(f"Failed to load adapter: {e}")
        return

    # 5. Test Adapter Generation
    print("\n[Test 2] Adapter Output (ChatML Prompt)")
    prompt_text = "<|im_start|>user\nお前誰？<|im_end|>\n<|im_start|>assistant\n"
    inputs = tokenizer(prompt_text, return_tensors="pt").to(model.device)
    if "token_type_ids" in inputs: del inputs["token_type_ids"]

    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=50, pad_token_id=tokenizer.eos_token_id)
    print("Adapter Output:", tokenizer.decode(out[0], skip_special_tokens=False))

if __name__ == "__main__":
    main()
