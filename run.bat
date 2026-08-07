@echo off
echo Starting Django Backend Server...
cd django_backend
start cmd /k "..\venv\Scripts\activate.ps1 & python manage.py runserver"

echo Backend server started on port 8000.
echo Opening the frontend in your browser...
cd ..
start uploader.html
