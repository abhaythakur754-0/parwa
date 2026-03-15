# PARWA Development Environment Setup Script (PowerShell)
# Run this ONCE after Python is installed to set up the virtual environment.
# Usage: .\setup_env.ps1

Write-Host "Creating virtual environment..." -ForegroundColor Cyan
python -m venv venv

Write-Host "Activating virtual environment..." -ForegroundColor Cyan
.\venv\Scripts\Activate.ps1

Write-Host "Upgrading pip..." -ForegroundColor Cyan
python -m pip install --upgrade pip

Write-Host "Installing all project dependencies..." -ForegroundColor Cyan
pip install -r requirements.txt

Write-Host ""
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "To activate the venv in future sessions, run: .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
