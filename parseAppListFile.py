import os
import sys
import shutil
import json

appListFile = "applist.txt"
sessionStateFile = "session_state.json"

defaultApps = ["#C:\\Program Files (x86)\\Steam#", "#C:\\Program Files (x86)\\Overwolf#", "#C:\\Program Files (x86)\\Epic Games#", "#C:\\Program Files\\Oculus#", "#C:\\Program Files\\Unity#", "#C:\\XboxGames#", "#C:\\Program Files\\Ubisoft#", "#C:\\Program Files\\EA Games#"]
defaultWebsites = ["steam.com", "store.steampowered.com", "GOG.com", "Battle.net", "itch.io", "poki.com", "fancade.com", "facebook.com", "youtube.com", "imgur.com", "instagram.com", "reddit.com", "discord.com", "ign.com", "gamespot.com", "whatsapp.com", "threads.com", "meta.com", "x.com", "tiktok.com", "snapchat.com", "linkedin.com", "pinterest.com", "twitch.com"]

def getDataPath(filename):
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle
        basePath = sys._MEIPASS
    else:
        # Running in normal Python
        basePath = os.path.dirname(__file__)
    return os.path.join(basePath, filename)

def getUserDataDir():
    userDir = os.path.join(os.path.expanduser("~"), "Documents", "FocusLock")
    os.makedirs(userDir, exist_ok=True)
    return userDir

def getAppListPath():
    userDir = getUserDataDir()
    userPath = os.path.join(userDir, "applist.txt")
    bundledPath = getDataPath(appListFile)
    if not os.path.exists(userPath):
        if os.path.exists(bundledPath):
            shutil.copy(bundledPath, userPath)
        else:
            # Create default
            with open(userPath, "w") as f:
                f.write("$NAMESPACE$^Default\n$Apps$\n")
                for app in defaultApps:
                    f.write(f"{app}\n")
                f.write("$Websites$\n")
                for website in defaultWebsites:
                    f.write(f"{website}\n")
                f.write("$END$\n")
    return userPath

def getSessionStatePath():
    return os.path.join(getUserDataDir(), sessionStateFile)

