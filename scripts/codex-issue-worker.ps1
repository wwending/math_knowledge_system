[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 2147483647)]
    [int]$IssueNumber,

    [Parameter(Mandatory = $true)]
    [string]$Branch,

    [Parameter(Mandatory = $true)]
    [string]$WorktreePath,

    [Parameter(Mandatory = $true)]
    [string]$BaseRef,

    [Parameter(Mandatory = $true)]
    [string]$ExpectedRepository,

    [string]$ControlPath = (Split-Path -Parent $PSScriptRoot),

    [Parameter(ParameterSetName = "Prompt", Mandatory = $true)]
    [string]$Prompt,

    [Parameter(ParameterSetName = "PromptFile", Mandatory = $true)]
    [string]$PromptFile,

    [string]$CodexCommand = "codex",

    [string]$ResultRoot = (Join-Path ([System.IO.Path]::GetTempPath()) "math-knowledge-system-codex-workers"),

    [switch]$AllowDirtyIssueWorktree,

    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function ConvertTo-NormalPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    return [System.IO.Path]::GetFullPath($Path).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
}

function Test-SamePath {
    param(
        [Parameter(Mandatory = $true)][string]$Left,
        [Parameter(Mandatory = $true)][string]$Right
    )

    return [string]::Equals(
        (ConvertTo-NormalPath $Left),
        (ConvertTo-NormalPath $Right),
        [System.StringComparison]::OrdinalIgnoreCase
    )
}

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)][string]$RepositoryPath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$AllowFailure
    )

    $gitCommand = Get-Command git -CommandType Application -ErrorAction Stop
    $processInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $processInfo.FileName = $gitCommand.Source
    $processInfo.UseShellExecute = $false
    $processInfo.RedirectStandardOutput = $true
    $processInfo.RedirectStandardError = $true
    $processInfo.ArgumentList.Add("-C")
    $processInfo.ArgumentList.Add($RepositoryPath)
    foreach ($argument in $Arguments) {
        $processInfo.ArgumentList.Add($argument)
    }
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $processInfo
    if (-not $process.Start()) {
        throw "Git process could not be started."
    }
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $stdout = $stdoutTask.GetAwaiter().GetResult().Trim()
    $stderr = $stderrTask.GetAwaiter().GetResult().Trim()
    if (-not $AllowFailure -and $process.ExitCode -ne 0) {
        throw "git $($Arguments -join ' ') failed with exit code $($process.ExitCode): $stderr"
    }

    return [pscustomobject]@{
        ExitCode = $process.ExitCode
        Output = $stdout
        Error = $stderr
    }
}

function Get-WorktreeInventory {
    param([Parameter(Mandatory = $true)][string]$RepositoryPath)

    $raw = (Invoke-Git -RepositoryPath $RepositoryPath -Arguments @("worktree", "list", "--porcelain")).Output
    $entries = @()
    $current = $null
    foreach ($line in ($raw -split "`r?`n")) {
        if ($line.StartsWith("worktree ")) {
            if ($null -ne $current) {
                $entries += [pscustomobject]$current
            }
            $current = [ordered]@{ Path = $line.Substring(9); Branch = $null; Head = $null; Bare = $false }
        }
        elseif ($null -ne $current -and $line.StartsWith("HEAD ")) {
            $current.Head = $line.Substring(5)
        }
        elseif ($null -ne $current -and $line.StartsWith("branch ")) {
            $current.Branch = $line.Substring(7)
        }
        elseif ($null -ne $current -and $line -eq "bare") {
            $current.Bare = $true
        }
    }
    if ($null -ne $current) {
        $entries += [pscustomobject]$current
    }
    return @($entries)
}

function Get-CodexCapability {
    param([Parameter(Mandatory = $true)][string]$Command)

    $resolved = Get-Command $Command -ErrorAction Stop
    $versionOutput = & $resolved.Source --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Codex CLI version check failed."
    }
    $helpOutput = & $resolved.Source exec --help 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Codex CLI exec help check failed."
    }
    $helpText = ($helpOutput | ForEach-Object { $_.ToString() }) -join "`n"
    foreach ($requiredOption in @("--cd", "--sandbox", "--approve-for-me", "--add-dir", "--json", "--output-last-message")) {
        if (-not $helpText.Contains($requiredOption, [System.StringComparison]::Ordinal)) {
            throw "Codex CLI is incompatible: exec help does not advertise $requiredOption."
        }
    }

    $source = $resolved.Source
    if ($resolved.CommandType -eq [System.Management.Automation.CommandTypes]::ExternalScript) {
        return [pscustomobject]@{
            Version = (($versionOutput | ForEach-Object { $_.ToString() }) -join " ").Trim()
            FileName = (Get-Process -Id $PID).Path
            PrefixArguments = @("-NoProfile", "-File", $source)
        }
    }
    if ($resolved.CommandType -ne [System.Management.Automation.CommandTypes]::Application) {
        throw "Codex command must resolve to an application or external PowerShell script."
    }
    return [pscustomobject]@{
        Version = (($versionOutput | ForEach-Object { $_.ToString() }) -join " ").Trim()
        FileName = $source
        PrefixArguments = @()
    }
}

