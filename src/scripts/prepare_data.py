import json
import os
import random

OUTPUT_FILE = "data/lora_dataset.jsonl"
SYSTEM_PROMPT = "You are ORA, an AI assistant. You can use tools to help the user. Answer in Japanese."
TOTAL_SAMPLES = 2000

# Templates define the intent, trigger phrases, and the target tool or response.
# format:
#   "intent": Label
#   "phrases": List of user inputs (with {slots})
#   "slots": Dict of slot values
#   "tool": Tool name (Optional, mutually exclusive with 'response')
#   "response": Text response (Optional, for identity/chitchat)
#   "arg_key": Primary argument key (Optional)
#   "fixed_args": Fixed arguments to mix in (Optional)

TEMPLATES = [
    # --- EXISTING CAPABILITIES ---
    {
        "intent": "music_play",
        "phrases": ["{song}流して", "{song}聴きたい", "Play {song}", "{song}再生して", "{song}お願い"],
        "slots": {"song": ["Bling-Bang-Bang-Born", "アイドル", "Specialz", "Kick Back", "Pokemon Theme", "Lo-fi HipHop", "Classic Jazz", "Heavy Metal"]},
        "tool": "music_play",
        "arg_key": "query"
    },
    {
        "intent": "google_search",
        "phrases": ["{query}について教えて", "今日の{query}", "{query}のニュース", "{query}の価格", "Search for {query}", "{query}とは？"],
        "slots": {"query": ["天気", "株価", "Bitcoin", "大谷翔平", "台風情報", "新作ゲーム", "RTX 5090", "Python入門"]},
        "tool": "google_search",
        "arg_key": "query"
    },
    {
        "intent": "generate_image",
        "phrases": ["画像生成 {prompt}", "{prompt}の絵を描いて", "Draw {prompt}", "{prompt}のイラスト"],
        "slots": {"prompt": ["可愛い猫", "サイバーパンクな街", "富士山", "未来の車", "ファンタジーの城", "アニメ風の少女"]},
        "tool": "generate_image",
        "arg_key": "prompt"
    },



    # --- MODERATION ---
    {
        "intent": "mod_ban",
        "phrases": ["{user}をBANして", "{user}は荒らしだ、BANだ", "Ban {user}"],
        "slots": {"user": ["@Taro", "@Spammer123", "荒らし", "BaddestBoy"]},
        "tool": "moderate_user",
        "arg_key": "target_user",
        "fixed_args": {"action": "ban", "reason": "Violated rules"}
    },
    {
        "intent": "mod_kick",
        "phrases": ["{user}をKickして", "{user}をキック", "Kick {user}"],
        "slots": {"user": ["@Hanako", "@Guest", "UserA"]},
        "tool": "moderate_user",
        "arg_key": "target_user",
        "fixed_args": {"action": "kick"}
    },
    {
        "intent": "mod_timeout",
        "phrases": ["{user}をタイムアウト", "{user}を黙らせて", "Timeout {user}"],
        "slots": {"user": ["@Noisy", "@Spam", "UserB"]},
        "tool": "moderate_user",
        "arg_key": "target_user",
        "fixed_args": {"action": "timeout", "duration": "10m"}
    },

    # --- UTILITY ---
    {
        "intent": "utility_remind",
        "phrases": ["{time}後に{task}って教えて", "{time}したら{task}", "Remind me to {task} in {time}"],
        "slots": {
            "time": ["3分", "10分", "1時間", "明日"],
            "task": ["カップラーメン", "会議", "ゲームやめる", "薬飲む"]
        },
        "tool": "set_reminder",
        "fixed_args": {}, # Logic implies time/message parsing, simplified for synthetic data
        # Mapping straightforward args for simulation
        "custom_arg_logic": lambda phrase, slots: {"duration": slots["time"], "message": slots["task"]}
    },
    {
        "intent": "utility_poll",
        "phrases": ["アンケート: {topic}", "{topic}について皆に聞いて", "Create poll: {topic}"],
        "slots": {"topic": ["明日の予定", "好きなゲーム", "晩御飯", "次回のイベント"]},
        "tool": "create_poll",
        "arg_key": "question"
    },
    {
        "intent": "utility_summary",
        "phrases": ["ここまでの流れまとめて", "要約して", "Summarize chat", "三行でまとめて"],
        "slots": {},
        "tool": "summarize_chat",
        "fixed_args": {"limit": 100}
    },

    # --- IDENTITY ---
    {
        "intent": "identity_who",
        "phrases": ["お前誰？", "自己紹介して", "Who are you?", "名前は？"],
        "slots": {},
        "response": "私はORA、YoneRai12によって作成されたAIアシスタントです。ゲームサーバーの管理やDiscordのモデレーション、検索などができます。"
    },
    {
        "intent": "identity_creator",
        "phrases": ["誰が作ったの？", "作者は？", "Who created you?"],
        "slots": {},
        "response": "私の開発者はYoneRai12です。"
    }
]

