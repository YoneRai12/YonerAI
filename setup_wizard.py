
import os
import sys
import subprocess
import shutil
import platform
import textwrap

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_banner():
    print(f"{Colors.CYAN}")
    print(r"""
   ____  ____    _    
  / __ \|  _ \  / \   
 | |  | | |_) |/ _ \  
 | |__| |  _ < / ___ \ 
  \____/|_| \_/_/   \_\
                       
   SYSTEM SETUP WIZARD
    """)
    print(f"{Colors.ENDC}")

def check_python_version():
    print(f"{Colors.HEADER}[1/5] Checking Python Environment...{Colors.ENDC}")
    ver = sys.version_info
    print(f"   Python Version: {ver.major}.{ver.minor}.{ver.micro}")
    
    if ver.major < 3 or (ver.major == 3 and ver.minor < 10):
        print(f"{Colors.FAIL}   ERROR: Python 3.10+ is required.{Colors.ENDC}")
        sys.exit(1)
    print(f"{Colors.GREEN}   ✅ Python Version OK{Colors.ENDC}")

def check_cuda():
    print(f"\n{Colors.HEADER}[2/5] Checking GPU (NVIDIA CUDA)...{Colors.ENDC}")
    try:
        # Simple check using nvidia-smi
        result = subprocess.run(['nvidia-smi'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            print(f"{Colors.GREEN}   ✅ NVIDIA GPU Detected.{Colors.ENDC}")
            # Optional: Parse output for driver version
        else:
            print(f"{Colors.WARNING}   ⚠️  NVIDIA GPU not detected via nvidia-smi.{Colors.ENDC}")
            print("      ORA can run in Cloud-Only mode or CPU mode (slow).")
    except FileNotFoundError:
        print(f"{Colors.WARNING}   ⚠️  nvidia-smi not found. Ensure NVIDIA Drivers are installed.{Colors.ENDC}")

def setup_venv():
    print(f"\n{Colors.HEADER}[3/5] Setting up Virtual Environment (venv)...{Colors.ENDC}")
    venv_dir = os.path.join(os.getcwd(), "venv")
    
    if os.path.exists(venv_dir):
        print(f"{Colors.BLUE}   ℹ️  venv already exists at {venv_dir}. Skipping creation.{Colors.ENDC}")
    else:
        print("   Creating venv...")
        subprocess.check_call([sys.executable, "-m", "venv", "venv"])
        print(f"{Colors.GREEN}   ✅ venv created.{Colors.ENDC}")

    # Return the path to the python executable in venv
    if platform.system() == "Windows":
        return os.path.join(venv_dir, "Scripts", "python.exe"), os.path.join(venv_dir, "Scripts", "pip.exe")
    else:
        return os.path.join(venv_dir, "bin", "python"), os.path.join(venv_dir, "bin", "pip")

def install_dependencies(python_path, pip_path):
    print(f"\n{Colors.HEADER}[4/5] Installing Dependencies...{Colors.ENDC}")
    
    # 1. Install PyTorch with CUDA support first (Crucial for Windows)
    print("   📦 Installing PyTorch (CUDA 12.1)... this may take a while.")
    subprocess.check_call([
        pip_path, "install", 
        "torch", "torchvision", "torchaudio", 
        "--index-url", "https://download.pytorch.org/whl/cu121"
    ])
    
    # 2. Install requirements.txt
    if os.path.exists("requirements.txt"):
        print("   📦 Installing Core Dependencies from requirements.txt...")
        subprocess.check_call([pip_path, "install", "-r", "requirements.txt"])
        print(f"{Colors.GREEN}   ✅ Dependencies installed.{Colors.ENDC}")
    else:
        print(f"{Colors.FAIL}   ❌ requirements.txt not found!{Colors.ENDC}")
        sys.exit(1)

def setup_env_file():
    print(f"\n{Colors.HEADER}[5/5] Checking Configuration (.env)...{Colors.ENDC}")
    if not os.path.exists(".env"):
        if os.path.exists(".env.example"):
            print("   ⚠️  .env not found. Creating from .env.example...")
            shutil.copy(".env.example", ".env")
            print(f"{Colors.GREEN}   ✅ Created .env{Colors.ENDC}")
            print(f"{Colors.WARNING}   IMPORTANT: Please edit .env and add your DISCORD_BOT_TOKEN!{Colors.ENDC}")
            
            # Simple interactive setup
            token = input(f"{Colors.CYAN}   Enter Discord Bot Token now (or Press Enter to skip): {Colors.ENDC}").strip()
            if token:
                with open(".env", "a") as f:
                    # Naive append, ideally we should replace the placeholder
                    # But for now, let's just append to overwrite (Discord.py python-dotenv overrides? check later)
                    # standard .env loaders usually take first or last. python-dotenv takes FIRST.
                    # So we need to Read, Replace, Write.
                    pass 
                
                # Let's do a read-replace
                with open(".env", "r", encoding="utf-8") as f:
                    content = f.read()
                
                if "DISCORD_BOT_TOKEN=" in content:
                     # Replace first occurrence
                     lines = content.splitlines()
                     new_lines = []
                     for line in lines:
                         if line.startswith("DISCORD_BOT_TOKEN="):
                             new_lines.append(f"DISCORD_BOT_TOKEN={token}")
                         else:
                             new_lines.append(line)
                     with open(".env", "w", encoding="utf-8") as f:
                         f.write("\n".join(new_lines))
                else:
                    with open(".env", "a") as f:
                         f.write(f"\nDISCORD_BOT_TOKEN={token}")
                
                print(f"{Colors.GREEN}   ✅ Token saved.{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}   ❌ .env and .env.example not found.{Colors.ENDC}")
    else:
        print(f"{Colors.GREEN}   ✅ .env exists.{Colors.ENDC}")

def finish():
    print(f"\n{Colors.HEADER}============================================={Colors.ENDC}")
    print(f"{Colors.GREEN}   SETUP COMPLETE!{Colors.ENDC}")
    print(f"{Colors.HEADER}============================================={Colors.ENDC}")
    print("\nTo start ORA, run:")
    if platform.system() == "Windows":
        print(f"   {Colors.CYAN}.\\start_windows.bat{Colors.ENDC}   (Recommended)")
        print(f"   or")
        print(f"   {Colors.CYAN}.\\venv\\Scripts\\python.exe -m src.bot{Colors.ENDC}")
    else:
        print(f"   {Colors.CYAN}./venv/bin/python -m src.bot{Colors.ENDC}")

if __name__ == "__main__":
    try:
        # Ensure we are in the root directory
        if not os.path.exists("src"):
            print("Please run this script from the project root directory.")
            sys.exit(1)
            
        print_banner()
        check_python_version()
        check_cuda()
        py_path, pip_path = setup_venv()
        install_dependencies(py_path, pip_path)
        setup_env_file()
        finish()
    except subprocess.CalledProcessError as e:
        print(f"\n{Colors.FAIL}❌ Setup Failed during command execution.{Colors.ENDC}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nSetup cancelled.")
