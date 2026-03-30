# Django Management Commands (Windows PowerShell)

# Help
function Show-Help {
    Write-Host "Available commands:" -ForegroundColor Green
    Write-Host "  .\manage.ps1 install         - Install dependencies"
    Write-Host "  .\manage.ps1 migrate         - Run database migrations"
    Write-Host "  .\manage.ps1 makemigrations  - Create new migrations"
    Write-Host "  .\manage.ps1 createsuperuser - Create Django superuser"
    Write-Host "  .\manage.ps1 run             - Run development server"
    Write-Host "  .\manage.ps1 test            - Run tests"
    Write-Host "  .\manage.ps1 lint            - Run linting"
    Write-Host "  .\manage.ps1 format          - Format code with black"
    Write-Host "  .\manage.ps1 clean           - Remove Python cache files"
    Write-Host "  .\manage.ps1 collectstatic   - Collect static files"
    Write-Host "  .\manage.ps1 shell           - Open Django shell"
}

# Main script
param (
    [Parameter(Position=0)]
    [string]$Command = "help"
)

switch ($Command) {
    "install" {
        pip install -r requirements.txt
    }
    "migrate" {
        python manage.py migrate
    }
    "makemigrations" {
        python manage.py makemigrations
    }
    "createsuperuser" {
        python manage.py createsuperuser
    }
    "run" {
        python manage.py runserver
    }
    "test" {
        pytest
    }
    "lint" {
        flake8 .
        pylint --load-plugins pylint_django --django-settings-module=Backend.settings Backend/ users/ api/ core/
    }
    "format" {
        black --line-length 120 .
        isort .
    }
    "clean" {
        Get-ChildItem -Path . -Filter "__pycache__" -Recurse -Directory | Remove-Item -Recurse -Force
        Get-ChildItem -Path . -Filter "*.pyc" -Recurse -File | Remove-Item -Force
        Get-ChildItem -Path . -Filter ".pytest_cache" -Recurse -Directory | Remove-Item -Recurse -Force
        Get-ChildItem -Path . -Filter "*.egg-info" -Recurse -Directory | Remove-Item -Recurse -Force
    }
    "collectstatic" {
        python manage.py collectstatic --noinput
    }
    "shell" {
        python manage.py shell
    }
    default {
        Show-Help
    }
}
