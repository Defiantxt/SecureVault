# Disclaimer: This script was built with AI, so it is not guaranteed to work.
# It worked for me, but results may vary on other systems.

[CmdletBinding()]
param(
    [switch]$SkipDependencyInstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (Test-Path -LiteralPath $VenvPython -PathType Leaf) {
    $Python = $VenvPython
}
else {
    $PythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -eq $PythonCommand) {
        throw "Python was not found. Install Python or create .venv before running this script."
    }
    $Python = $PythonCommand.Source
}

function Invoke-Python {
    param([Parameter(Mandatory = $true)][string[]]$PythonArguments)

    & $Python @PythonArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE."
    }
}

$TempParent = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$TempBuild = Join-Path $TempParent ("SecureVault-build-" + [Guid]::NewGuid().ToString("N"))
$TempBuildFull = [IO.Path]::GetFullPath($TempBuild)

if (-not $TempBuildFull.StartsWith($TempParent, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to use a temporary build directory outside the system temp folder."
}

New-Item -ItemType Directory -Path $TempBuildFull | Out-Null
Push-Location $ProjectRoot

try {
    if (-not $SkipDependencyInstall) {
        Invoke-Python -PythonArguments @(
            "-m", "pip", "install", "--disable-pip-version-check",
            "-r", (Join-Path $ProjectRoot "requirements.txt")
        )
    }

    & $Python -c "import PyInstaller; assert tuple(map(int, PyInstaller.__version__.split('.')[:2])) >= (6, 15)"
    if ($LASTEXITCODE -ne 0) {
        Invoke-Python -PythonArguments @(
            "-m", "pip", "install", "--disable-pip-version-check",
            "pyinstaller>=6.15"
        )
    }

    $LauncherPath = Join-Path $TempBuildFull "securevault_launcher.py"
    $LauncherSource = @'
"""Build-only launcher for the frozen SecureVault application.

The application source intentionally remains unchanged. This launcher keeps the
database beside the executable while resolving bundled static assets from
PyInstaller's private extraction directory.
"""

import os
import sys
from pathlib import Path


if getattr(sys, "frozen", False):
    _BUNDLE_ROOT = Path(sys._MEIPASS).resolve()
    _STATIC_ROOT = (_BUNDLE_ROOT / "static").resolve()
    _EXE_ROOT = Path(sys.executable).resolve().parent
    os.chdir(_EXE_ROOT)

    def _bundled_static_path(value):
        try:
            raw_path = os.fspath(value)
        except TypeError:
            return value

        if isinstance(raw_path, bytes):
            raw_path = os.fsdecode(raw_path)
        if os.path.isabs(raw_path):
            return value

        normalized = os.path.normpath(raw_path)
        candidate = (_BUNDLE_ROOT / normalized).resolve()
        try:
            candidate.relative_to(_STATIC_ROOT)
        except ValueError:
            return value

        if candidate.exists():
            return os.fspath(candidate)
        return value

    _original_listdir = os.listdir

    def _listdir_from_bundle(path="."):
        return _original_listdir(_bundled_static_path(path))

    os.listdir = _listdir_from_bundle

    from PIL import Image

    _original_image_open = Image.open

    def _image_open_from_bundle(fp, *args, **kwargs):
        return _original_image_open(_bundled_static_path(fp), *args, **kwargs)

    Image.open = _image_open_from_bundle

    if os.environ.get("SECUREVAULT_BUILD_PROBE") == "1":
        import argon2.low_level
        import cryptography
        import customtkinter
        import keyring

        with Image.open("static/logo.png") as image:
            image.verify()
        if "plus_icon.png" not in os.listdir("static/icons"):
            raise RuntimeError("Bundled SecureVault icons were not found.")
        if type(keyring.get_keyring()).__module__ != "keyring.backends.Windows":
            raise RuntimeError("The Windows Credential Manager backend was not bundled.")
        raise SystemExit(0)


import main  # noqa: E402,F401 - importing starts the GUI application
'@

    [IO.File]::WriteAllText(
        $LauncherPath,
        $LauncherSource,
        [Text.UTF8Encoding]::new($false)
    )

    $DistPath = Join-Path $ProjectRoot "dist"
    $WorkPath = Join-Path $TempBuildFull "work"
    $SpecPath = Join-Path $TempBuildFull "spec"
    $StaticSource = Join-Path $ProjectRoot "static"

    Invoke-Python -PythonArguments @(
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name", "SecureVault",
        "--distpath", $DistPath,
        "--workpath", $WorkPath,
        "--specpath", $SpecPath,
        "--paths", $ProjectRoot,
        "--add-data", ($StaticSource + ";static"),
        "--collect-all", "customtkinter",
        "--collect-submodules", "keyring.backends",
        "--copy-metadata", "keyring",
        $LauncherPath
    )

    $ExePath = Join-Path $DistPath "SecureVault.exe"
    if (-not (Test-Path -LiteralPath $ExePath -PathType Leaf)) {
        throw "PyInstaller finished without creating $ExePath."
    }

    $OldProbeValue = $env:SECUREVAULT_BUILD_PROBE
    try {
        $env:SECUREVAULT_BUILD_PROBE = "1"
        $Probe = Start-Process -FilePath $ExePath -WindowStyle Hidden -Wait -PassThru
        if ($Probe.ExitCode -ne 0) {
            throw "The packaged executable failed its self-check with exit code $($Probe.ExitCode)."
        }
    }
    finally {
        $env:SECUREVAULT_BUILD_PROBE = $OldProbeValue
    }

    $Exe = Get-Item -LiteralPath $ExePath
    Write-Host ""
    Write-Host "Build complete: $($Exe.FullName)"
    Write-Host ("Size: {0:N1} MB" -f ($Exe.Length / 1MB))
    Write-Host "The existing vault.db was not included. At runtime, vault.db stays beside the EXE."
}
finally {
    Pop-Location
    if (Test-Path -LiteralPath $TempBuildFull) {
        Remove-Item -LiteralPath $TempBuildFull -Recurse -Force
    }
}
