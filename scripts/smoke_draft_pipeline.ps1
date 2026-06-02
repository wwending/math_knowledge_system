param(
    [string]$BaseUrl = "http://127.0.0.1:8000/api/v1",
    [Parameter(Mandatory = $true)]
    [string]$Username,
    [Parameter(Mandatory = $true)]
    [string]$Password,
    [Parameter(Mandatory = $true)]
    [string]$ImagePath,
    [switch]$SkipRecognize,
    [switch]$LiveRecognize
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0
Add-Type -AssemblyName System.Net.Http

function Write-Step {
    param([string]$Name)
    Write-Host ""
    Write-Host "== $Name ==" -ForegroundColor Cyan
}

function Write-Field {
    param(
        [string]$Name,
        [AllowNull()]$Value
    )
    if ($null -eq $Value -or $Value -eq "") {
        Write-Host ("{0}: <empty>" -f $Name)
    } else {
        Write-Host ("{0}: {1}" -f $Name, $Value)
    }
}

function Get-Prop {
    param(
        [AllowNull()]$Object,
        [string[]]$Names
    )
    if ($null -eq $Object) {
        return $null
    }
    foreach ($name in $Names) {
        if ($Object.PSObject.Properties.Name -contains $name) {
            return $Object.$name
        }
    }
    return $null
}

function Assert-Value {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) {
        throw "ASSERT FAILED: $Message"
    }
}

function Join-ApiUrl {
    param(
        [string]$Root,
        [string]$Path
    )
    return ($Root.TrimEnd("/") + "/" + $Path.TrimStart("/"))
}

function ConvertTo-CompactJson {
    param([AllowNull()]$Value)
    if ($null -eq $Value) {
        return "<null>"
    }
    return ($Value | ConvertTo-Json -Depth 20 -Compress)
}

function Get-ErrorBody {
    param([System.Management.Automation.ErrorRecord]$ErrorRecord)
    $message = $ErrorRecord.Exception.Message
    $body = $null

    if ($ErrorRecord.ErrorDetails -and $ErrorRecord.ErrorDetails.Message) {
        $body = $ErrorRecord.ErrorDetails.Message
    } elseif ($ErrorRecord.Exception.Response) {
        try {
            $stream = $ErrorRecord.Exception.Response.GetResponseStream()
            if ($stream) {
                $reader = New-Object System.IO.StreamReader($stream)
                $body = $reader.ReadToEnd()
            }
        } catch {
            $body = $null
        }
    }

    if ($body) {
        try {
            $parsed = $body | ConvertFrom-Json
            return [pscustomobject]@{
                message = $message
                raw = $body
                json = $parsed
            }
        } catch {
            return [pscustomobject]@{
                message = $message
                raw = $body
                json = $null
            }
        }
    }

    return [pscustomobject]@{
        message = $message
        raw = $null
        json = $null
    }
}

function Invoke-Json {
    param(
        [string]$Method,
        [string]$Url,
        [hashtable]$Headers = @{},
        [AllowNull()]$Body
    )
    $params = @{
        Method = $Method
        Uri = $Url
        Headers = $Headers
        ErrorAction = "Stop"
    }
    if ($null -ne $Body) {
        $params["ContentType"] = "application/json"
        $params["Body"] = ($Body | ConvertTo-Json -Depth 20)
    }

    try {
        return Invoke-RestMethod @params
    } catch {
        $errorBody = Get-ErrorBody -ErrorRecord $_
        Write-Host "HTTP request failed: $Method $Url" -ForegroundColor Red
        Write-Field "message" $errorBody.message
        if ($errorBody.json) {
            Write-Field "detail" (Get-Prop $errorBody.json @("detail", "error", "message"))
            Write-Field "body" (ConvertTo-CompactJson $errorBody.json)
        } elseif ($errorBody.raw) {
            Write-Field "body" $errorBody.raw
        }
        throw
    }
}

function Get-MimeType {
    param([string]$Path)
    $extension = [System.IO.Path]::GetExtension($Path).ToLowerInvariant()
    switch ($extension) {
        ".png" { return "image/png" }
        ".jpg" { return "image/jpeg" }
        ".jpeg" { return "image/jpeg" }
        ".gif" { return "image/gif" }
        ".bmp" { return "image/bmp" }
        ".webp" { return "image/webp" }
        ".pdf" { return "application/pdf" }
        default { return "application/octet-stream" }
    }
}

