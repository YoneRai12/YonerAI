import winreg
import ctypes
import sys
import os

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def install_context_menu():
    key_path = r"Directory\Background\shell\CleanupCMDs"
    try:
        # Determine path to kill_ora.bat (same dir as this script)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        bat_path = os.path.join(script_dir, "kill_ora.bat")
        
        if not os.path.exists(bat_path):
            print(f"❌ エラー: スクリプトが見つかりません: {bat_path}")
            return

        # Create Key
        key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, key_path)
        winreg.SetValue(key, "", winreg.REG_SZ, "🧹 ORA一括終了 (Cleanup)")
        winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, "cmd.exe")
        
        # Create Command Subkey
        cmd_key = winreg.CreateKey(key, "command")
        
        # Command: Just run the bat file. It handles elevation itself.
        # \"%1\" is passed but ignored, handled by bat logic.
        command = f'"{bat_path}"'
        
        winreg.SetValue(cmd_key, "", winreg.REG_SZ, command)
        
        winreg.CloseKey(cmd_key)
        winreg.CloseKey(key)
        
        print("✅ 完了: 右クリックメニューに「🧹 ORA一括終了 (Cleanup)」を追加しました。")
        print("デスクトップやフォルダの背景を右クリックすると表示されます。")
        
    except Exception as e:
        print(f"❌ エラー: {e}")

if __name__ == "__main__":
    if is_admin():
        install_context_menu()
        print("\n[Enter]キーを押して終了してください...")
        input()
    else:
        # Re-run as admin
        print("🔒 管理者権限を要求しています...")
        try:
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        except Exception as e:
            print(f"管理者権限の取得に失敗しました: {e}")
            input()

