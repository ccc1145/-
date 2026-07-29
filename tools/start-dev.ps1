$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $projectRoot 'backend'
$frontendDir = Join-Path $projectRoot 'frontend'

function Find-Command {
    param([string[]]$Names)
    foreach ($name in $Names) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) { return $command.Source }
    }
    return $null
}

function Invoke-Checked {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$FailureMessage
    )
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) { throw $FailureMessage }
}

function Test-HttpService {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest $Url -UseBasicParsing -TimeoutSec 1
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    } catch {
        return $false
    }
}

Write-Host '=== Xiuxian Simulator - one-click startup ===' -ForegroundColor Cyan

$python = Find-Command @('python.exe', 'python3.exe', 'py.exe')
if (-not $python) {
    throw 'Python was not found. Install Python 3.11 or newer and add it to PATH.'
}

$node = Find-Command @('node.exe')
$npm = Find-Command @('npm.cmd')
if (-not $node -or -not $npm) {
    throw 'Node.js/npm was not found. Install Node.js 20 or newer and add it to PATH.'
}

Write-Host '[1/4] Checking backend dependencies...'
$venvDir = Join-Path $backendDir '.venv'
$backendPython = Join-Path $venvDir 'Scripts\python.exe'
if (-not (Test-Path $backendPython)) {
    Write-Host '      Creating an isolated Python environment...'
    Invoke-Checked $python @('-m', 'venv', $venvDir) 'Could not create the backend virtual environment.'
}

& $backendPython -c 'import fastapi, uvicorn, sqlalchemy, yaml, dotenv, httpx, jinja2' 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host '      Missing dependencies detected; installing them now...' -ForegroundColor Yellow
    Invoke-Checked $backendPython @('-m', 'pip', 'install', '-r', (Join-Path $backendDir 'requirements.txt')) `
        'Backend dependency installation failed.'
}

Write-Host '[2/4] Checking frontend dependencies...'
if (-not (Test-Path (Join-Path $frontendDir 'node_modules'))) {
    Push-Location $frontendDir
    try {
        Invoke-Checked $npm @('ci') 'Frontend dependency installation failed.'
    } finally {
        Pop-Location
    }
}

Write-Host '[3/4] Preparing local configuration...'
$backendEnv = Join-Path $backendDir '.env'
if (-not (Test-Path $backendEnv)) {
    Copy-Item (Join-Path $backendDir '.env.example') $backendEnv
    Write-Host '      Created backend/.env. Add an API key there to enable live AI narration.' -ForegroundColor Yellow
}

$frontendEnv = Join-Path $frontendDir '.env'
if (-not (Test-Path $frontendEnv)) {
    @(
        'VITE_USE_MOCK=false'
        'VITE_API_BASE_URL=http://localhost:8000/api'
    ) | Set-Content -Path $frontendEnv -Encoding utf8
}

Write-Host '[4/4] Starting backend and frontend...'
$backendCommand = "Set-Location -LiteralPath '$($backendDir.Replace("'", "''"))'; & '$($backendPython.Replace("'", "''"))' -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
$frontendCommand = "Set-Location -LiteralPath '$($frontendDir.Replace("'", "''"))'; & '$($npm.Replace("'", "''"))' run dev -- --host localhost --port 5173 --strictPort"

if (Test-HttpService 'http://localhost:8000/api/health') {
    Write-Host '      Backend is already running on port 8000; reusing it.' -ForegroundColor Yellow
} else {
    Start-Process powershell.exe -ArgumentList @('-NoExit', '-NoLogo', '-Command', $backendCommand) -WindowStyle Normal | Out-Null
}

if (Test-HttpService 'http://localhost:5173') {
    Write-Host '      Frontend is already running on port 5173; reusing it.' -ForegroundColor Yellow
} else {
    Start-Process powershell.exe -ArgumentList @('-NoExit', '-NoLogo', '-Command', $frontendCommand) -WindowStyle Normal | Out-Null
}

$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Seconds 1
    try {
        if (Test-HttpService 'http://localhost:5173') {
            $ready = $true
            break
        }
    } catch {
        # The development servers are still starting.
    }
}

if ($ready) {
    Start-Process 'http://localhost:5173'
    Write-Host 'Started successfully: http://localhost:5173' -ForegroundColor Green
    Write-Host 'Close the two service windows to stop the project.'
} else {
    Write-Host 'The service windows were opened, but the frontend was not ready within 30 seconds.' -ForegroundColor Yellow
    Write-Host 'Check the backend/frontend windows for startup errors.'
}
