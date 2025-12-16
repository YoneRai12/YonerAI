@echo off
title ORA vLLM Server (INSTRUCT - Default)
echo.
echo ===================================================
echo  Starting Qwen3-VL-30B-A3B-Instruct (Local Optimal)
echo  Features: Conversation, Tools, Long Context
echo ===================================================
echo.

wsl -d Ubuntu-22.04 bash -c "HF_HOME=/mnt/l/ai_models/huggingface python3 -m vllm.entrypoints.openai.api_server --model /mnt/l/ai_models/huggingface/QuantTrio_Qwen3-VL-30B-A3B-Instruct-AWQ --quantization awq --dtype half --gpu-memory-utilization 0.90 --max-model-len 8192 --enforce-eager --disable-custom-all-reduce --tensor-parallel-size 1 --host 0.0.0.0 --port 8001 --served-model-name Qwen3-VL-30B-Instruct --trust-remote-code"

echo.
pause