function Invoke-AssetUpload {
    param(
        [string]$Url,
        [hashtable]$Headers,
        [string]$Path
    )

    $client = New-Object System.Net.Http.HttpClient
    $content = $null
    $fileStream = $null
    try {
        foreach ($key in $Headers.Keys) {
            [void]$client.DefaultRequestHeaders.TryAddWithoutValidation($key, [string]$Headers[$key])
        }

        $content = New-Object System.Net.Http.MultipartFormDataContent
        $fileStream = [System.IO.File]::OpenRead($Path)
        $fileContent = New-Object System.Net.Http.StreamContent($fileStream)
        $fileContent.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse((Get-MimeType $Path))
        $fileName = [System.IO.Path]::GetFileName($Path)
        $content.Add($fileContent, "file", $fileName)

        $response = $client.PostAsync($Url, $content).GetAwaiter().GetResult()
        $responseBody = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        if (-not $response.IsSuccessStatusCode) {
            Write-Host "HTTP request failed: POST $Url" -ForegroundColor Red
            Write-Field "status" ([int]$response.StatusCode)
            Write-Field "body" $responseBody
            throw "Asset upload failed with HTTP status $([int]$response.StatusCode)"
        }
        return ($responseBody | ConvertFrom-Json)
    } finally {
        if ($fileStream) { $fileStream.Dispose() }
        if ($content) { $content.Dispose() }
        $client.Dispose()
    }
}

function Test-LiveRecognizeEnv {
    $missing = @()
    if (-not $env:BAIDU_API_KEY) { $missing += "BAIDU_API_KEY" }
    if (-not $env:BAIDU_SECRET_KEY) { $missing += "BAIDU_SECRET_KEY" }
    if (-not $env:DEEPSEEK_API_KEY) { $missing += "DEEPSEEK_API_KEY" }
    return $missing
}

$BaseUrl = $BaseUrl.TrimEnd("/")
$resolvedImagePath = (Resolve-Path -LiteralPath $ImagePath).Path
Assert-Value (Test-Path -LiteralPath $resolvedImagePath -PathType Leaf) "ImagePath does not exist: $ImagePath"

if ($SkipRecognize -and $LiveRecognize) {
    throw "Use either -SkipRecognize or -LiveRecognize, not both."
}

Write-Host "Draft pipeline API smoke"
Write-Field "BaseUrl" $BaseUrl
Write-Field "ImagePath" $resolvedImagePath
Write-Field "Mode" $(if ($SkipRecognize) { "basic checks, recognize skipped" } elseif ($LiveRecognize) { "live OCR/LLM forced" } else { "auto; skip live recognize when local env keys are missing" })

Write-Step "1. Login"
$loginUrl = Join-ApiUrl $BaseUrl "/auth/login"
$loginResponse = Invoke-Json -Method "POST" -Url $loginUrl -Body @{
    phone = $Username
    password = $Password
}
$accessToken = Get-Prop $loginResponse @("access_token")
Assert-Value (-not [string]::IsNullOrWhiteSpace($accessToken)) "Login must return access_token"
Write-Field "access_token" ($accessToken.Substring(0, [Math]::Min(18, $accessToken.Length)) + "...")
Write-Field "user_id" (Get-Prop (Get-Prop $loginResponse @("user")) @("id"))

$headers = @{ Authorization = "Bearer $accessToken" }

Write-Step "2. Upload Asset"
$assetUrl = Join-ApiUrl $BaseUrl "/assets"
$assetResponse = Invoke-AssetUpload -Url $assetUrl -Headers $headers -Path $resolvedImagePath
$sourceAssetId = Get-Prop $assetResponse @("source_asset_id", "asset_id", "id")
Assert-Value ($null -ne $sourceAssetId) "Asset upload must return source_asset_id, asset_id, or id"
Write-Field "source_asset_id" $sourceAssetId
Write-Field "kind" (Get-Prop $assetResponse @("kind"))
Write-Field "mime" (Get-Prop $assetResponse @("mime"))

Write-Step "3. Create Draft"
$draftUrl = Join-ApiUrl $BaseUrl "/drafts"
$draftResponse = Invoke-Json -Method "POST" -Url $draftUrl -Headers $headers -Body @{
    source_asset_id = [int]$sourceAssetId
}
$draftId = Get-Prop $draftResponse @("draft_id", "id")
Assert-Value ($null -ne $draftId) "Draft creation must return draft id"
$draftStatus = Get-Prop $draftResponse @("status")
Write-Field "draft_id" $draftId
Write-Field "draft_status" $draftStatus
Write-Field "partial_success" (Get-Prop $draftResponse @("partial_success"))
Write-Field "question_id" (Get-Prop $draftResponse @("question_id"))
Write-Field "question_revision_id" (Get-Prop $draftResponse @("question_revision_id"))

