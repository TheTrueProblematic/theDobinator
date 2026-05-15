' dobGit.vbs
' Continuously running script that triggers the Python updater every day at 5:00 AM

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonScript = fso.BuildPath(scriptDir, "git_updater\git_update.py")
logDir = fso.BuildPath(scriptDir, "git_updater\logs")

If Not fso.FolderExists(logDir) Then
    fso.CreateFolder(logDir)
End If

logFile = fso.BuildPath(logDir, "vbs.log")

Sub LogMsg(msg)
    Set file = fso.OpenTextFile(logFile, 8, True)
    file.WriteLine Now & " - " & msg
    file.Close
End Sub

LogMsg "dobGit.vbs started."

Do
    nowTime = Now
    ' Target time is today at 5:00 AM
    targetTime = DateValue(nowTime) + TimeValue("05:00:00")
    
    ' If it's already past 5:00 AM today, schedule for tomorrow at 5:00 AM
    If nowTime >= targetTime Then
        targetTime = targetTime + 1
    End If
    
    ' Calculate seconds until the target time
    diffSeconds = DateDiff("s", nowTime, targetTime)
    
    LogMsg "Calculated target time: " & targetTime & ". Sleeping for " & diffSeconds & " seconds."
    
    msToSleep = diffSeconds * 1000
    WScript.Sleep msToSleep
    
    LogMsg "Woke up at " & Now & ". Running python updater."
    
    exitCode = shell.Run("pythonw """ & pythonScript & """", 0, True)
    
    LogMsg "Python updater finished with exit code " & exitCode & "."
Loop