def generate_sample():
    template = random.choice(TEMPLATES)
    phrase = random.choice(template["phrases"])
    
    # 1. Fill Slots
    current_slots = {}
    if "slots" in template:
        for key, values in template["slots"].items():
            if values: # Ensure list is not empty
                val = random.choice(values)
                phrase = phrase.replace(f"{{{key}}}", val)
                current_slots[key] = val
    
    # 2. Determine Output (Tool Call vs Text Response)
    if "tool" in template:
        # Build Args
        args = {}
        if "fixed_args" in template:
            args.update(template["fixed_args"])
            
        if "custom_arg_logic" in template:
            # Custom lambda for complex mapping
            args.update(template["custom_arg_logic"](phrase, current_slots))
        elif "arg_key" in template:
            # Simple 1:1 mapping
            # Find the slot value used for this key
            # (Assuming the arg_key matches the slot name provided in 'slots' for simplicity, 
            #  or we map it if they differ. In TEMPLATES above, arg_key usually matches manual slot logic)
            # Actually, my simple logic above stored 'current_slots'.
            # If template has arg_key="query" and slots has "query", we use that.
            # If template has arg_key="game_name" but slot is "game", we need to know.
            # Let's fix the TEMPLATES to make slot keys match arg keys OR handle mapping.
            # FIX: In TEMPLATES, I used 'slots': {'game':...} but 'arg_key': 'game_name'.
            # I need to know which slot maps to arg_key.
            
            # Simple heuristic: look for value in current_slots that matches intent? No.
            # Let's just iterate current_slots and see if one seems primary?
            # Better: In the loop above, I know which slot key I used.
            # Let's use the 'arg_key' to grab the value from 'current_slots' if keys match.
            # If keys DON'T match (e.g. game vs game_name), we need a map.
            # For simplicity in this script, I will just iterate current_slots.
            # If len(current_slots) == 1, take it.
            if len(current_slots) == 1:
                args[template["arg_key"]] = list(current_slots.values())[0]
            else:
                # If multiple slots (e.g. remind me), custom_arg_logic handled it.
                # If no custom logic but multiple slots, we might miss one.
                # Fallback: Merge all current_slots into args using their names? 
                # No, keys might not match tool args.
                # For this specific script, 'game' -> 'game_name' is the only mismatch.
                if "game" in current_slots and template["arg_key"] == "game_name":
                    args["game_name"] = current_slots["game"]
                elif template["arg_key"] in current_slots:
                    args[template["arg_key"]] = current_slots[template["arg_key"]]

        content = json.dumps({"tool": template["tool"], "args": args}, ensure_ascii=False)
    
    elif "response" in template:
        content = template["response"]
    
    else:
        content = "Error: Invalid template"

    # 3. Construct Message
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": phrase},
        {"role": "assistant", "content": content} # JSON (Tool) or Text (Response)
    ]
    
    return json.dumps({"messages": messages}, ensure_ascii=False)

def main():
    os.makedirs("data", exist_ok=True)
    print(f"Generating {TOTAL_SAMPLES} samples to {OUTPUT_FILE}...")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for _ in range(TOTAL_SAMPLES):
            f.write(generate_sample() + "\n")
    
    print("Done.")

if __name__ == "__main__":
    main()
