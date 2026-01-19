import os
import platform
import subprocess
import sys
import zipfile

# --- CONFIGURATION ---
EXCLUDE_DIRS = {
    'node_modules', '.git', '__pycache__', '.venv', 'venv', 
    'ora-ui/.next', 'ora-ui/node_modules', 'dist', 'build',
    '.gemini', '.agent'
}
EXCLUDE_FILES = {
    'ora_migration.zip', '.DS_Store'
}
REQUIRED_FILES = [
    'src', 'ora-ui', 'package.json', 'requirements.txt', 
    'ora_bot.db', '.env', 'migration_helper.py'
]

def generate_launcher():
    """Generate a Mac launcher (.command) for extreme simplicity."""
    launcher_content = """#!/bin/bash
# ORA Bot One-Click Launcher
cd "$(dirname "$0")"
chmod +x migration_helper.py

echo "------------------------------------------------"
echo "🧠 ORA Bot: Automated Setup & Start"
echo "------------------------------------------------"

# 0.5 Check & Install Node.js (If missing)
if ! command -v node &> /dev/null; then
    echo "⚠️ Node.js not found. Installing automatically..."
    
    # Check for Homebrew
    if ! command -v brew &> /dev/null; then
        echo "🍺 Homebrew not found. Installing Homebrew first..."
        echo "🔓 NOTE: You may be asked for your Mac login password."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        
        # Add to PATH for Apple Silicon (M4)
        if [ -f "/opt/homebrew/bin/brew" ]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        elif [ -f "/usr/local/bin/brew" ]; then
            eval "$(/usr/local/bin/brew shellenv)"
        fi
    fi
    
    # Install Node
    echo "📦 Installing Node.js..."
    brew install node
else
    echo "✅ Node.js is already installed."
fi

# 1. Automatic Setup (includes VOICEVOX download)
python3 migration_helper.py setup

# 2. Start UI (Background)
if [ -d "ora-ui" ]; then
    echo "Starting Dashboard UI..."
    cd ora-ui
    if [ ! -d "node_modules" ]; then
        echo "Installing UI dependencies (First time)..."
        npm install
    fi
    npm run dev &
    UI_PID=$!
    cd ..
fi

# 3. Start Backend API (Background - Localhost Only)
echo "Starting Backend API..."
source .venv/bin/activate
uvicorn src.web.app:app --host 127.0.0.1 --port 8000 > backend.log 2>&1 &
API_PID=$!

# 4. Start VOICEVOX Engine (Background)
if [ -d "voicevox_engine" ]; then
    echo "Starting VOICEVOX Engine..."
    # 'run' is usually the entrypoint in the release zip
    if [ -f "voicevox_engine/run" ]; then
        chmod +x voicevox_engine/run
        ./voicevox_engine/run --host 127.0.0.1 --port 50021 > voicevox.log 2>&1 &
        VV_PID=$!
        echo "✅ VOICEVOX Started (PID: $VV_PID)"
    else
        echo "⚠️ VOICEVOX 'run' binary not found in expected path."
    fi
fi

# Cleanup Function
cleanup() {
    echo "Stopping ORA Bot Services..."
    [ ! -z "$UI_PID" ] && kill $UI_PID
    [ ! -z "$API_PID" ] && kill $API_PID
    [ ! -z "$VV_PID" ] && kill $VV_PID
}
trap cleanup EXIT

# 5. Tailscale Access Info
echo "------------------------------------------------"
echo "🔒 Secure Remote Access (Tailscale)"
echo "To access from Windows/Phone, run this in another terminal:"
echo "  tailscale serve https://localhost:3000"
echo "------------------------------------------------"

# 6. Start Bot (Foreground with Restart Loop)
echo "Starting ORA Bot Core..."
source .venv/bin/activate

while true; do
    echo "🚀 Launching Bot Process..."
    python3 main.py
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo "🔄 Bot requested restart (Exit Code 0). Restarting in 3 seconds..."
        sleep 3
    else
        echo "❌ Bot crashed or stopped with error (Exit Code $EXIT_CODE). Press Enter to restart manually or Ctrl+C to exit."
        read
    fi
done
"""
    launcher_name = "Double_Click_To_Start.command"
    with open(launcher_name, "w", newline='\n', encoding='utf-8') as f:
        f.write(launcher_content)
    # No chmod here as it's Windows, but it will be preserved in Zip properties usually or handled on Mac
    return launcher_name

