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

    [Parameter(Mandatory = $true)]
    [string]$ControlPath,

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

function Test-PathWithin {
    param(
        [Parameter(Mandatory = $true)][string]$Child,
        [Parameter(Mandatory = $true)][string]$Parent
    )

    $normalizedChild = ConvertTo-NormalPath $Child
    $normalizedParent = ConvertTo-NormalPath $Parent
    if (Test-SamePath $normalizedChild $normalizedParent) {
        return $true
    }
    $parentPrefix = "$normalizedParent$([System.IO.Path]::DirectorySeparatorChar)"
    return $normalizedChild.StartsWith($parentPrefix, [System.StringComparison]::OrdinalIgnoreCase)
}

function Test-PathsOverlap {
    param(
        [Parameter(Mandatory = $true)][string]$Left,
        [Parameter(Mandatory = $true)][string]$Right
    )

    return (Test-PathWithin -Child $Left -Parent $Right) -or (Test-PathWithin -Child $Right -Parent $Left)
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

function Get-CodexPermissionPreset {
    $preset = [pscustomobject]@{
        Name = "approve-for-me"
        Arguments = [string[]]@("--approve-for-me")
        ApprovalMode = "automatic-review"
        SandboxMode = "workspace-write"
        SandboxSource = "implicit-by-approve-for-me"
    }
    if ($preset.Arguments.Count -ne 1 -or $preset.Arguments[0] -ne "--approve-for-me") {
        throw "Internal Codex permission preset is invalid."
    }
    return $preset
}

function Get-CodexWorkerExecArguments {
    param(
        [Parameter(Mandatory = $true)]$PermissionPreset,
        [Parameter(Mandatory = $true)][string]$WorkerPath,
        [Parameter(Mandatory = $true)][string]$CommonGitDirectory,
        [Parameter(Mandatory = $true)][string]$OutputFile
    )

    $arguments = @("exec", "-C", $WorkerPath)
    $arguments += @($PermissionPreset.Arguments)
    $arguments += @(
        "--add-dir", $CommonGitDirectory,
        "--json",
        "-o", $OutputFile,
        "-"
    )
    return $arguments
}

function Get-CodexCapability {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)]$PermissionPreset
    )

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
    if ($helpText -notmatch "(?m)^\s*-C,\s*--cd(?:\s|<)") {
        throw "Codex CLI is incompatible: exec help does not advertise -C/--cd."
    }
    foreach ($requiredOption in @("--approve-for-me", "--add-dir", "--json", "--output-last-message")) {
        if (-not $helpText.Contains($requiredOption, [System.StringComparison]::Ordinal)) {
            throw "Codex CLI is incompatible: exec help does not advertise $requiredOption."
        }
    }
    $normalizedHelp = [regex]::Replace($helpText, "\s+", " ").Trim()
    $permissionContract = "--approve-for-me Route approval requests through automatic review using the workspace-write sandbox"
    if (-not $normalizedHelp.Contains($permissionContract, [System.StringComparison]::Ordinal)) {
        throw "Codex CLI is incompatible: exec help does not define --approve-for-me as automatic review using the workspace-write sandbox."
    }
    if ($PermissionPreset.Name -ne "approve-for-me" -or
        $PermissionPreset.ApprovalMode -ne "automatic-review" -or
        $PermissionPreset.SandboxMode -ne "workspace-write" -or
        $PermissionPreset.SandboxSource -ne "implicit-by-approve-for-me") {
        throw "Internal Codex permission preset does not match the validated exec help contract."
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

function Get-WorkerLeaseIdentity {
    param(
        [Parameter(Mandatory = $true)][string]$CommonGitDirectory,
        [Parameter(Mandatory = $true)][string]$RepositoryIdentity,
        [Parameter(Mandatory = $true)][string]$CanonicalWorktree
    )

    $identity = @(
        $RepositoryIdentity.ToLowerInvariant()
        (ConvertTo-NormalPath $CommonGitDirectory).ToLowerInvariant()
        (ConvertTo-NormalPath $CanonicalWorktree).ToLowerInvariant()
    ) -join "`n"
    $hashBytes = [System.Security.Cryptography.SHA256]::HashData([System.Text.Encoding]::UTF8.GetBytes($identity))
    $leaseKey = [System.Convert]::ToHexString($hashBytes).ToLowerInvariant()
    $leaseDirectory = Join-Path (ConvertTo-NormalPath $CommonGitDirectory) "codex-worker-leases"
    $leasePath = Join-Path $leaseDirectory "$leaseKey.lock"

    return [pscustomobject]@{
        Key = $leaseKey
        Path = $leasePath
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

$workerLease = $null
$supervisorProcess = $null
$outerJob = [IntPtr]::Zero

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
    if (Test-PathsOverlap $control $target) {
        throw "WorktreePath must be a non-overlapping dedicated path outside the Control Checkout."
    }
    if (Test-PathsOverlap $control $resultRootPath) {
        throw "ResultRoot must remain outside all linked repository worktrees."
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
    $resolvedBaseSha = $baseResult.Output.ToLowerInvariant()
    $permissionPreset = Get-CodexPermissionPreset
    $codex = Get-CodexCapability -Command $CodexCommand -PermissionPreset $permissionPreset
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
    if ($inventory.Count -eq 0 -or -not (Test-SamePath $inventory[0].Path $control)) {
        throw "ControlPath must identify the repository's primary permanent Control Checkout, not a linked Task Worktree."
    }
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
    foreach ($worktreeEntry in $inventory) {
        $inventoryPath = ConvertTo-NormalPath $worktreeEntry.Path
        if (-not (Test-SamePath $inventoryPath $target) -and (Test-PathsOverlap $inventoryPath $target)) {
            throw "Requested worktree path overlaps another linked worktree: $inventoryPath"
        }
        if (Test-PathsOverlap $inventoryPath $resultRootPath) {
            throw "ResultRoot overlaps a linked repository worktree: $inventoryPath"
        }
    }
    if (Test-PathsOverlap $target $resultRootPath) {
        throw "ResultRoot must remain outside the requested Task Worktree."
    }
    if ((Test-Path -LiteralPath $target) -and $pathEntry.Count -eq 0) {
        throw "Expected path exists but is not the expected linked worktree: $target"
    }

    $branchExistsResult = Invoke-Git -RepositoryPath $control -Arguments @("show-ref", "--verify", "--quiet", $expectedBranchRef) -AllowFailure
    $branchExists = $branchExistsResult.ExitCode -eq 0
    if ($branchExistsResult.ExitCode -notin @(0, 1)) {
        throw "Unable to inspect the expected branch."
    }
    $branchHeadBefore = $null
    if ($branchExists) {
        $branchHeadResult = Invoke-Git -RepositoryPath $control -Arguments @("rev-parse", "--verify", "$expectedBranchRef`^{commit}")
        if ($branchHeadResult.Output -notmatch "^[0-9a-fA-F]{40}$") {
            throw "Expected branch does not resolve to a commit: $Branch"
        }
        $branchHeadBefore = $branchHeadResult.Output.ToLowerInvariant()
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
    $workerLease = Get-WorkerLeaseIdentity `
        -CommonGitDirectory $commonGitDir `
        -RepositoryIdentity $ExpectedRepository `
        -CanonicalWorktree $target
    $commandShapeArguments = Get-CodexWorkerExecArguments `
        -PermissionPreset $permissionPreset `
        -WorkerPath "<dedicated-worktree>" `
        -CommonGitDirectory "<git-common-dir>" `
        -OutputFile "<temporary-result-file>"
    $commandShape = "codex $($commandShapeArguments -join ' ')"

    if ($DryRun) {
        [ordered]@{
            status = "DRY_RUN_OK"
            repository = $ExpectedRepository
            issue = $IssueNumber
            branch = $Branch
            worktree = $target
            requestedBaseRef = $BaseRef
            resolvedBaseSha = $resolvedBaseSha
            branchHeadSha = $branchHeadBefore
            intendedInitialHeadSha = if ($decision -eq "CREATE_BRANCH_AND_WORKTREE") { $resolvedBaseSha } else { $null }
            decision = $decision
            workingState = $workingState
            codexVersion = $codex.Version
            commandShape = $commandShape
            permission = [ordered]@{
                preset = $permissionPreset.Name
                argv = @($permissionPreset.Arguments)
                approvalMode = $permissionPreset.ApprovalMode
                sandboxMode = $permissionPreset.SandboxMode
                sandboxSource = $permissionPreset.SandboxSource
            }
            validation = "OK"
        } | ConvertTo-Json -Depth 5
        exit 0
    }

    if (-not $IsWindows) {
        throw "Windows Job Objects are required for Worker lifetime coupling."
    }
    $jobHelperPath = Join-Path $PSScriptRoot "codex-worker-job.ps1"
    $supervisorPath = Join-Path $PSScriptRoot "codex-worker-supervisor.ps1"
    if (-not (Test-Path -LiteralPath $jobHelperPath -PathType Leaf) -or -not (Test-Path -LiteralPath $supervisorPath -PathType Leaf)) {
        throw "Worker lifetime-coupling helpers are missing."
    }
    . $jobHelperPath

    $runDirectory = Join-Path $resultRootPath ("issue-{0}\{1}" -f $IssueNumber, (Get-Date -Format "yyyyMMdd-HHmmss-fff"))
    [System.IO.Directory]::CreateDirectory($runDirectory) | Out-Null
    $eventFile = Join-Path $runDirectory "events.jsonl"
    $errorFile = Join-Path $runDirectory "stderr.log"
    $finalFile = Join-Path $runDirectory "final-message.txt"
    $invocationFile = Join-Path $runDirectory "worker-invocation.json"

    $outerJob = New-CodexKillOnCloseJob
    $supervisorInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $supervisorInfo.FileName = (Get-Process -Id $PID).Path
    $supervisorInfo.WorkingDirectory = $control
    $supervisorInfo.UseShellExecute = $false
    $supervisorInfo.RedirectStandardInput = $true
    $supervisorInfo.RedirectStandardOutput = $true
    $supervisorInfo.RedirectStandardError = $true
    foreach ($argument in @(
        "-NoProfile", "-File", $supervisorPath,
        "-InvocationFile", $invocationFile,
        "-LeasePath", $workerLease.Path,
        "-JobHelperPath", $jobHelperPath
    )) {
        $supervisorInfo.ArgumentList.Add($argument)
    }
    $supervisorProcess = [System.Diagnostics.Process]::new()
    $supervisorProcess.StartInfo = $supervisorInfo
    if (-not $supervisorProcess.Start()) {
        throw "Worker supervisor could not be started."
    }
    $supervisorStderrTask = $supervisorProcess.StandardError.ReadToEndAsync()
    Add-CodexProcessToJob -Job $outerJob -ProcessHandle $supervisorProcess.Handle
    if (-not (Test-CodexProcessInJob -Job $outerJob -ProcessHandle $supervisorProcess.Handle)) {
        throw "Worker supervisor could not verify its outer Job Object membership."
    }
    $supervisorProcess.StandardInput.WriteLine("CODEX_SUPERVISOR_ESTABLISH_V1")
    $supervisorProcess.StandardInput.Flush()
    $supervisorHandshake = $supervisorProcess.StandardOutput.ReadLine()
    if ($supervisorHandshake -ne "CODEX_SUPERVISOR_READY") {
        if ($supervisorHandshake -match "^CODEX_SUPERVISOR_BLOCKED (?<message>[A-Za-z0-9+/=]+)$") {
            $supervisorBlocker = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($Matches.message))
            if ($supervisorBlocker -match "^Worker lease is already held") {
                throw "Worker lease is already held for this repository/worktree: $target"
            }
            throw $supervisorBlocker
        }
        throw "Worker supervisor failed before establishing lifetime coupling."
    }

    if ($BaseRef.StartsWith("origin/", [System.StringComparison]::Ordinal)) {
        $remoteBranch = $BaseRef.Substring(7)
        if ($remoteBranch.Length -eq 0) {
            throw "Remote base branch is empty."
        }
        Invoke-Git -RepositoryPath $control -Arguments @("fetch", "--no-tags", "origin", $remoteBranch) | Out-Null
        $freshBase = (Invoke-Git -RepositoryPath $control -Arguments @("rev-parse", "--verify", "$BaseRef`^{commit}")).Output.ToLowerInvariant()
        if ($freshBase -ne $resolvedBaseSha) {
            throw "BaseRef changed during preflight ($resolvedBaseSha -> $freshBase); rerun to accept the new exact base."
        }
    }

    if ($decision -eq "CREATE_BRANCH_AND_WORKTREE") {
        Invoke-Git -RepositoryPath $control -Arguments @("worktree", "add", "-b", $Branch, $target, $resolvedBaseSha) | Out-Null
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
    $branchHeadSha = (Invoke-Git -RepositoryPath $target -Arguments @("rev-parse", "HEAD")).Output.ToLowerInvariant()
    if ($branchHeadSha -notmatch "^[0-9a-f]{40}$") {
        throw "Provisioned branch HEAD does not resolve to an exact commit."
    }
    if ($decision -eq "CREATE_BRANCH_AND_WORKTREE" -and $branchHeadSha -ne $resolvedBaseSha) {
        throw "New branch HEAD does not equal the resolved base SHA."
    }
    if ($decision -ne "CREATE_BRANCH_AND_WORKTREE" -and $branchHeadSha -ne $branchHeadBefore) {
        throw "Existing branch HEAD changed during provisioning; no reset, rebase, or history repair was attempted."
    }
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
Requested base ref: $BaseRef
Resolved base SHA: $resolvedBaseSha
Branch HEAD SHA: $branchHeadSha
Working state: $workingState

This worktree is dedicated to Issue #$IssueNumber. Perform writable repository operations only inside this task workspace, except for justified shared Git operations required by the repository workflow. Obey the repository AGENTS.md and any applicable AGENTS.override.md. Before writing, verify the Issue/branch/worktree mapping and stop on foreign, unknown, unrecognized dirty, or concurrently changing state. A DIRTY_ACCEPTED state means the launcher caller explicitly recognized the pre-existing changes as Issue #$IssueNumber work; inspect them and stop if that recognition is not supported by the evidence. Never repair another task with reset, destructive clean, stash, force push, branch deletion, history rewrite, or worktree deletion.

$taskPrompt
"@

    $workerArguments = @()
    foreach ($argument in $codex.PrefixArguments) {
        $workerArguments += $argument
    }
    $workerExecArguments = Get-CodexWorkerExecArguments `
        -PermissionPreset $permissionPreset `
        -WorkerPath $target `
        -CommonGitDirectory $commonGitDir `
        -OutputFile $finalFile
    foreach ($argument in $workerExecArguments) {
        $workerArguments += $argument
    }
    $invocationJson = [ordered]@{
        fileName = $codex.FileName
        workingDirectory = $target
        arguments = $workerArguments
    } | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText($invocationFile, $invocationJson, [System.Text.UTF8Encoding]::new($false))

    $stdoutTask = $supervisorProcess.StandardOutput.ReadToEndAsync()
    $supervisorProcess.StandardInput.WriteLine("CODEX_WORKER_GATE_V1")
    $supervisorProcess.StandardInput.Write($workerPrompt)
    $supervisorProcess.StandardInput.Close()
    $supervisorProcess.WaitForExit()
    $stdout = $stdoutTask.GetAwaiter().GetResult()
    $stderr = $supervisorStderrTask.GetAwaiter().GetResult()
    $workerExitCode = $supervisorProcess.ExitCode
    Close-CodexJob -Job $outerJob
    $outerJob = [IntPtr]::Zero
    [System.IO.File]::WriteAllText($eventFile, $stdout, [System.Text.UTF8Encoding]::new($false))
    [System.IO.File]::WriteAllText($errorFile, $stderr, [System.Text.UTF8Encoding]::new($false))

    $workerStatus = if ($workerExitCode -eq 0) { "WORKER_SUCCEEDED" } else { "WORKER_FAILED" }
    [ordered]@{
        status = $workerStatus
        statuses = @("PROVISIONED", "WORKER_STARTED", $workerStatus)
        repository = $ExpectedRepository
        issue = $IssueNumber
        branch = $Branch
        worktree = $target
        requestedBaseRef = $BaseRef
        resolvedBaseSha = $resolvedBaseSha
        branchHeadSha = $branchHeadSha
        decision = $decision
        workingState = if ($targetStatus.Length -gt 0) { "DIRTY_ACCEPTED" } else { "CLEAN" }
        workerLeaseKey = $workerLease.Key
        codexVersion = $codex.Version
        workerExitCode = $workerExitCode
        resultDirectory = $runDirectory
        finalMessageFile = $finalFile
        eventFile = $eventFile
        stderrFile = $errorFile
    } | ConvertTo-Json -Depth 5
    exit $workerExitCode
}
catch {
    $blocker = $_.Exception.Message
    if ($outerJob -ne [IntPtr]::Zero) {
        try {
            Close-CodexJob -Job $outerJob
            $outerJob = [IntPtr]::Zero
        }
        catch {
            # Preserve the original blocker.
        }
    }
    if ($null -ne $supervisorProcess) {
        try {
            $supervisorProcess.StandardInput.Close()
            $null = $supervisorProcess.WaitForExit(5000)
        }
        catch {
            # Preserve the original blocker after kill-on-close teardown was requested.
        }
    }
    (New-BlockedResult -Message $blocker) | ConvertTo-Json -Depth 5
    exit 2
}