def readSessionState():
    statePath = getSessionStatePath()
    if not os.path.exists(statePath):
        return None

    try:
        with open(statePath, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

def writeSessionState(state):
    statePath = getSessionStatePath()
    tempPath = f"{statePath}.tmp"
    with open(tempPath, "w") as f:
        json.dump(state, f)
    os.replace(tempPath, statePath)

def clearSessionState():
    statePath = getSessionStatePath()
    if os.path.exists(statePath):
        os.remove(statePath)

def readListFile(location, currentNamespace):
    isValid, error = validateListFile(location)

    if not isValid:
        print(f"File structure error: {error}")
        return
    with open(location, "r") as f:
        apps = f.read().splitlines()
    
    addingToList = False
    for line in apps:
        if line.startswith("$END$") and addingToList:
            addingToList = False

        if addingToList:
            yield line

        if line.startswith("$NAMESPACE$") and line.split("$^")[1:][0] == currentNamespace and not addingToList:
            addingToList = True

def turnToReadableDictonary(location, currentNamespace):
    is_valid, error = validateListFile(location)

    if not is_valid:
        print(f"File structure error: {error}")
        return
    result = {}
    modifiers = {"#": "blackList", "*": "extensionBlock", "%": "whiteList", "!": "computerLock"}
    currentType = "Unknown"
    result[currentType] = {}
    for line in readListFile(location, currentNamespace):
        if line == "$Apps$":
            currentType = "Apps"
            result[currentType] = {}
        elif line == "$Websites$":
            currentType = "Websites"
            result[currentType] = {}
        for modifier in modifiers:
            if modifier in line:
                start = line.find(modifier) + 1
                end = line.find(modifier, start)
                name = line[start:end]
                result[currentType][name] = modifiers[modifier]
        if not any(modifier in line for modifier in modifiers) and line != "$Apps$" and line != "$Websites$":
            result[currentType][line] = "normal"
    return result

def scanForAppListFile(location):
    with open(location, "r") as f:
        apps = f.read().splitlines()
    
    namespaces = []

    for line in apps:
        if line.startswith("$NAMESPACE$"):
            namespaces.append(line.split("$^")[1:][0])
    return namespaces

def saveList(app_input, web_input, nameInput, refreshCallback=None):
    location = getAppListPath()
    is_valid, error = validateListFile(location)

    if not is_valid:
        print(f"File structure error: {error}")
        return
    appsText = app_input.get("1.0", "end-1c")
    websitesText = web_input.get("1.0", "end-1c")
    listName = nameInput.get()

    # Read existing content
    try:
        with open(location, "r") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        lines = []

    startIndex = None
    endIndex = None

    # Find the block to replace
    for i, line in enumerate(lines):
        if line.startswith("$NAMESPACE$") and line.split("$^")[1] == listName:
            startIndex = i

        if startIndex is not None and line.startswith("$END$"):
            endIndex = i
            break

    # Build the new block
    newBlock = []
    newBlock.append(f"$NAMESPACE$^{listName}")
    newBlock.append("$Apps$")
    newBlock.extend(appsText.splitlines())
    newBlock.append("$Websites$")
    newBlock.extend(websitesText.splitlines())
    newBlock.append("$END$")

    # Replace or append
    if startIndex is not None and endIndex is not None:
        # Replace in place
        lines = lines[:startIndex] + newBlock + lines[endIndex + 1:]
    else:
        # Namespace doesn't exist → append
        lines.extend(newBlock)

    # Write back
    with open(location, "w") as f:
        f.write("\n".join(lines) + "\n")
    
    # Call the refresh callback if provided
    if refreshCallback:
        try:
            refreshCallback()
        except Exception as e:
            print(f"Error calling refresh callback: {e}")

def validateListFile(location):
    try:
        with open(location, "r") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return True, None  # Treat missing file as valid (it'll be created)

    in_namespace = False
    current_namespace = None
    namespaces_seen = set()

    for i, line in enumerate(lines):
        # Start of namespace
        if line.startswith("$NAMESPACE$"):
            if in_namespace:
                return False, f"Line {i+1}: Nested namespace detected"

            parts = line.split("$^")
            if len(parts) < 2:
                return False, f"Line {i+1}: Invalid namespace format"

            current_namespace = parts[1]

            if current_namespace in namespaces_seen:
                return False, f"Line {i+1}: Duplicate namespace '{current_namespace}'"

            namespaces_seen.add(current_namespace)
            in_namespace = True
            continue

        # End of namespace
        if line.startswith("$END$"):
            if not in_namespace:
                return False, f"Line {i+1}: $END$ without a namespace"

            in_namespace = False
            current_namespace = None
            continue

        # Section markers
        if line in ("$Apps$", "$Websites$"):
            if not in_namespace:
                return False, f"Line {i+1}: '{line}' outside of namespace"

        # Any other content
        else:
            if not in_namespace and line.strip() != "":
                return False, f"Line {i+1}: Content outside namespace"

    # File ended while still inside a namespace
    if in_namespace:
        return False, "File ended before $END$"

    return True, None

def deleteList(name, refreshCallback=None):
    location = getAppListPath()
    is_valid, error = validateListFile(location)

    if not is_valid:
        print(f"File structure error: {error}")
        return

    try:
        with open(location, "r") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        print("No list file found to delete from.")
        return

    startIndex = None
    endIndex = None

    for i, line in enumerate(lines):
        if line.startswith("$NAMESPACE$") and line.split("$^")[1] == name:
            startIndex = i

        if startIndex is not None and line.startswith("$END$"):
            endIndex = i
            break

    if startIndex is not None and endIndex is not None:
        del lines[startIndex:endIndex + 1]
        with open(location, "w") as f:
            f.write("\n".join(lines) + "\n")
        
        # Call the refresh callback if provided
        if refreshCallback:
            try:
                refreshCallback()
            except Exception as e:
                print(f"Error calling refresh callback: {e}")
    else:
        print(f"No namespace named '{name}' found to delete.")