def pack():
    """Pack project for migration."""
    print("📦 ORA Bot Migration Wrapper: Packing...")
    zip_filename = "ora_migration.zip"
    
    # Generate Launcher first
    launcher = generate_launcher()
    print(f"  Generated Launcher: {launcher}")

    if os.path.exists(zip_filename):
        os.remove(zip_filename)
        
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk('.'):
            # Check exclusions
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith('.')]
            
            for file in files:
                if file in EXCLUDE_FILES or (file.startswith('.') and file != '.env'):
                    continue
                        
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, '.')
                print(f"  Adding: {rel_path}")
                zipf.write(abs_path, rel_path)
    
    # Cleanup local launcher after packing (optional, keeps workspace clean)
    if os.path.exists(launcher):
        os.remove(launcher)
                
    print(f"\n✅ Done! Pack created: {os.path.abspath(zip_filename)}")
    print("Transfer this ZIP file to your M4 Mac and double-click 'Double_Click_To_Start.command'.")

def setup():
    """Setup environment on M4 Mac."""
    print("🚀 ORA Bot Migration Wrapper: Setup (Mac/Linux)...")
    
    if platform.system() == "Windows":
        print("⚠️ Warning: Setup is intended for the target machine (Mac/Linux).")
    
    # 1. Create venv
    if not os.path.exists(".venv"):
        print("Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", ".venv"])
    
    # 2. Install dependencies
    pip_path = os.path.join(".venv", "bin", "pip") if os.name != "nt" else os.path.join(".venv", "Scripts", "pip")
    
    if os.path.exists("requirements.txt"):
        print("Installing Python dependencies...")
        subprocess.run([pip_path, "install", "-r", "requirements.txt"])
    
    # 3. Check for .env
    if not os.path.exists(".env"):
        print("⚠️ .env file missing. Creating template...")
        with open(".env", "w") as f:
            f.write("# ORA Bot Environment\n")
            f.write("DISCORD_TOKEN=YOUR_TOKEN_HERE\n")
            f.write("PC_IP_ADDRESS=192.168.x.x\n")
            f.write("PC_MAC_ADDRESS=xx:xx:xx:xx:xx:xx\n")
            f.write("PC_SSH_USER=administrator\n")
            f.write("VOICEVOX_API_URL=http://localhost:50021\n") 
        print("Please edit the .env file with your Discord Token and PC information.")

    # 4. Install VOICEVOX Engine (Mac ARM64)
    install_voicevox_engine()

    print("\n✅ Setup Complete!")
    print("1. Edit .env if you haven't yet.")
    print("2. Run the bot: .venv/bin/python main.py")

def install_voicevox_engine():
    """Download and install VOICEVOX Engine for Mac (ARM64)."""
    # Only run on Mac
    if platform.system() != "Darwin":
        return

    target_dir = "voicevox_engine"
    if os.path.exists(target_dir):
        print("✅ VOICEVOX Engine already installed.")
        return

    print("⬇️ Downloading VOICEVOX Engine (Mac ARM64) from GitHub (v0.22.0)...")
    url = "https://github.com/VOICEVOX/voicevox_engine/releases/download/0.22.0/voicevox_engine-macos-aarch64-cpu-0.22.0.zip"
    zip_name = "voicevox_engine.zip"
    
    import urllib.request
    try:
        urllib.request.urlretrieve(url, zip_name)
        print("📦 Extracting VOICEVOX Engine...")
        with zipfile.ZipFile(zip_name, 'r') as zip_ref:
            zip_ref.extractall(".")
        
        # Rename extracted folder to fixed name 'voicevox_engine'
        # The zip usually contains a folder like 'voicevox_engine-macos-aarch64-cpu-0.22.0'
        for item in os.listdir("."):
            if item.startswith("voicevox_engine-") and os.path.isdir(item):
                os.rename(item, target_dir)
                break
        
        # Cleanup
        if os.path.exists(zip_name):
            os.remove(zip_name)
            
        # Permission fix
        run_path = os.path.join(target_dir, "run")
        if os.path.exists(run_path):
             os.chmod(run_path, 0o755)
             
        print("✅ VOICEVOX Engine installed successfully.")
        
    except Exception as e:
        print(f"❌ Failed to download/install VOICEVOX: {e}")
        print("   You may need to download 'Mac ARM64' version manually from voicevox.hiroshiba.jp")

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python migration_helper.py pack  - Run on Windows to create migration pack")
        print("  python migration_helper.py setup - Run on Mac to install dependencies")
        return

    command = sys.argv[1].lower()
    if command == "pack":
        pack()
    elif command == "setup":
        setup()
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()
