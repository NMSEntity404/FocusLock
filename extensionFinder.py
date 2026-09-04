import os

def findFileType(extension):
    with open(f"{extension}OnComputer.txt", 'w') as appFile:
        appFile.write("")

    with open(f"{extension}OnComputer.txt", 'a') as appFile:
        for root, dirs, files in os.walk(os.path.abspath(os.sep)):
            for file in files:
                if file.endswith(f".{extension}"):
                    filePath = os.path.join(root, file)
                    appFile.write(filePath + '\n')

    print("Done writing to file!")