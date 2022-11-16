cd E:\Programs\python3.7\Lib

if exist igni\ (
    del /s /f /q igni\*.*
    for /f %%f in ('dir /ad /b igni\') do rd /s /q igni\%%f
    rd igni\
)

xcopy E:\projects\the_witcher\content_pipeline\igni .\igni\ /E