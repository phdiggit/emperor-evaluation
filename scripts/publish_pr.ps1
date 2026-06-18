param(
    [Parameter(Mandatory = $true)]
    [string]$Title,

    [Parameter(Mandatory = $false)]
    [string]$Body = "",

    [Parameter(Mandatory = $false)]
    [string]$Base = "GPT",

    [Parameter(Mandatory = $false)]
    [switch]$Draft,

    [Parameter(Mandatory = $false)]
    [switch]$Ready,

    [Parameter(Mandatory = $false)]
    [switch]$UseSshRemote
)

$ErrorActionPreference = "Stop"

function Assert-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing required command: $Name"
    }
}

Assert-Command git
Assert-Command gh

$branch = (git branch --show-current).Trim()
if ([string]::IsNullOrWhiteSpace($branch)) {
    throw "Unable to detect the current branch."
}

if ($UseSshRemote) {
    git remote set-url origin git@github.com:phdiggit/emperor-evaluation.git
}

git push -u origin $branch

$createArgs = @("pr", "create", "--base", $Base, "--head", $branch, "--title", $Title)
if (-not [string]::IsNullOrWhiteSpace($Body)) {
    $createArgs += @("--body", $Body)
}
if ($Draft -or -not $Ready) {
    $createArgs += "--draft"
}

if ($Ready) {
    $createOutput = gh @createArgs
    $prRef = ($createOutput | Select-Object -Last 1).Trim()
    if ([string]::IsNullOrWhiteSpace($prRef)) {
        throw "Unable to determine the created pull request reference."
    }
    gh pr ready $prRef
}
else {
    gh @createArgs
}
