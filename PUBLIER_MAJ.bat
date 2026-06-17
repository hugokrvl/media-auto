@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ===============================================
echo    PUBLIER LES MISES A JOUR - MediaAuto
echo ===============================================
echo.
set "msg=Mise a jour"
set /p "msg=Decris ta modif (ou appuie sur Entree) : "
echo.
echo [1/3] Preparation des fichiers...
git add -A
echo [2/3] Enregistrement...
git commit -m "%msg%"
echo [3/3] Envoi vers GitHub...
git push
echo.
echo ===============================================
echo    Termine ! GitHub Actions va se declencher
echo    cette nuit a 1h du matin automatiquement.
echo ===============================================
echo.
pause
