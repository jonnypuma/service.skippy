@echo off
setlocal EnableDelayedExpansion

echo.
echo === EDL Batch Rewriter: Replace All Types Except 4 ===
echo.

:: Prompt for replacement type
set /p replaceType=Enter the action type to replace all non-4 values with (e.g. 6): 

echo.
echo Processing all .edl files: updating all types not equal to 4 to %replaceType%...

echo.

for /r %%f in (*.edl) do (
    echo Processing: %%f

    > "%%f.tmp" (
        for /f "tokens=1,2,3" %%a in ('type "%%f"') do (
            if not "%%c"=="4" (
                echo %%a %%b %replaceType%
            ) else (
                echo %%a %%b %%c
            )
        )
    )
    move /Y "%%f.tmp" "%%f" >nul
    echo Done: %%f
)

echo.
echo All files processed.
pause
