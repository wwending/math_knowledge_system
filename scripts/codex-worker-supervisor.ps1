[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InvocationFile,

    [Parameter(Mandatory = $true)]
    [string]$LeasePath,

    [Parameter(Mandatory = $true)]
    [string]$JobHelperPath
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$innerJob = [IntPtr]::Zero
$leaseStream = $null
$workerProcess = $null
$ready = $false

function Write-SupervisorBlocked {
    param([Parameter(Mandatory = $true)][string]$Message)

    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Message))
    [Console]::Out.WriteLine("CODEX_SUPERVISOR_BLOCKED $encoded")
    [Console]::Out.Flush()
}

try {
    if (-not $IsWindows) {
        throw "Windows Job Objects are required for Worker lifetime coupling."
    }
    . $JobHelperPath

    $establish = [Console]::In.ReadLine()
    if ($establish -ne "CODEX_SUPERVISOR_ESTABLISH_V1") {
        throw "Supervisor establishment gate was not received."
    }

    $innerJob = New-CodexKillOnCloseJob
    $currentProcessHandle = Get-CodexCurrentProcessHandle
    Add-CodexProcessToJob -Job $innerJob -ProcessHandle $currentProcessHandle
    if (-not (Test-CodexProcessInJob -Job $innerJob -ProcessHandle $currentProcessHandle)) {
        throw "Supervisor could not verify its inner Job Object membership."
    }

    [System.IO.Directory]::CreateDirectory((Split-Path -Parent $LeasePath)) | Out-Null
    try {
        $leaseStream = [System.IO.FileStream]::new(
            $LeasePath,
            [System.IO.FileMode]::OpenOrCreate,
            [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::None
        )
    }
    catch [System.IO.IOException] {
        throw "Worker lease is already held for this repository/worktree."
    }

    [Console]::Out.WriteLine("CODEX_SUPERVISOR_READY")
    [Console]::Out.Flush()
    $ready = $true

    $gate = [Console]::In.ReadLine()
    if ($gate -ne "CODEX_WORKER_GATE_V1") {
        throw "Worker launch gate was not received."
    }
    $workerPrompt = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($workerPrompt)) {
        throw "Worker prompt must not be empty."
    }

    $config = Get-Content -Raw -LiteralPath $InvocationFile | ConvertFrom-Json
    $processInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $processInfo.FileName = [string]$config.fileName
    $processInfo.WorkingDirectory = [string]$config.workingDirectory
    $processInfo.UseShellExecute = $false
    $processInfo.RedirectStandardInput = $true
    $processInfo.RedirectStandardOutput = $true
    $processInfo.RedirectStandardError = $true
    foreach ($argument in @($config.arguments)) {
        $processInfo.ArgumentList.Add([string]$argument)
    }

    $workerProcess = [System.Diagnostics.Process]::new()
    $workerProcess.StartInfo = $processInfo
    if (-not $workerProcess.Start()) {
        throw "Worker process could not be started."
    }
    if (-not (Test-CodexProcessInJob -Job $innerJob -ProcessHandle $workerProcess.Handle)) {
        throw "Worker process did not inherit the supervisor Job Object."
    }

    $stdoutTask = $workerProcess.StandardOutput.ReadToEndAsync()
    $stderrTask = $workerProcess.StandardError.ReadToEndAsync()
    $workerProcess.StandardInput.Write($workerPrompt)
    $workerProcess.StandardInput.Close()
    $workerProcess.WaitForExit()
    $stdout = $stdoutTask.GetAwaiter().GetResult()
    $stderr = $stderrTask.GetAwaiter().GetResult()
    [Console]::Out.Write($stdout)
    [Console]::Error.Write($stderr)
    [Console]::Out.Flush()
    [Console]::Error.Flush()
    exit $workerProcess.ExitCode
}
catch {
    if (-not $ready) {
        Write-SupervisorBlocked -Message $_.Exception.Message
    }
    else {
        [Console]::Error.WriteLine($_.Exception.Message)
        [Console]::Error.Flush()
    }
    exit 2
}
finally {
    if ($null -ne $leaseStream) {
        $leaseStream.Dispose()
    }
    # Do not close the inner kill-on-close Job while this process is still alive.
    # Process teardown closes the handle and terminates any surviving descendants.
}
