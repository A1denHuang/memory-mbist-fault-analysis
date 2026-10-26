param(
    [ValidateSet('iverilog','questa')][string]$Simulator='iverilog',
    [int]$Seeds=60,
    [int]$BlindSeeds=55
)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonCandidates=@(
    (Join-Path $PSScriptRoot '.venv\Scripts\python.exe'),
    (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
)
$pythonCmd=$null
foreach ($candidate in $pythonCandidates) {
    if (Test-Path -LiteralPath $candidate) { $pythonCmd=$candidate; break }
}
if (-not $pythonCmd) {
    $found=Get-Command python -ErrorAction SilentlyContinue
    if ($found) { $pythonCmd=$found.Source }
}
if (-not $pythonCmd) { throw 'Install Python 3.10+ or create .venv first.' }
$depsPath=Join-Path $PSScriptRoot '.deps'
$env:PYTHONPATH=$depsPath
$env:PYTHONIOENCODING='utf-8'
$env:MPLCONFIGDIR=Join-Path $PSScriptRoot 'results\build\mpl'
& $pythonCmd -c "import importlib.util,sys; sys.exit(0 if all(importlib.util.find_spec(m) for m in ('pandas','matplotlib')) else 1)"
if ($LASTEXITCODE -ne 0) {
    & $pythonCmd -m pip install --target $depsPath -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
}
if ($Simulator -eq 'iverilog' -and -not (Get-Command iverilog -ErrorAction SilentlyContinue)) {
    $icarusPath='C:\msys64\ucrt64\bin'
    if (Test-Path -LiteralPath (Join-Path $icarusPath 'iverilog.exe')) {
        $env:PATH=$icarusPath+';'+$env:PATH
    }
}
if ($Simulator -eq 'questa' -and -not (Get-Command vsim -ErrorAction SilentlyContinue)) {
    if (Test-Path -LiteralPath 'D:\Questasim\win64\vsim.exe') {
        $env:PATH='D:\Questasim\win64;'+$env:PATH
    }
}
$outFolder=if ($Simulator -eq 'questa') {'results_questa'} else {'results'}
& $pythonCmd scripts/run.py --simulator $Simulator --seeds $Seeds --blind-seeds $BlindSeeds --out $outFolder
if ($LASTEXITCODE -ne 0) { throw 'Project regression failed. See the displayed error.' }
Write-Host "Completed. Open $outFolder\report.md"
