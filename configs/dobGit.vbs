' dobGit.vbs
'
' Background watcher. Wakes every day at 5:00 AM and invokes the Python
' updater (git_update.py). Designed to run continuously after logon.
'
' Notes for future agents:
'  - On Error Resume Next is set around the loop so a single bad day
'    (e.g. winget temporarily unavailable, transient git error) does not
'    kill the watcher.
'  - We do not trust PATH to resolve pythonw.exe because schtasks/wscript
'    on logon can hand us a sparse environment. ResolvePython() searches
'    a small list of typical install locations and falls back to a bare
'    "pythonw" if nothing matched.
'  - All actions go to configs\logs\vbs.log in append mode so we have an
'    audit trail across reboots.

Option Explicit

Dim fso, shell
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

Dim scriptDir, pythonScript, logDir, logFile
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonScript = fso.BuildPath(scriptDir, "git_updater\git_update.py")
logDir = fso.BuildPath(scriptDir, "logs")

If Not fso.FolderExists(logDir) Then
    fso.CreateFolder(logDir)
End If
logFile = fso.BuildPath(logDir, "vbs.log")

Sub LogMsg(msg)
    On Error Resume Next
    Dim f
    Set f = fso.OpenTextFile(logFile, 8, True)
    f.WriteLine Now & " - " & msg
    f.Close
    On Error Goto 0
End Sub

Function ResolvePython()
    Dim candidates, i, p, userProfile, localAppData, programFiles, programFilesX86
    userProfile = shell.ExpandEnvironmentStrings("%USERPROFILE%")
    localAppData = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%")
    programFiles = shell.ExpandEnvironmentStrings("%ProgramFiles%")
    programFilesX86 = shell.ExpandEnvironmentStrings("%ProgramFiles(x86)%")

    candidates = Array( _
        localAppData & "\Programs\Python\Python311\pythonw.exe", _
        localAppData & "\Programs\Python\Python312\pythonw.exe", _
        localAppData & "\Programs\Python\Python313\pythonw.exe", _
        localAppData & "\Programs\Python\Python310\pythonw.exe", _
        programFiles & "\Python311\pythonw.exe", _
        programFiles & "\Python312\pythonw.exe", _
        programFiles & "\Python313\pythonw.exe", _
        programFiles & "\Python310\pythonw.exe", _
        programFilesX86 & "\Python311\pythonw.exe", _
        programFilesX86 & "\Python312\pythonw.exe", _
        userProfile & "\AppData\Local\Programs\Python\Python311\pythonw.exe" _
    )

    For i = 0 To UBound(candidates)
        p = candidates(i)
        If fso.FileExists(p) Then
            ResolvePython = p
            Exit Function
        End If
    Next

    ' Last resort: rely on PATH.
    ResolvePython = "pythonw"
End Function

Dim pythonw
pythonw = ResolvePython()

LogMsg "dobGit.vbs started."
LogMsg "scriptDir   = " & scriptDir
LogMsg "pythonScript= " & pythonScript
LogMsg "pythonw     = " & pythonw

If Not fso.FileExists(pythonScript) Then
    LogMsg "FATAL: git_update.py not found at expected path. Exiting watcher."
    WScript.Quit 1
End If

Dim nowTime, targetTime, diffSeconds, msToSleep, exitCode, runCmd

Do
    On Error Resume Next

    nowTime = Now
    targetTime = DateValue(nowTime) + TimeValue("05:00:00")
    If nowTime >= targetTime Then
        targetTime = targetTime + 1
    End If

    diffSeconds = DateDiff("s", nowTime, targetTime)
    LogMsg "Target time: " & targetTime & ". Sleeping for " & diffSeconds & " seconds."

    msToSleep = diffSeconds * 1000
    WScript.Sleep msToSleep

    LogMsg "Woke up at " & Now & ". Running Python updater."

    ' Build a quoted command line. shell.Run with showWindow=0 and
    ' waitOnReturn=True invokes the updater synchronously and gives us
    ' its exit code.
    runCmd = """" & pythonw & """ """ & pythonScript & """"
    LogMsg "Invoking: " & runCmd

    Err.Clear
    exitCode = shell.Run(runCmd, 0, True)
    If Err.Number <> 0 Then
        LogMsg "shell.Run raised error " & Err.Number & ": " & Err.Description
        Err.Clear
    Else
        LogMsg "Python updater finished with exit code " & exitCode & "."
    End If

    On Error Goto 0
Loop
