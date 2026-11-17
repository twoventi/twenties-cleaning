@echo off
rem Avvio da codice sorgente su Windows (per sviluppatori). Gli utenti scaricano il .exe dalle Releases.
cd /d "%~dp0"
python src\twenties_cleaning.py
pause
