$ErrorActionPreference = "Stop"

$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) {
    $BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path $BundledPython) {
        $PythonExe = $BundledPython
    }
}

if (-not $PythonExe) {
    throw "Python was not found. Install Python 3.12+ or update run.ps1 with your Python path."
}

& $PythonExe -m pixel_annotator @args
