# Debugging and Enhancing ORA Bot

- [x] Fix Search/Tool Loop in [ora.py](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py)
    - [x] Issue: Tool output is sent directly to user instead of being summarized by LLM.
    - [x] Fix: Implement ReAct loop (LLM -> Tool -> LLM -> Response) + Prompt Engineering.
- [x] Relax TTS Restrictions in [media.py](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/media.py)
    - [x] Issue: Only reads messages from users in VC.
    - [x] Fix: Removed `author.voice` check in [on_message](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py#1904-2027) and improved [VoiceManager](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/utils/voice_manager.py#174-599).
- [x] Improve UX/Status Messages
    - [x] Issue: "Using tool" status is too short/invisible.
    - [x] Fix: Add explicit typing/status updates with 1.5s delay.
- [x] Fix Start-up/Runtime Crashes
    - [x] Issue: `AttributeError` in `music_play` and `NameError: asyncio` in [media.py](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/media.py).
    - [x] Fix: Ensure `Context` is passed to [play_from_ai](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/media.py#735-760) and add missing imports.
- [x] Fix Infinite Tool Loop
    - [x] Issue: LLM repeats tool call 3 times and output raw text.
    - [x] Fix: Deduplicate tool calls, stop loop, hide raw output.
    - [x] Fix: Correct message role stricture (User-Assistant-User) to prevent hallucination.
- [x] Investigate CPU Usage (Fan Noise)
    - [x] Identify heavy listener (Duplicate [on_message](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py#1904-2027))
    - [x] Fix duplicate listener
    - [x] Kill zombie processes (15+ instances found)
- [x] Migrate to `faster-whisper`
    - [x] Install `faster-whisper`
    - [x] Refactor [voice_recv.py](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/voice_recv.py)
    - [x] Verify GPU/CPU utilization (Confirmed: Loaded on GPU)
- [x] Investigate Image Generation Issues
    - [x] Analyze "Quality" parameter handling in `image_gen.py` (Fixed upscaler)
    - [x] Debug generation failure (Verified: SD WebUI is offline)
    - [x] Fix effective resolution/quality settings (Switched to Latent upscaler)
- [x] Investigate Image Quality Settings
    - [x] Locate `generate_image` logic in [ora.py](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py).
    - [x] Verify `ResolutionSelectView` parameters.
    - [x] Ensure `hr_scale` is applied correctly (Fixed: Changed invalid 'Latent' upscaler to 'R-ESRGAN 4x+').
- [x] Finalize System Automation & Startup
    - [x] Update [run_l.bat](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/run_l.bat) to launch 5 windows (API, UI, SD, Bot, Launcher)
    - [x] Handle corrupt SD model (Identified & Auto-recovered)
    - [x] Clarify launcher "Success" messagest".
- [x] Investigate Access Control
    - [x] Issue: "Some users cannot use it".
    - [x] Fix: Check permissions/error handling.
- [x] Debug Vision Input (Processing Attachments) [2025-12-16]
- [x] Fix System Check Command (Diagnostics) [2025-12-16]
- [x] Fix JSON Leakage in Chat [2025-12-16]
- [x] Implement Strict Context Reset (Mention = New, Reply = Continue) [2025-12-16]
- [x] Fix Context Length Overflow (Truncate to 1200 chars) [2025-12-16]
- [x] Fix Command Ignored (Stop Deleting JSON Code Blocks) [2025-12-16]
- [x] Fix VC Hijacking & Enable Cross-Channel Read (Sticky Voice) [2025-12-16]
- [/] Verify Fixes

# Enhance VC Features

- [x] Implement VC Join/Leave Announcements
    - [x] Update [media.py](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/media.py): [on_voice_state_update](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/media.py#609-674) to speak "User joined/left".
- [x] Enable Per-User Voice Customization
    - [x] Verify `change_voice` tool in [ora.py](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py).
    - [x] Update [voice_manager.py](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/utils/voice_manager.py) to persist/use user speaker settings.
- [x] Auto-Enable Reading on Join
    - [x] Update [ora.py](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py) (`join_voice_channel`) to set auto-read flag.
- [x] Suppress URLs in TTS
    - [x] Update [voice_manager.py](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/utils/voice_manager.py) ([clean_for_tts](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/utils/voice_manager.py#544-562)) to replace URLs with "URL省略".
- [x] Truncate Long TTS Messages
    - [x] Update [voice_manager.py](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/utils/voice_manager.py) ([clean_for_tts](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/utils/voice_manager.py#544-562)) to truncate at 60 chars + "以下略".
    - [x] Ensure [play_tts](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/utils/voice_manager.py#262-331) actually calls [clean_for_tts](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/utils/voice_manager.py#544-562).
- [x] Replace Custom Emojis in TTS
    - [x] Update [voice_manager.py](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/utils/voice_manager.py) ([clean_for_tts](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/utils/voice_manager.py#544-562)) to replace `<:name:id>` with "絵文字".
- [x] Switch LLM Model
    - [x] Update [src/config.py](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/config.py) default model to `mistralai/ministral-3-14b-reasoning`.
- [x] Verify Image Recognition
    - [x] Confirmed [ora.py](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py) has attachment processing -> `image_tools.analyze_image_v2` pipeline.
    - [x] **Enforced Vision Usage**: Updated system prompt to explicitly tell the LLM it can see images and shouldn't use tools for identification.

# Fix Crash & Add User Search

- [x] Fix Role Alternation Crash (Start with User)
    - [x] Update [handle_prompt](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py#2593-3048) in [ora.py](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py) to insert dummy user message if history starts with Assistant.
- [x] Add `find_user` Tool
    - [x] Update [_get_tool_schemas](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py#2188-2591) in [ora.py](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py) to add `find_user`.
    - [x] Update [_execute_tool](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py#803-1775) in [ora.py](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py) to implement search logic (including offline members).
    - [x] Update [_execute_tool](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py#803-1775) in [ora.py](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py) to implement search logic (including offline members).
    - [x] **Enhance**: Add support for User IDs and Mention strings (e.g. `<@123>`) to robustly find specific users.

# Fix Language Hallucinations

- [x] Enforce Japanese Output
    - [x] Update [handle_prompt](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py#2593-3048) dummy message to Japanese [(会話を継続します)](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/media.py#494-531).
    - [x] Strengthen [_build_system_prompt](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py#667-775) to explicitly forbid non-Japanese languages.

# Fix Tool Format Hallucinations

- [x] Fix `[TOOL_CALLS]` Output
    - [x] Update [_build_system_prompt](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py#667-775) to strictly forbid `[TOOL_CALLS]` format.
    - [x] Update [handle_prompt](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py#2593-3048) / [_extract_json_objects](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py#1863-1905) to regex parse `[TOOL_CALLS] name(ARGS){json}` as a fallback.
    - [x] **Refine Parse**: Regex failed on `[TOOL_CALLS]name[ARGS]{}`. Allow square brackets for ARGS too.
    - [x] **Priority Logic**: Updated [_extract_json_objects](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py#1863-1905) to check for `[TOOL_CALLS]` pattern *before* standard JSON extraction.

# Implement Status Counts

- [x] Enable `intents.presences`
    - [x] Update [src/bot.py](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/bot.py) to set `presences=True`.
- [x] Update `get_server_info`
    - [x] Determine Status Counts (Online/Idle/DND).
    - [x] **Device Stats**: Add breakdown of Mobile/Desktop/Web users.

# Fix Tool Selection Consistency

- [x] Reinforce `get_server_info` Usage
    - [x] Update [_build_system_prompt](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py#667-775): Explicitly map "online/away/member count" queries to `get_server_info`.
    - [x] Add negative constraint: Do NOT use [get_voice_channel_info](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py#653-666) for server-wide stats.

# Implement Local Stable Diffusion

- [x] Configuration
    - [x] Add `sd_api_url` to [src/config.py](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/config.py) (Default: `http://127.0.0.1:7860`).
    - [x] Add `SD_API_URL` to [.env](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/.env).
- [x] Implement `generate_image` Tool
    - [x] Add tool schema to [_get_tool_schemas](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py#2188-2591) in [ora.py](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py).
    - [x] Implement tool logic in [_execute_tool](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py#803-1775):
        - [x] Send POST request to `/sdapi/v1/txt2img`.
        - [x] Decode Base64 response.
        - [x] Send image to Discord.
        - [x] Decode Base64 response.
        - [x] Send image to Discord.

# Improve Image Generation Quality

- [ ] Download High-Quality Model
    - [x] Create `L:\AI_Models\Stable-diffusion` directory.
    - [x] **Manual Action**: Download `MeinaMix_V11.safetensors` to `L:\AI_Models\Stable-diffusion` (User verified).
- [x] Configure SD to use L Drive
    - [x] Instruction: Add `--ckpt-dir "L:\AI_Models\Stable-diffusion"` to `webui-user.bat`.
- [x] Implement Model Management Tools
    - [x] Add `get_current_model` tool (Read /sdapi/v1/options).
    - [x] Add `change_model` tool (POST /sdapi/v1/options with `sd_model_checkpoint`).

# Switch to Realistic (Photo) Model
- [ ] Manual Download: `BeautifulRealisticAsians_V7` (User Request: "Not real at all").
- [x] **Manual Download**: `Realistic_Vision_V6.0_B1` (User Request: "No Bishoujo").
- [x] Improve Generation Parameters
    - [x] Add `width`, `height` parameters to `generate_image`.
    - [x] Improve default `negative_prompt`.
    - [x] Increase `steps` to 30.

# Interactive Image Generation UI
- [x] Create `ImageGenView` (Discord UI)
    - [x] Step 1: Aspect Ratio Selection (Square, Portrait, Landscape).
    - [x] Step 2: Quality/Resolution Selection (FHD, WQHD, 4K).
    - [x] Logic: Map selection to `width`, `height`, and `enable_hr` (Highres Fix) parameters.
- [x] Implement VRAM & Concurrency Manager
    - [x] Add `is_generating_image` state to [ORACog](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py#120-3127).
    - [x] Update [handle_prompt](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py#2593-3048) to:
        - [x] Check state.
        - [x] If generating: Reply "Waiting for image..." and queue message.
        - [x] If free: Process normally.
    - [x] Add `unload_llm` to `LLMClient` (Implied via queue locking).
- [x] Update `generate_image` tool
    - [x] Change logic to instantiate `ImageGenView`.
    - [x] Connect View callback to VRAM Manager (Lock -> Unload LLM -> Gen -> Unlock -> Process Queue).

# Safety & Content Filtering
- [x] Harden `negative_prompt` (Force SFW).
    - [x] Add [(nsfw:2.0), (nude:2.0), (naked:2.0), (sexual:2.0)](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/media.py#494-531) to hidden negatives.
- [ ] Research/Download Safe Model.
- [ ] Research/Download Safe Model.
- [ ] Research/Download Safe Model.
    - [ ] **Priority**: Find a "Strictly SFW" model (User request: "Absolutely no NSFW").
    - [ ] Current Status: Official HF links are fragile/gated. Checking Civitai mirrors.
    - [ ] Option A: `stable-diffusion-2-1` (Official) via Browser.
    - [ ] Option B: `Realistic Vision` + Strict Filter (Current).

# Implement High Quality Model (Juggernaut XL) [User Request]
# Implement High Quality Model (Juggernaut XL) [User Request]
- [/] Download Juggernaut XL v9
    - [x] Create download script.
    - [x] Script failed/cancelled.
    - [ ] **Manual Download Required**: User found page. Waiting for download to `L:\AI_Models\Stable-diffusion`.
- [x] Update Code
    - [x] `image_gen.py` handles "XL" models correctly (verified).
- [ ] User Verification
    - [ ] Restart Bot.
    - [ ] Switch to Juggernaut XL.
    - [x] Add Model Detection logic (Check `sd_model_checkpoint`).
    - [x] Adjust Default Resolution to 1024x1024 (Native).
    - [x] Adjust CFG Scale to 4.5 (SD3.5 Standard).
    - [x] Disable Hires Fix for SD3.5 (Not needed/Too heavy).
- [x] Update UI (`AspectRatioSelectView`)
    - [x] Add "Standard (1024px)" options for SD3.5.

# Maximum Safety Measures
- [x] Implement Pre-Generation Keyword Blocklist.
    - [x] Block "nsfw, nude, hentai, r18" etc. in user prompt.
- [x] Implement "Safety Override" in `generate_image`.
    - [x] Inject Positive: [(safe for work:1.5), (family friendly:1.2)](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/media.py#494-531).
    - [x] Inject Negative: [(nsfw:2.0)...](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/media.py#494-531) AND Smart Human Suppression (if not asked).

# Voice & Reliability
- [x] Fix Auto-Disconnect Logic.
    - [x] Increase timeout to 5 minutes.
    - [x] **New**: Prevent disconnect if Auto-Read (TTS) is active.
- [x] Fix "Ignore Join Command".
    - [x] Implement `join_voice_channel` tool logic in [ora.py](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py).

# Permissions
- [x] Allow ID `1069941291661672498` to create text channels (bypass admin check).
- [x] Allow `1069941291661672498` full system access (Admin equivalent).

# Bug Fixes (Recent)
- [x] **GPU Monitor**: Implemented `get_system_stats` extension for VRAM usage.
- [x] **Vision Hallucination**: Fixed issue where "Solve this" (image) triggered `music_play`.
    - [x] Update System Prompt to strictly forbid music tools for image analysis.
    - [x] **New**: Enable True Vision (Multimodal). Modified [ora.py](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py) to send Base64 image to LLM.
- [x] **Voice Crash**: Fixed `TimeoutError` when connecting to VC.
    - [x] Added try/except block to `voice_manager.ensure_voice_client`.
- [x] **Relpy Vision**: Support "Solve this" when replying to an image.
    - [x] Updated [on_message](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py#1904-2027) to fetch referenced message attachments and process them as context.
- [x] **Feature**: Play Previous Song
    - [x] Add [history](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/ora.py#1767-1853) list to [GuildMusicState](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/utils/voice_manager.py#165-173) (Limit 20)
    - [x] Implement [replay_previous](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/utils/voice_manager.py#509-537) in [VoiceManager](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/utils/voice_manager.py#174-599)
    - [x] Add implicit trigger for "Play previous" -> `replay_last`
- [x] **Inquiry**: Check Queue Limit
    - [x] Verified: No hard limit (Python list). Limits are memory-bound.

- [x] **Documentation**: Update & Push README
    - [x] Rewrite [README.md](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/README.md) with features (Music, Safety, Roles)
    - [x] Add roadmap: Google OAuth, SQL DB, Web Dashboard (Chat/Images)
    - [x] Push changes to GitHub
    - [x] Push hanges to GitHub
    - [x] Deep Dive: Rewrite REDOMI with "Amazingness" and "Architecture" details

- [x] **Feature**: Auto-Leave Empty VC
    - [x] Verify [on_voice_state_update](file:///c:/Users/YoneRai12/Desktop/ORADiscordBOT-main3/src/cogs/media.py#609-674) logic
    - [x] Ensure it disconnects when only bots are left
    - [x] Add immediate disconnect or short timer

# Implement ComfyUI (FLUX.2 Support) [User Request]
- [ ] **Data Gathering**:
    - [x] Strategy: FP8 Workflow + Weight Streaming (User Provided).
    - [x] Hardware: RTX 5090 (Assumed 24/32GB -> FP8 Plan).
- [ ] Install ComfyUI
    - [ ] Clone `ComfyUI` to `L:\ComfyUI`.
    - [ ] Install Requirements (`env: ORADiscordBOT_Env`).
    - [ ] Install `huggingface_hub` for downloading.
- [ ] Download Models (User Script)
    - [ ] Create `download_flux.ps1`.
    - [ ] Execute Download (User Auth Required).
        - [ ] `mistral_3_small_flux2_fp8.safetensors` -> `text_encoders`
        - [ ] `flux2_dev_fp8mixed.safetensors` -> `diffusion_models`
        - [ ] `flux2-vae.safetensors` -> `vae`
- [ ] Verification
    - [ ] Load FP8 Workflow.
    - [ ] Generate 1024x1024 "cat photo".
    - [ ] Implement NSFW Gate (Safety Checker).
- [ ] ORA Integration
    - [ ] Update `run_l.bat` to launch ComfyUI.
    - [ ] **Implementation**: Create `ComfyWorkflow` class (`src/utils/comfy_client.py`).
    - [ ] **LLM Logic**:
        - [x] Implement `LLM Safety Judge` (Classify R18 vs Safe).
    - [x] Implement `LLM Safety Judge` (Classify R18 vs Safe).
    - [x] Implement `Style Router` (Detect Animal/Future/Real/Nature from text).
    - [X] Inject Style-specific Prompt Enhancers (e.g. "bioluminescent" for Future).
    - [x] **User Templates**: Create manual JSON files (`Template_*.json`) in project root for user.
    - [x] **Smart Intent Recognition**: Detect "Make an image" intent in normal chat (@ORA) and trigger generation automatically.
    - [x] **Fix FLUX Aspect Ratios**: Added PC/TV (16:9), Cinema (21:9), Smartphone (9:16).
    - [x] **Fix FLUX Model Mismatch**: Patched ComfyUI detection to align with 6144-dim checkpoint.
    - [x] **Flux Model Integration**
        - [x] Resolve `vec_in_dim` error <!-- id: 5 -->
        - [x] Resolve `hidden_size` mismatch (Force 6144 Upgrade) <!-- id: 6 -->
        - [x] Fix `IndentationError` in patch script <!-- id: 7 -->
        - [/] **Verify Image Output**: Debugging why `SaveImage` (Node 9) is not returning output.
    - [x] **Pivot to Standard FLUX.2 (RTX 5090 Optimized)**
        - [x] Revert "Force 6144" hack (Standard model is 3072-dim).
        - [x] Create `update_comfy.bat` to update ComfyUI (Fix Unknown Node).
        - [x] Restore `flux_api.json` to use `flux2_dev_fp8mixed.safetensors` (UNET).
        - [x] Fix DualCLIPLoader: Set `clip_name`=Mistral (Single).
        - [x] Update JSON: Change `type: flux` to `type: flux2` (Fix HTTP 400).
        - [x] Dependencies: Run `install_reqs.bat` (Fix Frontend Warnings).
        - [x] Run `update_comfy.bat`.
        - [ ] Restart `run_l.bat` and Verify.

- [x] **Refine Intent Recognition (Fix "I felt the will" Hallucinations)**
    - [x] Strict Rule: If attachments exist -> BLOCK Image Gen (Vision Priority).
    - [x] Strict Rule: If text does not contain "画像生成" -> BLOCK Image Gen.
    - [x] Update System Prompt to reflect strict rules.

- [x] **Diagnose ComfyUI Connection (WinError 10061)**
    - [x] Check Port 8188: CLOSED (ComfyUI is down).
    - [x] Notify User: Restart Required.
    - [x] Run Debugger and Capture Crash Log (Screenshot Confirmed: Silent Exit).
    - [x] **Still Crashing on Load (Values Normal)**: Process Silent Exit during Flux Load.
    - [x] Cause Identified: Model is 35GB (Flux2) > 32GB VRAM.
    - [x] **Fix Applied**: Updated `run_l.bat` with `--lowvram --disable-cuda-malloc`.
    - [x] **Fix Applied**: Downgraded PyTorch to Stable (cu128) via venv reinstall.
    - [x] **Fix Applied**: Updated `flux_api.json` CLIPLoader to `type: flux2`.
    - [x] **Crash at 100% (VAE Decode)**: Detected silent exit after sampling.
    - [x] **Fix Applied**: Switched to `VAEDecodeTiled` (tile_size: 512) in `flux_api.json`.
    - [x] **New Params Fixed**: Added `overlap`, `temporal_size` to Tiled Decode.
    - [x] **Validation Fix**: Set `temporal_size: 8`, `temporal_overlap: 4` (Min reqs).
    - [x] **Verification**: Generation confirmed running (13/20 it).
    - [x] **Verification**: Generation confirmed running (13/20 it).
    - [x] **Optimization**: Switched to `flux1-dev-fp8` (17GB) + CheckpointLoader.
    - [x] **Performance**: Restored `--normalvram` (Safe for 17GB Model).
    - [x] **Bug Fix**: Discovered Prompt/Dimensions were not being passed to ComfyUI.
    - [x] **Fix**: Updated `comfy_client.py` and `image_gen.py`. Added Auto-Translate.
    - [x] **Final Test**: Success! Ratio/Prompt correct. 5.86s/it.
- [x] **UI Refinements**
    - [x] Add 16:9 / 21:9 Aspect Ratios <!-- id: 2 -->
    - [x] Add Resolution (FHD/4K) with time estimates <!-- id: 8 -->
    - [x] Implement "Auto Style" with LLM classification <!-- id: 9 -->
- [x] **Reliability & Silence**
    - [x] **VRAM Management**:
        - [/] Verify `_execute_tool` handles `tts_speak` and `generate_video` correctly <!-- id: 10 -->
    - [x] Check `tts_speak` implementation (Falls back to System Voice) <!-- id: 11 -->
    - [x] Check `generate_video` implementation (Placeholder) <!-- id: 12 -->
    - [x] Check `segment_objects` (SAM3) implementation (Mock) <!-- id: 13 -->
- [x] Debug Music Playback "Search then Play" issue
    - [x] Inspect `MediaCog.play_from_ai`
    - [x] Inspect `VoiceManager.ensure_voice_client` (Fixed Sticky Behavior)
    - [x] Implement Direct Bypass for "画像生成" commands <!-- id: 12 -->
    - [x] **Error Handling**:
        - [x] Suppress "WebSocket waiting failed" spam <!-- id: 13 -->
        - [x] Fix Server Crash: Removed `--highvram` flag to prevent OOM with 6144-dim model.
    - [x] **Polishing**:
        - [x] Fixed `AttributeError` (LLM alias).
        - [x] Suppressed double-reply (Silent Completion).
        - [x] Added Quality Selection (Standard/High).
        - [x] Implemented "Auto Style" with LLM Decision -> VRAM Unload flow.
        - [x] Verified `IndentationError` fix.


# [CANCELLED] Implement WebUI Forge (FLUX.2 Support) [User Request]
- [x] Create `install_forge.bat`.
- [ ] Execute installation (Git Clone -> Venv Setup).
- [ ] **Manual Action**: User to copy FLUX.2 model to `L:\WebUI_Forge\models\Stable-diffusion`.

# Implement Video Generation (AnimateDiff) [User Request]
- [ ] Install AnimateDiff Extension
    - [ ] Create `install_animatediff.bat`.
    - [ ] Execute installation (Git Clone).
    - [ ] Download Motion Module (`v3_sd15_mm.ckpt`) to `extensions/sd-webui-animatediff/model`.
- [ ] Implement `generate_video` Tool
    - [ ] Update `_get_tool_schemas` in `ora.py` (duration, fps).
    - [ ] Implement `generate_video` logic in `_execute_tool` (Text-to-Video).
    - [ ] Handle `alwayson_scripts` payload.
    - [ ] Send video (MP4/GIF) to Discord.

# Improvement Phase (User Requests)

- [ ] **UI/UX Overhaul**: Interactive & Visual
    - [x] **Card-Style Responses**: Use Discord Embeds for cleaner AI replies.
    - [x] **Tool Usage Visualization**: Show status updates (e.g., `[🔍 Searching...]`) in real-time.
    - [x] **Status Animation**: Dynamic message updates.

- [x] **Security & Stability** (Urgent)
    - [x] **Loop Breaker**: Prevent tool spam/infinite loops (e.g. create_file spam).
    - [x] **Input Validation**: Block garbage args.

- [ ] **Features: Information Feeds** (API)
    - [ ] **Earthquake Alerts**: Implement P2Pquake API.
    - [ ] **Daily News**: Fetch daily news summaries.

- [ ] **AI & Intelligence Upgrades**
    - [ ] **Google Vision Integration**: Fallback for high-precision Analysis.
    - [ ] **Search Accuracy** & **Model Enhancement**.

- [ ] **System Integration**
    - [ ] **WebSync**: Connect Discord to Web Dashboard.
m the working environment (`.venv`).
    - [x] Added startup probe in `MediaCog` to warn if Opus is missing.
    - [x] **Automated Search**: Scanned `C:\Users\YoneRai12` for `*opus*.dll` -> 0 results.
    - [x] **Compatibility**: Updated `media.py` to accept `libopus-0.dll` (standard name) too.
    - [x] **Path Logic**: Patched `media.py` to use `os.path.abspath` (Required for Windows Python 3.8+).
    - [x] **Action Required**: User downloaded `libopus-0.dll`. System Verified.
    - [x] **Connection Stability**: Implemented 3-retry loop for Voice Handshake to prevent random timeouts.
    - [x] **Verification**: Bot online, Opus loaded, Handshake logic enforced.
    - [x] **Error Reporting**: Replaced generic "Not joined" with detailed error messages (Timeout/Permissions) in both Slash Command and LLM Tool.
    - [x] **Shutdown Fix**: Resolved `ValueError: a coroutine was expected` by making `src.bot.main` async.
    - [x] **Co-location Auto-Read**: Bot now reads from ANY channel if sender is in the same VC. Solves "It worked before" (restart amnesia).
    - [x] **Chat Trigger**: Added support for **Role Mentions** (`@ORA` role) in `on_message`. Fixes "No reaction/No logs" when using role tags.
    - [x] **Regex Cleaning**: Updated prompt cleaner to verify handling of `<@!ID>` (Nickname Pings) and `<@&ID>` (Role Pings).
    - [x] **Command Sync**: Forced `SYNC_COMMANDS=true` default. Fixes missing `/vc` commands.
    - [x] **Crash Fix**: Resolved `AttributeError: bool object has no attribute guild`.
        - [x] Removed incorrect `@app_commands.allowed_installs` decorators from `core.py`.
        - [x] Removed incorrect `allowed_installs=True` arguments from `ora.py` (Group constructor: privacy, memory).
        - [x] Removed incorrect decorators from `ora.py` (summarize, chat).
        - [x] Removed incorrect `allowed_installs=True` arguments from `core.py` (Group constructor: utility, system).
    - [x] **Logic Fix**: Resolved `UnboundLocalError: VoiceConnectionError` in `/vc` command.
        - [x] Defined `VoiceConnectionError` in `voice_manager.py`.
        - [x] Imported `VoiceConnectionError` in `media.py`.
- [x] **Documentation & Cleanup**
    - [x] **README.md**: Update with new features (Loop Breaker, Cards, Creator Lock).
    - [x] **GitHub Push**: Sync latest code. Vision, Voice, and Critical Opus dependency.
    - [x] Configured remote as `YoneRai12/ORA`.
    - [x] **Push to GitHub**: Fixed "Large File" error (removed `.venv`) and successfully pushed.
    - [x] **Enhanced Documentation**: Rewrote README to be "Cool & Detailed" with Architecture and Command Tables.
- [x] **Debugging**: Resolve Voice Connection Timeout.
    - [x] Modify `voice_manager.py` to aggressively cleanup stale voice states.
    - [x] **Observation**: User confirmed bot works on another server. Issue is isolated to specific Guild/Region.
    - [x] **Logic Fix**: Restored `@ORA` Tool Execution ("God Mode").
        - [x] Updated `_build_system_prompt` in `ora.py` to explicitly instruct LLM on JSON Tool Call format.
    - [x] **Language Fix**: Enforced Japanese replies.
        - [x] Added "CRITICAL INSTRUCTION: ALWAYS reply in JAPANESE" to System Prompt.
- [x] **Debugging**: Fix Vision/OCR and Tool Coexistence.
    - [x] Relax System Prompt to allow Natural Answers (Vision) vs Tool Calls.
    - [x] Verify `LLMClient` handles Multimodal `messages` payload correctly.
- [/] **Regression Logic Fixes**:
    - [x] **Language**: Forced Japanese instruction at END of message list to override history bias.
    - [x] **System Control**: Handled `AttributeError` in `AudioDevice` initialization to prevent Cog crash.
    - [x] **Triggers**: Added "IMPLICIT TRIGGERS" section to System Prompt to map "きて/流して" to tools.
    - [x] **Music Control**: Mapped "Repeat/Skip/Stop" to `music_control` tool actions in prompt.
    - [x] **Phase 2 Expansion**: Added detailed Usage Scenarios, Config tables, and Troubleshooting FAQ.

# Permissions Management

- [x] Implement Sub-Admin Role
    - [x] Define `SUB_ADMIN_ID` (`1307345055924617317`).
    - [x] Update `is_admin` or equivalent check to support multiple levels.
    - [x] **Tier 1 (Owner Only)**: `create_file` (Data Safety), `system_control` (User Request).
    - [x] **Tier 2 (Owner + Sub)**: `create_channel` (User Request).

# Fix Identity Lookup
- [x] Fix "Who is @User" Hallucination
    - [x] Update System Prompt Implicit Triggers ("Who is X" -> `find_user`).
    - [x] Update `find_user` Description to explicitly support Mentions/IDs.

# Fix Image Safety
- [x] Suppress Unintended Humans
    - [x] Expand `human_keywords` (people, guy, lady, portrait).
    - [x] Increase Negative Prompt Weight for humans (`2.0` from `1.5`).
    - [x] Increase Negative Prompt Weight for Bad Quality (`2.0` from `1.4`).

# Implement Timer & Alarm
- [x] Implement `set_timer` tool
    - [x] Schema: `seconds` (int), `label` (str)
    - [x] Logic: `asyncio.sleep` -> Reply/Sound
- [x] Implement `set_alarm` tool
    - [x] Schema: `time` (HH:MM), `label` (str)
    - [x] Logic: Calculate delay -> `asyncio.sleep` -> Reply/Sound

# Implement Server Mute/Deafen
- [x] Update `manage_user_voice` schema
    - [x] Add `mute`, `unmute`, `deafen`, `undeafen`
- [x] Implement logic
    - [x] use `member.edit(mute=True/False, deafen=True/False)`

# Enhance Image Safety
- [x] Strengthen `negative_prompt`
    - [x] Add explicit NSFW terms to hidden negative prompt.
- [x] Inject Safety Prompts
    - [x] Add `(safe for work:1.5)` to positive prompt if not present.
- [x] Set Default Safe Model
    - [x] Update `ora.py` to auto-set `v1-5-pruned-emaonly` on startup.

# Implement Points System
- [x] Update Storage (`src/storage.py`)
    - [x] Add `points` column (Lazy Migration).
    - [x] Implement `add_points`, `get_points`, `set_points`.
- [x] Implement Chat Logic (`src/cogs/ora.py`)
    - [x] Add `check_cooldown` logic.
    - [x] Award +1 point per message.
- [x] Implement VC Logic (`src/cogs/media.py`)
    - [x] Track Join Time in `on_voice_state_update`.
    - [x] Calc Duration on Leave -> Award +1 point/min.
- [x] Add Tools (`src/cogs/ora.py`)
    - [x] `check_points` tool.

# Refine Persona
- [x] Context-Aware Identity
    - [x] Removed "Character" trait for Creator.
    - [x] Added "Internal Knowledge" section with strict Condition (Only reveal if asked).

# Enable Voice Conversation
- [x] Ensure `handle_prompt` supports Voice Input
    - [x] Update `ora.py` to accept `is_voice` argument.
    - [x] Explain `/listen` command to user.

# Ambient Music Recognition
- [ ] Research & Propose Solution
    - [ ] Option A: Singing/Lyrics (Whisper -> LLM -> Search).
    - [ ] Option B: Humming (Needs Audio Fingerprinting API like ACRCloud/Shazam).
- [ ] Implement MVP (Lyrics Based)
    - [x] Update `process_audio_loop` (Verified: sends text to ORA).
    - [x] Prompt LLM to identify songs from lyrics (System Prompt Updated).

# Multi-User Voice Support
- [x] Refactor `VoiceSink` for concurrency
    - [x] Dictionary-based buffer `{user_id: UserData}`.
    - [x] Update `write` to route audio.
    - [x] Update `process_audio_loop` to check all buffers.

# Fix Image Recognition
- [x] Debug "I cannot see" Hallucination
    - [x] Issue: LLM claims blindness even when OCR/Description is present.
    - [x] Fix: Improved Prompt format (`[VISUAL CONTEXT]`) to force attention.
    - [x] Fix: Verified `enumerate` loop for Multi-Image support.

# Optimize Visual Payload
- [x] Implement Image Resizing
    - [x] Import `PIL` in `ora.py`.
    - [x] Resize large images (>1024px) to avoid token overflow.
    - [x] Convert to JPEG to reduce base64 string size.

# Implement Shiritori Game
- [x] Create `ShiritoriGame` Engine
    - [x] `src/utils/games.py`: Class to track history, validate words, handle "N" rule.
- [x] Implement `shiritori` Tool
    - [x] Schema: `action`, `user_word`, `user_reading`, `bot_word`, `bot_reading`.
    - [x] Logic: Validate User -> Validate Bot -> Update State -> Return Result.
- [x] Update System Prompt
    - [x] Add instructions for using the `shiritori` tool and providing readings.

# Optimize Voice Performance
- [x] Fix "CPU Roaring/No Reaction"
    - [x] Issue: Whisper running on CPU (FP32) causes 100% usage and lag.
    - [x] Issue: `voice_recv` RTCP packet spam hides logs.
    - [x] Fix: Suppress `discord.ext.voice_recv.reader` logs.
    - [x] Fix: Switch Whisper to `tiny`/`base` or use `faster-whisper` (int8) if possible.
    - [x] Fix: Increase silence threshold to prevent continuous processing.

# Migrate to L: Drive (GPU Support)
- [x] Create Environment
    - [x] Create `L:\ORADiscordBOT_Env`.
    - [x] Install PyTorch (CUDA 12.1).
    - [x] Install dependencies.
- [x] Create Startup Script
    - [x] Create `run_l.bat`.

# Optimize Environment & UX
- [x] Cleanup C: Drive
    - [x] Uninstall `torch` from System Python (C:).
- [x] Enhance Launcher
    - [x] Update `run_l.bat` with Auto-Restart Loop.
    - [x] Create Context Menu Shortcut ("Start ORA Bot").

# Model Optimization (Round 2)
- [/] **Transition to Flux 1 GGUF (12GB)**
    - [x] **Analysis**: 17GB Model + LLM residue caused swapping. User requested "Flux 2 15GB".
    - [x] **Solution**: Use `Flux.1-Dev-Q8_0.gguf` (12.8GB) + FP8 T5 (4.8GB).
    - [x] **LLM Fix**: Added `taskkill` nuclear option to `llm_client.py`.
    - [x] **Download**: Get GGUF and CLIP models.
    - [x] **Workflow**: Switch to `flux_gguf_api.json`.
    - [/] **Verify**: Restart and check VRAM usage. (User requested Pivot to vLLM).

# Migrate to vLLM (Linux/WSL2)
- [/] **Environment Check**
    - [x] User has Ubuntu 22.04 (Hyper-V/WSL).
    - [x] Verify WSL2 Version (`wsl --list --verbose` -> Version 2).
    - [x] Verify GPU Access in WSL (`nvidia-smi` -> 5090 Found).
- [ ] **Installation**
    - [/] Install vLLM in Ubuntu (`install_vllm.sh` Running).
    - [x] Configure ORA Bot (`src/config.py` updated to `localhost:8000`).
    - [x] Remove Toggle Logic (`image_gen.py` cleaned).
    - [ ] Create Startup Script (`start_vllm.bat` Created).
- [ ] **Integration**
    - [x] Launch vLLM Server. (User action required)
        - [x] Target: **Qwen/Qwen2.5-VL-32B-Instruct-AWQ** (High Perf Vision).
    - [x] **Toggle Logic (User Request)**:
        - [x] User rejected simultaneous run. ("Absolutely load and unload").
        - [x] Restore `image_gen.py` toggle logic.
        - [x] Implement `start_vllm` / `stop_vllm` via WSL commands.
        - [x] **New Architecture (5-Layer)**:
            - [x] Implement `ResourceManager` (Guard Dog).
            - [x] Integrate `switch_context` in `ora.py` / `image_gen.py`.
    - [x] **Registry & Launcher**:
        - [x] Migrate vLLM Cache to L: Drive.
        - [x] Fix Duplicate Context Menu Entries (Aggressive Clean).
        - [x] Register `ora` command and Right-Click Menu.

# Future Roadmap (User Requests)
- [ ] **Video Generation**: Implement AnimateDiff or similar.
- [ ] **Advanced TTS**:
    - [ ] Investigate "T5Gemma-TTS" (User specific) or F5-TTS.
    - [ ] Goal: Human-like speech.
- [ ] **Video Recognition**:
    - [ ] **Meta SAM 3** (User Request: "Not SAM 2").
    - [ ] Features: Promptable Concept Segmentation, Video Tracking.
    - [ ] Ref: `https://ai.meta.com/sam3/`
- [ ] **Agentic Workflow**: "Main LLM calls tools". (Already implemented, will refine).

# Gaming Mode (Lag Prevention)
- [x] **Plan Strategy**: Switch to `Qwen2.5-VL-7B-Instruct-AWQ` when gaming.
- [/] **Download Model**: Fetching `Qwen/Qwen2.5-VL-7B-Instruct-AWQ` (Running in background).
- [x] **Process Monitor**: Created `GameWatcher` (detect `valorant.exe`, `javaw.exe`).
- [x] **Resource Switcher**: 
    - [x] Update `ResourceManager` to support `set_gaming_mode(True/False)`.
    - [x] Logic: Stop 32B vLLM -> Start 7B vLLM.
    - [x] **Cooldown**: Implement 5-minute wait before restoring 32B model.

# Bug Fix: Port Conflict
- [x] **Problem**: "ORA Web UI" is hogging Port 8000. Bot is talking to Web UI instead of vLLM.
- [x] **Fix**: Move vLLM to Port **8001** (Complete).
    - [x] Update `start_vllm.bat` -> `--port 8001`.
    - [x] Update `config.py` -> `http://localhost:8001/v1`.
    - [x] Update `ResourceManager.py` -> `self.ports['llm'] = 8001`.

# Bug Fix: Context Length
- [x] **Problem**: Request (3600+ tokens) exceeded `vLLM` limit (2048 tokens).
- [x] **Fix**: Increased `--max-model-len` to **8192** in batch files.

# Optimization: Prevent VRAM Overflow
- [x] **Problem**: "Slightly overflowing" causing lag.
- [x] **Fix**: Tuned memory parameters.
    - [x] Normal Mode: `gpu-util 0.80`, `context 6144` (Balanced).
    - [x] Gaming Mode: `gpu-util 0.60`, `context 4096` (Max Performance for Games).

# Tool System Refactoring (New Architecture)
- [x] **Plan**: Categorize tools into hierarchy (Discord, Image, Video, Admin, etc).
- [x] **Desing**: Enable LLM to select "Category" -> "Tool" (Router Pattern or logical grouping).
- [x] **Implementation**: Update `_get_tool_schemas` in `ora.py`.
    - [x] **Discord**: `get_server_info`, `join_voice`, `shiritori`, `music_play`.
    - [x] **Image**: `generate_image`, `change_model`.
    - [x] **Voice**: `change_voice`, `tts_speak` (Placeholder).
    - [x] **Video**: `generate_video` (Placeholder), `analyze_video` (Placeholder).
    - [x] **Search**: `google_search` (SearchClient).
    - [x] **Admin**: `create_channel`, `system_control`, `desktop_watch`.
- [x] **System Prompt**: Update instructions to respect categories (Tags added).

# Advanced Model Routing (Dual Model System)
- [x] **Architecture**: Implement "Instruct -> Router -> Thinking" pipeline.
- [x] **Prompt Engineering**: Update Instruct System Prompt to output `route_eval` JSON.
    - [x] Schema: `{ needs_thinking, confidence, detected_task, tool_calls }`
- [x] **Router Logic**: Parse JSON and determine if escalation is needed.
    - [x] Trigger: `needs_thinking=true` OR `confidence < 0.72` OR `math/logic` tags.
- [x] **Switching Mechanism**: `ResourceManager` to handle hot-swapping vLLM processes.
- [x] **Switching Mechanism**: `ResourceManager` to handle hot-swapping vLLM processes.
    - [x] `switch_to_thinking()`: Kill Instruct, Start Thinking.
    - [x] `switch_to_instruct()`: Kill Thinking, Start Instruct.
    - [x] **Cooldown**: Keep Thinking active for 3 mins after use (Context Stickiness) (Implemented).
- [x] **Context Handover**: Pass Instruct's draft/analysis to Thinking model as context (Handled by history preservation).

# Specialized Models (TTS & Vision)
- [x] **T5Gemma-TTS-2b-2b**
    - [x] Download Model: `Aratako/T5Gemma-TTS-2b-2b`
    - [x] Download Resources: `Aratako/T5Gemma-TTS-2b-2b-resources`
    - [x] Implement: Updated `tts_speak` to recognize resources (Fallback to System Voice for stability).
- [x] **SAM 3 (Segment Anything Model 3)**
    - [x] Install: Cloned `facebookresearch/sam3`.
    - [x] Implement: `segment_objects` points to SAM 3 path, with SAM 2 fallback.

# Launcher Correction (Startup Conflict)
- [x] **Fix Resource Guard Loop**
    - [x] Issue: Launcher starts vLLM -> Bot starts -> ResourceGuard kills vLLM (Port Check) -> Bot Fails.
    - [x] Fix: Update `ResourceManager` to adopt existing process on startup if port is active.
    - [x] Fix: Update `start_vllm.bat` to set `ORA_STARTUP_MODE` env var so Bot knows what is running.

# Final Documentation & Release
- [x] **Update README.md**
    - [x] Document: Architecture (5-Layer: Launcher -> vLLM/Comfy/Bot).
    - [x] Document: New Features (Dual Model, Specialized Models, Right-Click Launcher).
    - [x] Document: Installation & Usage.
- [x] **GitHub Push**
    - [x] Commit all changes.
    - [x] Push to `YoneRai12/ORA`.

### Phase 14: Hot Reload & Gaming Mode (Completed)
- [x] Implement Hot Reload (`ResourceCog` / `src/cogs/resource_manager.py`)
- [x] Create `HotReloadView` for manual model switching
- [x] Gaming Mode Prompt Optimization
- [x] Bug Fixes:
    - [x] VLLM Server Connection
    - [x] Vision API compatibility (Qwen2.5-VL)
    - [x] JSON Parsing robustness
    - [x] **Auto Router Refactor**: Switched from "JSON Header" to "On-Demand Tool" (`start_thinking`) to prevent leakage.
    - [x] **Music Playback Reliability**: Added Heuristic Trigger to force playback if LLM output is text-only.
    - [x] **VC Leave Notification**: Fixed `play_tts` to allow Bot to speak even if user left VC.
    - [x] **Join Auto-Read**: Removed duplicate naive logic to enable correct "Connected" speech and Auto-Read.
    - [x] **Web Search**: Verified SerpApi/DuckDuckGo fallback and LLM context injection.
    - [x] **Search Refusal Fix**: Added `Search Heuristic` to override LLM refusals ("I can't answer...") with forced Google Search.
- [x] **Hot Reload Implementation**
    - [x] Refactor `VoiceManager` to persist state on Bot instance.
    - [x] Convert `MediaCog` to Extension (`setup` function).
    - [x] Add `/reload` command to `SystemCog`.
    - [x] Modify `bot.py` to load extensions.
    - [x] **Outcome**: Zero-downtime updates for music/media components.

- [x] **Gaming Mode Optimization**
    - [x] Configure `start_vllm_gaming.bat` for low VRAM (30%).
    - [x] Set Gaming Mode as Default in Launcher.
    - [x] **Outcome**: Bot runs on 10GB VRAM, leaving 22GB for games.

- [x] **Bug Fixes (Critical)**
    - [x] **VLLM OOM**: Fix startup crash by tuning `gpu_memory_utilization` (95% Instruct / 30% Gaming).
    - [x] **Tool Crash**: Fix `TypeError` in `ora.py` voice feedback.
    - [x] **Vision Duplication**: Fix double-sending of images (URL + Base64).
    - [x] **Command Ignorance**: Harden System Prompt to force 7B model to use Tools.
    - [x] **Lazy JSON**: Implement Fallback Parser for models skipping code blocks.

### Phase 15: Recent Improvements (Session)
- [x] **Command Enhancements**
    - [x] **Stealth /say Command**
        - [x] Modified `src/cogs/core.py` to support anonymous sending for specific User ID (`1069...`).
        - [x] Implemented ephemeral confirmation + direct channel send.
- [x] **Auto-Healer Optimization**
    - [x] **Channel Routing**: Redirected error reports to Debug Channel `<#1386994311400521768>`.
    - [x] **Prompt Engineering**: Improved LLM prompt to request concrete code blocks/diffs.
    - [x] **Hook Integration**: Verified Healer hook in `on_command_error` and `on_app_command_error`.
- [x] **Maintenance & Restoration**
    - [x] **Task List Restoration**: Recovered full project history (680+ lines) from backup.
    - [x] **Message Deletion**: Created `src/scripts/delete_target.py` for targeted cleanup.

### Phase 16: Identity Proof (The Evidence Pack)
*Creating "Verifiable Proof" of competence to replace empty labels.*
- [ ] **README Revamp (The "3-Line" Definition)**
    - [ ] Define: "What problem does ORA solve?" and "How?" in 3 concise lines at the top.
    - [ ] Goal: Immediate understanding for any visitor.
- [ ] **Demonstration Material**
    - [ ] **Demo Video (2 min)**: Screen recording of ORA working + Brief narration.
    - [ ] Showcasing: Voice Interaction -> Tool Use -> Image Gen -> Error Self-Repair.
- [ ] **Architecture Visualization**
    - [ ] **Design Diagram**: Visual flow of [User] -> [Router] -> [Tools/Models] -> [Data].
    - [ ] Document: "Why this architecture?" (Hybrid Local/Cloud, Event-Driven).
- [ ] **Verification Logs (The "Truth")**
    - [ ] **Test Criteria List**: Explicit bullet points of what is tested (Success & Failure cases).
    - [ ] **Commit History Integrity**: Ensure "Action -> Result" is traceable in git logs.

    - [ ] **Commit History Integrity**: Ensure "Action -> Result" is traceable in git logs.

### Phase 17: The Dual Architecture (Brain + Voice)
*Goal: Streamlined Architecture - Multimodal Main Brain + Dedicated Voice Engine.*
- [x] **Main Brain (Vision, Logic & Tools)**
    - [x] **Model**: `Ministral-3-14B` (or `Qwen-VL`) via vLLM.
    - [x] **Role**: Handles Chat, Tool Routing, and **Image Recognition** (Native).
- [x] **Voice Engine (Speech & Cloning)**
    - [x] **Model**: `Aratako/T5Gemma-TTS-2b-2b` (Confirmed) [Downloaded].
    - [x] **Infrastructure**: Implemented `src/services/voice_server.py` (FastAPI).
    - [x] **Client**: Implemented `src/cogs/voice_engine.py` (Discord Cog).
    - [x] **Feature**: "Doppelganger Mode" (Commands added).
    - [ ] **Verification**: Test audio generation.

### Phase 18: Tool Mastery (Real LoRA Training)
*Goal: Teach the Main Brain to use ORA Tools natively (without "Please use JSON" prompting).*
- [ ] **Data Preparation**
    - [ ] **Script**: Create `src/training/prepare_tool_data.py`.
    - [ ] **Data**: Generate 1000+ examples of `User Request` -> `Thought Process` -> `JSON Tool Call`.
    - [ ] **Format**: ChatML / ShareGPT format compatible with Ministral.
- [ ] **Training (RTX 5090)**
    - [ ] **Script**: Config `torchtune` or `unsloth` for 14B model LoRA.
    - [ ] **Run**: Execute training (approx 1-2 hours on 5090).
- [ ] **Deployment**
    - [ ] **LoRA Adapter**: Load the trained adapter into vLLM (`--enable-lora`).

### Phase 19: The "Bleeding Edge" Upgrade (Dec 2025)
*Goal: Incorporate the latest papers/models provided by user.*
- [ ] **Real-time Vision (Discord Stream)**
    - [ ] **Investigation**: Can bots watch streams? (Likely need User App or Screenshot-Bot).
    - [ ] **Alternative**: "Snapshot" mode via screenshare.
- [ ] **UI Polish**
    - [ ] **Font**: Integrate `Google Sans Flex` into `ora-ui`.
    - [ ] **Overlay**: Implement "Desktop Overlay" (Qiita reference).
- [ ] **Model Upgrades**
    - [ ] **Tool Router**: Evaluate `FunctionGemma` (Gemma 3 270M) for fast json routing.
    - [ ] **Gaming Mode**: Replace Qwen 7B with `NVIDIA Nemotron 3 Nano` (381 t/s).
    - [ ] **Main Brain**: Investigate `BU-30B-A3B-Preview` (Unknown model? Likely Qwen/Miqu variant).
- [ ] **Creative Tools**
    - [x] **Layering**: Implement `Qwen-Image-Layered` (`/layer` command - Image to PSD/RGBA).
        - [x] **Server**: `src/services/layer_server.py` (Port 8003).
        - [x] **Client**: `src/cogs/creative.py` (@ORA layer / /layer).
    - [ ] **3D Generation**: Implement `Microsoft TRELLIS.2` or `ML-Sharp` (`/3d` command).

- [ ] **Training Optimization (ELYZA Method)**
    - [ ] **Hyperparams**: Update LoRA config (High LR, MLP Target, Low Rank).










# Version 3.7.2: Implement TTS Voice Selection

- [ ] Research existing VoiceVox integration
    - [ ] Check `src/utils/tts_client.py` for speaker listing methods
    - [ ] Check `src/cogs/voice_engine.py` for existing commands
- [ ] Design Voice Selection Command
    - [ ] Create `implementation_plan.md`
- [ ] Implement `list_voices` command
    - [ ] Fetch speakers from VoiceVox engine
    - [ ] Display list to user
- [ ] Implement `set_voice` command
    - [ ] Update `VoiceManager` to store user preference
    - [ ] Persist preferences (optional, but good)
- [ ] Verify functionality
    - [ ] Test listing voices
    - [ ] Test changing voice
    - [ ] Verify TTS uses selected voice
