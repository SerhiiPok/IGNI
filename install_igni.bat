cd venv\Lib\site-packages

if exist igni\ (
    del /s /f /q igni\*.*
    for /f %%f in ('dir /ad /b igni\') do rd /s /q igni\%%f
    rd igni\
)

xcopy ..\..\..\igni .\igni\ /E