# Figured out how to block apps using this python tutorial - https://www.youtube.com/watch?v=G_4eitXJrrg

import os
import platform
import stat
import subprocess
import sys
import pathlib

def is_windows():
    return platform.system() == "Windows"

WINDOWS_APP_EXTENSIONS = (".exe", ".lnk", ".url")
LINUX_APP_EXTENSIONS = (".appimage", ".desktop", ".run", ".sh", ".py")
mainExeDir = os.path.dirname(sys.executable)
blockingExe = os.path.join(mainExeDir, "startBlocking.exe")
panicExe = os.path.join(mainExeDir, "panic.exe")
if is_windows():
    defaultUnblockables = ["C:\\Windows", "C:\\Windows.~WS", "C:\\$WINDOWS.~BT", sys.executable, blockingExe, panicExe]
elif platform.system() == "Linux":
    defaultUnblockables = ["/bin", "/sbin", "/usr/bin", "/usr/sbin", sys.executable, blockingExe, panicExe]


def get_default_scan_path():
    return "C:\\" if is_windows() else os.path.abspath(os.sep)


def is_lockable_app(file_name):
    lower_name = file_name.lower()
    if is_windows():
        return lower_name.endswith(WINDOWS_APP_EXTENSIONS) and not any(lower_name.startswith(unblockable.lower()) for unblockable in defaultUnblockables)

    if lower_name.endswith(LINUX_APP_EXTENSIONS) and not any(lower_name.startswith(unblockable.lower()) for unblockable in defaultUnblockables):
        return True

    return "." not in os.path.basename(lower_name)


def lockapp(path):
    if path in defaultUnblockables or any(path.startswith(unblockable) for unblockable in defaultUnblockables):
        return
    if is_windows():
        cmd = ['icacls', path, '/deny', 'Everyone:(F)']
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return

    try:
        current_mode = stat.S_IMODE(os.stat(path).st_mode)
        os.chmod(path, current_mode & ~0o111)
    except OSError:
        pass


def unlockapp(path):
    if is_windows():
        cmd = ['icacls', path, '/grant', 'Everyone:(F)']
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return

    try:
        current_mode = stat.S_IMODE(os.stat(path).st_mode)
        os.chmod(path, current_mode | 0o111)
    except OSError:
        pass

def lockComputer():
    for root, dirs, files in os.walk(get_default_scan_path()):
        for file in files:
            if is_lockable_app(file):
                file_path = os.path.join(root, file)
                lockapp(file_path)

def unlockComputer():
    for root, dirs, files in os.walk(get_default_scan_path()):
        for file in files:
            if is_lockable_app(file):
                file_path = os.path.join(root, file)
                unlockapp(file_path)
                print("Unlocked file: " + file_path)

def blockExtension(path=None, extension=None):
    if path is None:
        path = get_default_scan_path()
    for root, dirs, files in os.walk(path):
        for file in files:
            if extension:
                if file.endswith(f".{extension}"):
                    filePath = os.path.join(root, file)
                    lockapp(filePath)
            else:
                if is_lockable_app(file):
                    filePath = os.path.join(root, file)
                    lockapp(filePath)

def unlockExtension(path=None, extension=None):
    if path is None:
        path = get_default_scan_path()
    for root, dirs, files in os.walk(path):
        for file in files:
            if extension:
                if file.endswith(f".{extension}"):
                    file_path = os.path.join(root, file)
                    unlockapp(file_path)
            else:
                if is_lockable_app(file):
                    file_path = os.path.join(root, file)
                    unlockapp(file_path)

def blacklistApps(folderPath, blockingDict):
    for root, dirs, files in os.walk(folderPath):
            for file in files:
                if file in blockingDict["Apps"] and blockingDict["Apps"][file] == "whiteList":
                    pass
                elif is_lockable_app(file):
                    file_path = os.path.join(root, file)
                    lockapp(file_path)

def unlockBlacklistApps(folderPath, blockingDict):
    for root, dirs, files in os.walk(folderPath):
            for file in files:
                if file in blockingDict["Apps"] and blockingDict["Apps"][file] == "whiteList":
                    pass
                elif is_lockable_app(file):
                    file_path = os.path.join(root, file)
                    unlockapp(file_path)
