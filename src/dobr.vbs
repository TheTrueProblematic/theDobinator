Set objFSO = CreateObject("Scripting.FileSystemObject")
strPath = objFSO.GetParentFolderName(WScript.ScriptFullName)
Set objShell = CreateObject("WScript.Shell")

' 0 hides the window, False means don't wait for the script to finish
objShell.Run "pythonw """ & strPath & "\dobd.py""", 0, False
