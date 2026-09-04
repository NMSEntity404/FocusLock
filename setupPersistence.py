"""
FocusLock Setup Script
Configures persistence features:
1. Auto-resume blocking on app startup
2. Auto-start via Windows Task Scheduler  
3. Optional: Startup folder shortcut for automatic app launch
"""

import os
import sys
import platform
import subprocess
import ctypes
import json

def getDataPath(filename):
    """Get path to data files"""
    if getattr(sys, 'frozen', False):
        basePath = sys._MEIPASS
    else:
        basePath = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(basePath, filename)

def escapePowerShellString(value):
    """Escape string for PowerShell"""
    return value.replace("'", "''")

def isElevated():
    """Check if running with admin privileges"""
    if platform.system() != "Windows":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False

def setupTaskScheduler():
    """
    Set up Windows Task Scheduler to run the blocking monitor at system startup.
    Requires admin privileges.
    """
    if platform.system() != "Windows":
        print("Task Scheduler setup is only available on Windows.")
        return False
    
    if not isElevated():
        print("ERROR: Admin privileges required for Task Scheduler setup.")
        print("Please run this script as Administrator.")
        return False
    
    try:
        monitorScriptPath = os.path.abspath(os.path.join(os.path.dirname(__file__), "blockingMonitor.py"))
        if not os.path.exists(monitorScriptPath):
            print(f"ERROR: blockingMonitor.py not found at {monitorScriptPath}")
            return False
        
        taskName = "FocusLockBlockingMonitor"
        pythonExe = sys.executable
        
        # Remove existing task if it exists
        print(f"Removing old task if it exists...")
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
             f"Get-ScheduledTask -TaskName '{taskName}' -ErrorAction SilentlyContinue | Unregister-ScheduledTask -Confirm:$false -ErrorAction SilentlyContinue"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Create new scheduled task
        print(f"Creating Task Scheduler task '{taskName}'...")
        powershellCommand = (
            f"$TaskName = '{taskName}'; "
            f"$Action = New-ScheduledTaskAction -Execute '{escapePowerShellString(pythonExe)}' "
            f"-Argument '\"{escapePowerShellString(monitorScriptPath)}\"'; "
            f"$Trigger = New-ScheduledTaskTrigger -AtStartup; "
            f"$Principal = New-ScheduledTaskPrincipal -UserId (whoami) -LogonType Interactive; "
            f"$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RunOnlyIfNetworkAvailable:$false -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5); "
            f"Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force | Out-Null; "
            f"Write-Host 'Task created successfully'"
        )
        
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", powershellCommand],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✓ Task Scheduler configured successfully!")
            print(f"  Task: {taskName}")
            print(f"  Trigger: System startup")
            print(f"  Script: {monitorScriptPath}")
            return True
        else:
            print(f"ERROR: Failed to create task")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def createStartupShortcut():
    """
    Create a shortcut in the Windows startup folder to launch FocusLock on boot.
    This is optional and provides an alternative to Task Scheduler.
    """
    if platform.system() != "Windows":
        print("Startup shortcut is only available on Windows.")
        return False
    
    try:
        startupFolder = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup")
        if not os.path.exists(startupFolder):
            print(f"ERROR: Startup folder not found at {startupFolder}")
            return False
        
        shortcutPath = os.path.join(startupFolder, "FocusLock.lnk")
        focusLockPath = os.path.abspath(__file__)
        
        powershellCommand = (
            "$WshShell = New-Object -ComObject WScript.Shell; "
            f"$Shortcut = $WshShell.CreateShortcut('{escapePowerShellString(shortcutPath)}'); "
            f"$Shortcut.TargetPath = '{escapePowerShellString(sys.executable)}'; "
            f"$Shortcut.Arguments = '\"{escapePowerShellString(focusLockPath)}\"'; "
            f"$Shortcut.WorkingDirectory = '{escapePowerShellString(os.path.dirname(focusLockPath))}'; "
            "$Shortcut.WindowStyle = 1; "  # Normal window
            "$Shortcut.Save()"
        )
        
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", powershellCommand],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        print(f"✓ Startup shortcut created at {shortcutPath}")
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to create startup shortcut: {e}")
        return False

def printStatus():
    """Print current persistence setup status"""
    print("\n" + "="*60)
    print("FocusLock Persistence Features")
    print("="*60)
    print("\n1. AUTO-RESUME (✓ Built-in)")
    print("   - When you reopen FocusLock after power-off/reboot")
    print("   - It automatically resumes any interrupted session")
    print("   - No configuration needed!")
    
    print("\n2. TASK SCHEDULER (Recommended)")
    print("   - Monitors blocking in background even if app is closed")
    print("   - Automatically restarts blocking if it crashes")
    print("   - Persists across reboots")
    print("   - Requires admin privileges to set up")
    
    print("\n3. STARTUP SHORTCUT (Optional)")
    print("   - Launches FocusLock UI on every boot")
    print("   - Better for manual control of sessions")
    print("   - No admin privileges required")
    
    print("\n" + "="*60)

def main():
    """Main setup menu"""
    printStatus()
    
    if platform.system() != "Windows":
        print("\nERROR: Setup is only available on Windows")
        print("On Linux/Mac, auto-resume works but you'll need to manually")
        print("launch the blocking monitor if desired.")
        return
    
    print("\nSetup Options:")
    print("1. Configure Task Scheduler (Recommended)")
    print("2. Create Startup Shortcut (Optional)")
    print("3. Do both (1 + 2)")
    print("4. Exit")
    
    choice = input("\nSelect option (1-4): ").strip()
    
    if choice == "1":
        success = setupTaskScheduler()
        if success:
            print("\n✓ Setup complete!")
            print("The blocking monitor will now run at system startup.")
    elif choice == "2":
        success = createStartupShortcut()
        if success:
            print("\n✓ Setup complete!")
            print("FocusLock will launch on the next boot.")
    elif choice == "3":
        print("\nSetting up both...")
        success1 = setupTaskScheduler()
        success2 = createStartupShortcut()
        if success1 and success2:
            print("\n✓ Full setup complete!")
            print("FocusLock will now:")
            print("  - Auto-resume interrupted sessions when you open it")
            print("  - Run background monitor at startup (even if app is closed)")
            print("  - Launch the app on boot for convenience")
    elif choice == "4":
        print("Exiting setup.")
    else:
        print("Invalid option.")

if __name__ == "__main__":
    main()
