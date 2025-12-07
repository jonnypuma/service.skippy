@echo off
setlocal EnableDelayedExpansion

echo.
echo === Batch EDL Action Type Rewriter ===
echo.

:: Prompt for input and replacement types
set /p findType=Enter the action type to find (e.g. 3): 
set /p replaceType=Enter the action type to replace with (e.g. 6): 

echo.
echo Rewriting all .edl files: replacing type %findType% with %replaceType%...
echo.

for /r %%f in (*.edl) do (
    echo Processing: %%f

    > "%%f.tmp" (
        for /f "tokens=1,2,3*" %%a in ('type "%%f"') do (
            if "%%c"=="%findType%" (
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
