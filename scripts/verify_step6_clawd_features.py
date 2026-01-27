
import sys
import os
import asyncio

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

def verify_security_fixes():
    print("--- Verifying Security Fixes ---")
    
    with open("src/bot.py", "r", encoding="utf-8") as f:
        content = f.read()
        if 'r"C:\\Users\\' in content:
            print("❌ FAIL: Hardcoded path still found in src/bot.py")
        else:
            print("✅ PASS: No hardcoded user paths in src/bot.py")
            
        if '1454335076048568401' in content:
            print("❌ FAIL: Hardcoded Discord ID still found in src/bot.py")
        else:
            print("✅ PASS: No hardcoded Discord ID in src/bot.py")

    with open("src/utils/healer.py", "r", encoding="utf-8") as f:
        content = f.read()
        if 'gpt-5.1-codex' in content:
            print("❌ FAIL: valid model check (found gpt-5.1-codex)")
        else:
            print("✅ PASS: No fake models in src/utils/healer.py")

def verify_skill_loader():
    print("\n--- Verifying Skill Loader ---")
    from skills.loader import SkillLoader
    
    loader = SkillLoader()
    loader.load_skills()
    
    if "weather" in loader.skills:
        print("✅ PASS: 'weather' skill loaded")
        skill = loader.skills["weather"]
        desc = skill["description"]
        if "Weather Skill" in desc:
            print(f"✅ PASS: Description loaded ({len(desc)} chars)")
        else:
            print(f"❌ FAIL: Description content mismatch: {desc[:20]}...")
            
        # Check tool execution (mock)
        mod = skill["module"]
        if mod and hasattr(mod, "execute"):
            print("✅ PASS: tool.py loaded and executable")
        else:
            print("❌ FAIL: tool.py not executable")
            
    else:
        print(f"❌ FAIL: 'weather' skill not found. Skills: {loader.skills.keys()}")

if __name__ == "__main__":
    verify_security_fixes()
    try:
        verify_skill_loader()
    except Exception as e:
        print(f"❌ FAIL: Skill Loader crashed: {e}")