Write-Step "4. Get Draft"
$draftDetailUrl = Join-ApiUrl $BaseUrl "/drafts/$draftId"
$draftDetail = Invoke-Json -Method "GET" -Url $draftDetailUrl -Headers $headers
$draftStatus = Get-Prop $draftDetail @("status")
Assert-Value ((Get-Prop $draftDetail @("id")) -eq $draftId) "GET draft must return the created draft id"
Write-Field "draft_id" (Get-Prop $draftDetail @("id"))
Write-Field "draft_status" $draftStatus
Write-Field "partial_success" (Get-Prop $draftDetail @("partial_success"))
Write-Field "question_id" (Get-Prop $draftDetail @("question_id"))
Write-Field "question_revision_id" (Get-Prop $draftDetail @("question_revision_id"))

$missingLiveEnv = Test-LiveRecognizeEnv
if ($SkipRecognize) {
    Write-Step "5. Recognize Draft"
    Write-Host "Skipped by -SkipRecognize. This validates login, asset upload, draft creation, and draft retrieval only." -ForegroundColor Yellow
    Write-Step "6. Save To Bank"
    Write-Host "Skipped because recognize was skipped; only draft_ready drafts may be saved to bank." -ForegroundColor Yellow
    exit 0
}

if ((-not $LiveRecognize) -and $missingLiveEnv.Count -gt 0) {
    Write-Step "5. Recognize Draft"
    Write-Host "Skipped because local OCR/LLM environment variables are missing: $($missingLiveEnv -join ', ')." -ForegroundColor Yellow
    Write-Host "Run with -LiveRecognize to call the backend anyway if keys are configured in backend/.env or another server-side environment." -ForegroundColor Yellow
    Write-Step "6. Save To Bank"
    Write-Host "Skipped because recognize was not executed; only draft_ready drafts may be saved to bank." -ForegroundColor Yellow
    exit 0
}

if ($LiveRecognize -and $missingLiveEnv.Count -gt 0) {
    Write-Host "Local env keys missing: $($missingLiveEnv -join ', '). Continuing because -LiveRecognize was provided." -ForegroundColor Yellow
}

Write-Step "5. Recognize Draft"
$recognizeUrl = Join-ApiUrl $BaseUrl "/drafts/$draftId/recognize"
$recognizeResponse = Invoke-Json -Method "POST" -Url $recognizeUrl -Headers $headers
$draftStatus = Get-Prop $recognizeResponse @("status")
$partialSuccess = Get-Prop $recognizeResponse @("partial_success")
$errorType = Get-Prop $recognizeResponse @("error_type")
$errorText = Get-Prop $recognizeResponse @("error")
Assert-Value (@("draft_ready", "failed", "recognizing") -contains $draftStatus) "Recognize status must be draft_ready, failed, or an explicitly transitional status"
Write-Field "draft_id" (Get-Prop $recognizeResponse @("id"))
Write-Field "draft_status" $draftStatus
Write-Field "success" (Get-Prop $recognizeResponse @("success"))
Write-Field "partial_success" $partialSuccess
Write-Field "error_type" $errorType
Write-Field "error" $errorText
Write-Field "question_id" (Get-Prop $recognizeResponse @("question_id"))
Write-Field "question_revision_id" (Get-Prop $recognizeResponse @("question_revision_id"))

if ($draftStatus -ne "draft_ready") {
    Write-Step "6. Save To Bank"
    Write-Host "Skipped because draft_status is '$draftStatus'. Only draft_ready may call save-to-bank." -ForegroundColor Yellow
    if ($errorType -or $errorText) {
        Write-Host "Recognize did not reach draft_ready. External OCR/LLM configuration may be the cause." -ForegroundColor Yellow
        Write-Field "error_type" $errorType
        Write-Field "error" $errorText
    }
    exit 0
}

Write-Step "6. Save To Bank"
$saveUrl = Join-ApiUrl $BaseUrl "/drafts/$draftId/save-to-bank"
$saveResponse = Invoke-Json -Method "POST" -Url $saveUrl -Headers $headers
$questionId = Get-Prop $saveResponse @("question_id")
$questionRevisionId = Get-Prop $saveResponse @("question_revision_id")
Assert-Value ($null -ne $questionId) "save-to-bank must return question_id"
Assert-Value ($null -ne $questionRevisionId) "save-to-bank must return question_revision_id"
Write-Field "draft_id" (Get-Prop $saveResponse @("id"))
Write-Field "draft_status" (Get-Prop $saveResponse @("status"))
Write-Field "partial_success" (Get-Prop $saveResponse @("partial_success"))
Write-Field "question_id" $questionId
Write-Field "question_revision_id" $questionRevisionId
Write-Field "rev_no" (Get-Prop $saveResponse @("rev_no"))

Write-Host ""
Write-Host "Draft pipeline smoke completed." -ForegroundColor Green
