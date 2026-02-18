@echo off
REM ============================================================
REM   Rust+ FCM Registration Helper (Windows)
REM ============================================================
echo.
echo Rust+ Companion Bot - FCM Registration
echo ============================================================
echo.

REM Set the desktop path
set "DESKTOP=%USERPROFILE%\Desktop"
set "CONFIG_FILE=rustplus.config.json"
set "DESKTOP_CONFIG=%DESKTOP%\%CONFIG_FILE%"

REM Check if config already exists on desktop
if exist "%DESKTOP_CONFIG%" (
    echo Found existing %CONFIG_FILE% on Desktop
    echo.
    set /p "OVERWRITE=Re-register anyway? (y/N): "
    if /i not "%OVERWRITE%"=="y" (
        echo.
        echo Setup already complete!
        echo To pair a server: Join Rust, press ESC - Rust+ - Pair Server
        pause
        exit /b 0
    )
    echo.
)

echo Step 1: Checking Node.js installation...
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js not found!
    echo.
    echo Please install Node.js from https://nodejs.org
    echo Then re-run this script.
    pause
    exit /b 1
)

echo Node.js: OK
echo.

echo Step 2: Installing Rust+ FCM package...
echo This may take a minute...
echo.
call npm install -g @liamcottle/rustplus.js
if errorlevel 1 (
    echo.
    echo ERROR: Package installation failed!
    echo.
    echo Try running as Administrator:
    echo   Right-click this file - Run as administrator
    pause
    exit /b 1
)

echo.
echo Step 3: Starting FCM registration...
echo.
echo A Chrome window will open for Steam login.
echo Sign in with your Steam account.
echo.
pause

REM Change to desktop directory for registration
cd /d "%DESKTOP%"

REM Try multiple ways to run the command
rustplus.js fcm-register
if errorlevel 1 (
    echo.
    echo Trying alternative method...
    npx @liamcottle/rustplus.js fcm-register
    if errorlevel 1 (
        echo.
        echo ERROR: Could not start registration.
        echo.
        echo Please try running this command manually:
        echo   npx @liamcottle/rustplus.js fcm-register
        pause
        exit /b 1
    )
)

echo.
echo ============================================================

REM Check if config was created on desktop
if exist "%DESKTOP_CONFIG%" (
    echo.
    echo SUCCESS! Registration complete.
    echo.
    echo Config file saved to: %DESKTOP_CONFIG%
    echo.
    echo Next steps:
    echo   1. Open Discord and DM your bot
    echo   2. Send the command: !register
    echo   3. Attach the file from your Desktop: %CONFIG_FILE%
    echo   4. Join any Rust server in-game
    echo   5. Press ESC - Rust+ - Pair Server
    echo   6. Bot will auto-connect using YOUR credentials!
    echo.
    echo IMPORTANT: Keep this file private! It contains your Steam credentials.
    echo.
) else (
    REM Check if it was created in current directory instead
    if exist "%CONFIG_FILE%" (
        echo.
        echo Config created in current directory. Moving to Desktop...
        move "%CONFIG_FILE%" "%DESKTOP_CONFIG%" >nul
        if exist "%DESKTOP_CONFIG%" (
            echo SUCCESS! Config moved to: %DESKTOP_CONFIG%
            echo.
            echo Next steps:
            echo   1. Open Discord and DM your bot
            echo   2. Send: !register
            echo   3. Attach: %CONFIG_FILE% from Desktop
            echo.
        ) else (
            echo WARNING: Could not move file to Desktop.
            echo Config file is in: %CD%\%CONFIG_FILE%
            echo.
        )
    ) else (
        echo.
        echo WARNING: Config file not found.
        echo.
        echo If you successfully logged in with Steam, look for:
        echo   rustplus.config.json
        echo.
        echo Common locations:
        echo   - Your Desktop: %DESKTOP%
        echo   - Your home: %USERPROFILE%
        echo   - Current directory: %CD%
        echo.
    )
)

echo.
pause