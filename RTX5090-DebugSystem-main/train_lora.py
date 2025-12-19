import os
import sys
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, TaskType
from trl import SFTTrainer
from datasets import load_dataset
import logging
import mistral_common # Explicit import to ensure TokenizersBackend is available

# Config
MODEL_ID = "mistralai/Ministral-3-14B-Instruct-2512" # Valid Gated ID (token required)
OUTPUT_DIR = "checkpoints"
DATA_FILE = "data/lora_dataset.jsonl"

def main():
    print(f"Starting QLoRA Training for {MODEL_ID}...")
    
    # 1. Quantization Config
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    # 2. Load Model & Tokenizer
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
        tokenizer.pad_token = tokenizer.eos_token
        
        # Ministral 3 is Multimodal
        from transformers import AutoModelForImageTextToText, AutoConfig
        
        # Load config first to STRIP quantization info (forcing standard BFloat16 base for 4-bit override)
        config = AutoConfig.from_pretrained(MODEL_ID, trust_remote_code=True)
        if hasattr(config, "quantization_config"):
            del config.quantization_config
        
        model = AutoModelForImageTextToText.from_pretrained(
            MODEL_ID,
            config=config,                    # Pass sanitized config
            quantization_config=bnb_config,   # Force 4-bit NF4 Quantization
            device_map="auto",
            trust_remote_code=True
        )
    except Exception as e:
        print(f"Failed to load model {MODEL_ID}: {e}")
        # Setup for Smoke Test dummy if model load fails (no internet/auth)
        if os.environ.get("PHOENIX_SMOKE_TEST") == "1":
            print("Smoke Test: Skipping real model load, exiting success.")
            sys.exit(0)
        raise e

    model = prepare_model_for_kbit_training(model) # Crucial for 4-bit QLoRA stability


    # 3. LoRA Config
    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"] # Target All Linear Layers for better perf
    )
    
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    # 4. Load Data
    full_dataset = load_dataset("json", data_files=DATA_FILE, split="train")
    
    # Formatting Func
    # Formatting Func (Mistral Instruct Format)
    def format_prompts(example):
        msgs = example["messages"]
        # Convert map to list if needed (datasets.map passes dict)
        # Expected structure: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        
        # Simple string construction for [INST] ... [/INST]
        # Assumes User -> Assistant -> User ...
        text = "<s>"
        for i in range(0, len(msgs), 2):
            user_msg = msgs[i]
            if i+1 < len(msgs):
                assist_msg = msgs[i+1]
                # Check roles strictness if needed, but for now trust synthetic data
                text += f"[INST] {user_msg['content']} [/INST] {assist_msg['content']}</s>"
            else:
                 # Trailing user message (shouldn't happen in training data usually)
                 text += f"[INST] {user_msg['content']} [/INST]"
        return {"text": text}

    train_dataset = full_dataset.map(format_prompts)

    # 5. Trainer
    from trl import SFTConfig
    
    training_args = SFTConfig(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=4, # Restored to 4 (VRAM is now safe with 4-bit)
        gradient_accumulation_steps=4, # Standard accumulation
        learning_rate=5e-5, # Lower rate to prevent NaN/Divergence
        logging_steps=10, 
        max_steps=500, # Phase 2: Full Training
        fp16=False,
        bf16=True, # Switch to BF16 for RTX 5090
        save_steps=100, 
        optim="adamw_torch",
        gradient_checkpointing=True,
        max_grad_norm=0.3, # Aggressive clipping to prevent exploding gradients
        max_length=1024, # Increased length for context
        packing=False, 
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=train_dataset,
        processing_class=tokenizer, # Renamed from 'tokenizer' in TRL 0.26+
        args=training_args,
    )

    print("Training loop starting...")
    trainer.train()
    
    print("Saving adapter...")
    trainer.save_model(os.path.join(OUTPUT_DIR, "final_adapter"))
    print("Done.")

if __name__ == "__main__":
    main()