function New-BlockedResult {
    param([Parameter(Mandatory = $true)][string]$Message)

    return [ordered]@{
        status = "BLOCKED"
        issue = $IssueNumber
        branch = $Branch
        worktree = $WorktreePath
        blocker = $Message
    }
}

try {
    if ($Branch -notmatch "^[A-Za-z0-9][A-Za-z0-9._/-]*$" -or $Branch -notmatch "(^|/)issue-$IssueNumber(?:-|$)") {
        throw "Branch must be a safe Issue-numbered branch for Issue #$IssueNumber."
    }
    if ($BaseRef -notmatch "^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$") {
        throw "BaseRef contains unsupported characters."
    }
    if ($ExpectedRepository -notmatch "^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$") {
        throw "ExpectedRepository must use owner/repository form."
    }

    $control = ConvertTo-NormalPath $ControlPath
    $target = ConvertTo-NormalPath $WorktreePath
    $resultRootPath = ConvertTo-NormalPath $ResultRoot
    if (-not (Test-Path -LiteralPath $control -PathType Container)) {
        throw "Control Checkout does not exist: $control"
    }
    $controlRoot = (Invoke-Git -RepositoryPath $control -Arguments @("rev-parse", "--show-toplevel")).Output
    if (-not (Test-SamePath $control $controlRoot)) {
        throw "ControlPath is not the repository root: resolved root is $controlRoot"
    }
    if ((Test-SamePath $control $target) -or $target.StartsWith("$control$([System.IO.Path]::DirectorySeparatorChar)", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "WorktreePath must be a dedicated path outside the Control Checkout."
    }
    foreach ($repositoryPath in @($control, $target)) {
        if ((Test-SamePath $repositoryPath $resultRootPath) -or $resultRootPath.StartsWith("$repositoryPath$([System.IO.Path]::DirectorySeparatorChar)", [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "ResultRoot must remain outside repository worktrees."
        }
    }
    if ((Split-Path -Leaf $target) -notmatch "^issue-$IssueNumber(?:-|$)") {
        throw "WorktreePath leaf must identify Issue #$IssueNumber."
    }

    $remoteUrl = (Invoke-Git -RepositoryPath $control -Arguments @("remote", "get-url", "origin")).Output
    $escapedRepository = [regex]::Escape($ExpectedRepository)
    if ($remoteUrl -notmatch "(?i)(?:[:/])${escapedRepository}(?:\.git)?/?$") {
        throw "origin does not match expected repository $ExpectedRepository."
    }

    $baseResult = Invoke-Git -RepositoryPath $control -Arguments @("rev-parse", "--verify", "$BaseRef`^{commit}") -AllowFailure
    if ($baseResult.ExitCode -ne 0 -or $baseResult.Output -notmatch "^[0-9a-fA-F]{40}$") {
        throw "BaseRef cannot be resolved to an exact commit: $BaseRef"
    }
    $baseSha = $baseResult.Output.ToLowerInvariant()
    $codex = Get-CodexCapability -Command $CodexCommand
    $taskPrompt = if ($PSCmdlet.ParameterSetName -eq "PromptFile") {
        (Get-Content -Raw -LiteralPath (ConvertTo-NormalPath $PromptFile))
    }
    else {
        $Prompt
    }
    if ([string]::IsNullOrWhiteSpace($taskPrompt)) {
        throw "Worker prompt must not be empty."
    }
    $inventory = Get-WorktreeInventory -RepositoryPath $control
    $expectedBranchRef = "refs/heads/$Branch"
    $branchEntry = @($inventory | Where-Object { $_.Branch -eq $expectedBranchRef })
    $pathEntry = @($inventory | Where-Object { Test-SamePath $_.Path $target })
    if ($branchEntry.Count -gt 1 -or $pathEntry.Count -gt 1) {
        throw "Git worktree inventory contains duplicate branch or path mappings."
    }
    if ($branchEntry.Count -eq 1 -and -not (Test-SamePath $branchEntry[0].Path $target)) {
        throw "Expected branch is already attached to another worktree: $($branchEntry[0].Path)"
    }
    if ($pathEntry.Count -eq 1 -and $pathEntry[0].Branch -ne $expectedBranchRef) {
        throw "Expected path is linked to a different branch: $($pathEntry[0].Branch)"
    }
    if ((Test-Path -LiteralPath $target) -and $pathEntry.Count -eq 0) {
        throw "Expected path exists but is not the expected linked worktree: $target"
    }

    $branchExistsResult = Invoke-Git -RepositoryPath $control -Arguments @("show-ref", "--verify", "--quiet", $expectedBranchRef) -AllowFailure
    $branchExists = $branchExistsResult.ExitCode -eq 0
    if ($branchExistsResult.ExitCode -notin @(0, 1)) {
        throw "Unable to inspect the expected branch."
    }

    if ($pathEntry.Count -eq 1) {
        $decision = "REUSE"
        $status = (Invoke-Git -RepositoryPath $target -Arguments @("status", "--porcelain=v1", "--untracked-files=all")).Output
        if ($status.Length -gt 0 -and -not $AllowDirtyIssueWorktree) {
            throw "Expected worktree is dirty; no cleanup or stash was attempted."
        }
        $workingState = if ($status.Length -gt 0) { "DIRTY_ACCEPTED" } else { "CLEAN" }
    }
    elseif ($branchExists) {
        $decision = "ATTACH_EXISTING_BRANCH"
        $workingState = "NOT_CREATED"
    }
    else {
        $decision = "CREATE_BRANCH_AND_WORKTREE"
        $workingState = "NOT_CREATED"
    }

    $commonGitDirRaw = (Invoke-Git -RepositoryPath $control -Arguments @("rev-parse", "--git-common-dir")).Output
    $commonGitDir = if ([System.IO.Path]::IsPathRooted($commonGitDirRaw)) {
        ConvertTo-NormalPath $commonGitDirRaw
    }
    else {
        ConvertTo-NormalPath (Join-Path $control $commonGitDirRaw)
    }
    $commandShape = "codex exec -C <dedicated-worktree> --sandbox workspace-write --approve-for-me --add-dir <git-common-dir> --json -o <temporary-result-file> -"

    if ($DryRun) {
        [ordered]@{
            status = "DRY_RUN_OK"
            repository = $ExpectedRepository
            issue = $IssueNumber
            branch = $Branch
            worktree = $target
            baseRef = $BaseRef
            baseSha = $baseSha
            decision = $decision
            workingState = $workingState
            codexVersion = $codex.Version
            commandShape = $commandShape
            validation = "OK"
        } | ConvertTo-Json -Depth 5
        exit 0
    }

    if ($BaseRef.StartsWith("origin/", [System.StringComparison]::Ordinal)) {
        $remoteBranch = $BaseRef.Substring(7)
        if ($remoteBranch.Length -eq 0) {
            throw "Remote base branch is empty."
        }
        Invoke-Git -RepositoryPath $control -Arguments @("fetch", "--no-tags", "origin", $remoteBranch) | Out-Null
        $freshBase = (Invoke-Git -RepositoryPath $control -Arguments @("rev-parse", "--verify", "$BaseRef`^{commit}")).Output.ToLowerInvariant()
        if ($freshBase -ne $baseSha) {
            throw "BaseRef changed during preflight ($baseSha -> $freshBase); rerun to accept the new exact base."
        }
    }

    if ($decision -eq "CREATE_BRANCH_AND_WORKTREE") {
        Invoke-Git -RepositoryPath $control -Arguments @("worktree", "add", "-b", $Branch, $target, $baseSha) | Out-Null
    }
    elseif ($decision -eq "ATTACH_EXISTING_BRANCH") {
        Invoke-Git -RepositoryPath $control -Arguments @("worktree", "add", $target, $Branch) | Out-Null
    }

    $postInventory = Get-WorktreeInventory -RepositoryPath $control
    $postEntry = @($postInventory | Where-Object { Test-SamePath $_.Path $target })
    if ($postEntry.Count -ne 1 -or $postEntry[0].Branch -ne $expectedBranchRef) {
        throw "Post-provision branch/worktree validation failed."
    }
    $actualBranch = (Invoke-Git -RepositoryPath $target -Arguments @("branch", "--show-current")).Output
    $actualRoot = (Invoke-Git -RepositoryPath $target -Arguments @("rev-parse", "--show-toplevel")).Output
    $targetStatus = (Invoke-Git -RepositoryPath $target -Arguments @("status", "--porcelain=v1", "--untracked-files=all")).Output
    $acceptedDirtyState = $decision -eq "REUSE" -and $workingState -eq "DIRTY_ACCEPTED"
    if ($actualBranch -ne $Branch -or -not (Test-SamePath $actualRoot $target) -or ($targetStatus.Length -gt 0 -and -not $acceptedDirtyState)) {
        throw "Provisioned worktree failed root, branch, or clean-state validation."
    }
    $workerPrompt = @"
[LOCAL Codex]
Issue: #$IssueNumber
Branch: $Branch
Worktree: $target
Base SHA: $baseSha
Working state: $workingState

This worktree is dedicated to Issue #$IssueNumber. Perform writable repository operations only inside this task workspace, except for justified shared Git operations required by the repository workflow. Obey the repository AGENTS.md and any applicable AGENTS.override.md. Before writing, verify the Issue/branch/worktree mapping and stop on foreign, unknown, unrecognized dirty, or concurrently changing state. A DIRTY_ACCEPTED state means the launcher caller explicitly recognized the pre-existing changes as Issue #$IssueNumber work; inspect them and stop if that recognition is not supported by the evidence. Never repair another task with reset, destructive clean, stash, force push, branch deletion, history rewrite, or worktree deletion.

$taskPrompt
"@

    $runDirectory = Join-Path $resultRootPath ("issue-{0}\{1}" -f $IssueNumber, (Get-Date -Format "yyyyMMdd-HHmmss-fff"))
    [System.IO.Directory]::CreateDirectory($runDirectory) | Out-Null
    $eventFile = Join-Path $runDirectory "events.jsonl"
    $errorFile = Join-Path $runDirectory "stderr.log"
    $finalFile = Join-Path $runDirectory "final-message.txt"

    $processInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $processInfo.FileName = $codex.FileName
    $processInfo.WorkingDirectory = $target
    $processInfo.UseShellExecute = $false
    $processInfo.RedirectStandardInput = $true
    $processInfo.RedirectStandardOutput = $true
    $processInfo.RedirectStandardError = $true
    foreach ($argument in $codex.PrefixArguments) {
        $processInfo.ArgumentList.Add($argument)
    }
    foreach ($argument in @(
        "exec", "-C", $target,
        "--sandbox", "workspace-write",
        "--approve-for-me",
        "--add-dir", $commonGitDir,
        "--json",
        "-o", $finalFile,
        "-"
    )) {
        $processInfo.ArgumentList.Add($argument)
    }

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $processInfo
    if (-not $process.Start()) {
        throw "Worker process could not be started."
    }
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $process.StandardInput.Write($workerPrompt)
    $process.StandardInput.Close()
    $process.WaitForExit()
    $stdout = $stdoutTask.GetAwaiter().GetResult()
    $stderr = $stderrTask.GetAwaiter().GetResult()
    [System.IO.File]::WriteAllText($eventFile, $stdout, [System.Text.UTF8Encoding]::new($false))
    [System.IO.File]::WriteAllText($errorFile, $stderr, [System.Text.UTF8Encoding]::new($false))

    $workerStatus = if ($process.ExitCode -eq 0) { "WORKER_SUCCEEDED" } else { "WORKER_FAILED" }
    [ordered]@{
        status = $workerStatus
        statuses = @("PROVISIONED", "WORKER_STARTED", $workerStatus)
        repository = $ExpectedRepository
        issue = $IssueNumber
        branch = $Branch
        worktree = $target
        baseRef = $BaseRef
        baseSha = $baseSha
        decision = $decision
        workingState = if ($targetStatus.Length -gt 0) { "DIRTY_ACCEPTED" } else { "CLEAN" }
        codexVersion = $codex.Version
        workerExitCode = $process.ExitCode
        resultDirectory = $runDirectory
        finalMessageFile = $finalFile
        eventFile = $eventFile
        stderrFile = $errorFile
    } | ConvertTo-Json -Depth 5
    exit $process.ExitCode
}
catch {
    (New-BlockedResult -Message $_.Exception.Message) | ConvertTo-Json -Depth 5
    exit 2
}
