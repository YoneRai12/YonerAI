import torch
from transformers import AutoTokenizer, AutoModelForImageTextToText, BitsAndBytesConfig
from peft import PeftModel, PeftConfig
import os

# Configuration
MODEL_ID = "mistralai/Ministral-3-14B-Instruct-2512"
# Resolve path relative to this script location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ADAPTER_PATH = os.path.join(SCRIPT_DIR, "checkpoints", "final_adapter")

def main():
    print(f"Loading Base Model: {MODEL_ID}...")
    
    # Load config first to STRIP quantization info (forcing standard BFloat16 base for 4-bit override)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    
    # 2. Sanitize Config
    from transformers import AutoConfig
    base_config = AutoConfig.from_pretrained(MODEL_ID, trust_remote_code=True)
    if hasattr(base_config, "quantization_config"):
        del base_config.quantization_config

    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
        model = AutoModelForImageTextToText.from_pretrained(
            MODEL_ID,
            config=base_config,               # Pass sanitized config
            quantization_config=bnb_config,       # Force 4-bit config
            device_map="auto",
            trust_remote_code=True
        )
    except Exception as e:
        print(f"Error loading base model: {e}")
        return

    print(f"Loading LoRA Adapter from {ADAPTER_PATH}...")
    try:
        model = PeftModel.from_pretrained(model, ADAPTER_PATH)
    except Exception as e:
        print(f"Error loading adapter (Did training finish?): {e}")
        return

    print("\n=== Model Verification Start ===\n")

    # Test Scenarios (Phase 2 Capabilities)
    test_prompts = [
        "お前誰？",                                      # Identity
        "@Spammer123 をBANして",                        # Moderation
        "3分後にカップラーメンのリマインダーセットして",      # Utility
        "Bling-Bang-Bang-Born 流して",                  # Media
        "今日の東京の天気教えて"                          # Search
    ]
    
    system_prompt = "You are ORA, an AI assistant. You can use tools to help the user. Answer in Japanese."

    for prompt in test_prompts:
        # Format for Mistral ([INST] ... [/INST]) - Matches training data
        prompt_text = f"<s>[INST] {system_prompt}\n\n{prompt} [/INST]"
        
        inputs = tokenizer(prompt_text, return_tensors="pt").to(model.device)
        if "token_type_ids" in inputs:
            del inputs["token_type_ids"]

        with torch.no_grad():
            outputs = model.generate(
                **inputs, 
                max_new_tokens=100, 
                pad_token_id=tokenizer.eos_token_id
            )
        
        output_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        # Extract response part (naive split for demo)
        output_text = tokenizer.decode(outputs[0], skip_special_tokens=False) # Keep special tokens to see structure
        print(f"RAW OUTPUT: {output_text}")
        
        # Try a more robust split (by assistant header if possible, or just print all)
        # For now, let's just show the raw output to debug
        # response_only = output_text.split(prompt)[-1].strip()

        # print(f"Q: {prompt}")
        # print(f"A: {response_only}")
        print("-" * 50)

    print("\n=== Verification Complete ===")

if __name__ == "__main__":
    main()
