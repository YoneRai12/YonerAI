@echo off
title ORA vLLM Server (GAMING MODE)
echo.
echo ===================================================
echo  Starting vLLM Server (GAMING MODE)
echo  Model: Qwen/Qwen2.5-VL-7B-Instruct-AWQ
echo ===================================================
echo.

wsl -d Ubuntu-22.04 bash -c "HF_HOME=/mnt/l/ai_models/huggingface python3 -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-VL-7B-Instruct-AWQ --quantization awq --dtype half --gpu-memory-utilization 0.30 --max-model-len 4096 --enforce-eager --disable-custom-all-reduce --tensor-parallel-size 1 --host 0.0.0.0 --port 8001 --served-model-name Qwen3-VL-30B-Instruct --trust-remote-code"

pause
