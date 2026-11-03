@echo off
setlocal
chcp 65001 >nul
title Atalaya Studio
cd /d "%~dp0"

rem La clave se busca junto a este archivo y, si no esta, dos carpetas mas arriba.
set "ENVFILE="
if exist ".env" (set "ENVFILE=.env") else if exist "..\..\.env" set "ENVFILE=..\..\.env"
if not defined ENVFILE goto sin_env

rem Ruta completa de Docker: funciona aunque cmd no resuelva el nombre corto.
set "DOCKER="
for /f "delims=" %%i in ('where docker 2^>nul ^| findstr /i "\.exe$"') do if not defined DOCKER set "DOCKER=%%i"
if not defined DOCKER goto sin_docker
rem Docker necesita sus programas auxiliares en el PATH.
for %%d in ("%DOCKER%") do set "PATH=%%~dpd;%PATH%"
"%DOCKER%" info >nul 2>nul || goto sin_docker

echo Construyendo Atalaya Studio. La primera vez tarda unos minutos...
"%DOCKER%" build -q -t atalaya-studio . >nul || goto error
"%DOCKER%" rm -f atalaya-studio >nul 2>nul
rem Solo accesible desde este computador. La clave entra como variable; nunca queda en la imagen.
"%DOCKER%" run -d --name atalaya-studio -p 127.0.0.1:8790:8790 --env-file "%ENVFILE%" -v atalaya-datos:/datos atalaya-studio >nul || goto error
timeout /t 4 /nobreak >nul 2>nul
start "" "http://localhost:8790"
echo.
echo Atalaya Studio esta en http://localhost:8790
echo Tus datos quedan guardados aunque lo apagues.
echo Presiona una tecla para apagarlo.
if "%~1"=="" pause >nul
if "%~1"=="" "%DOCKER%" rm -f atalaya-studio >nul
goto fin

:sin_env
echo [ERROR] Falta el archivo .env. Crealo junto a este archivo con la linea: openai=tu-clave
if "%~1"=="" pause
exit /b 1

:sin_docker
echo [ERROR] Docker no esta instalado o no esta encendido. Abre Docker Desktop y vuelve a intentarlo.
if "%~1"=="" pause
exit /b 1

:error
echo [ERROR] No se pudo iniciar Atalaya Studio.
if "%~1"=="" pause
exit /b 1

:fin
endlocal
