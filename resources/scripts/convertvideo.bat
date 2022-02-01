@ECHO OFF
TITLE Video conversion and compression script
REM Video conversion and compression script               Learning Equality 2018
REM Usage:
REM    convertvideo.bat  inputfile.mpg  [outputfile.mp4]
REM
REM This script will perform the following conversion steps:
REM   - Apply CRF 32 compression (very aggressive; may need to adjust below)
REM   - Limit the audio track to 32k/sec
REM   - Resize the video to max_height=480
REM You can manually edit the command below to customize the oprations performed.
setlocal


REM 1. Check we have ffmpeg
REM ############################################################################
WHERE ffmpeg >nul 2>nul
IF %ERRORLEVEL% NEQ 0 (
    echo Error: ffmpeg not installed.
    echo Please download zip from https://web.archive.org/web/20200918193047/https://ffmpeg.zeranoe.com/builds/
    echo Then copy the files ffmpeg.exe and ffprobe.exe from bin/ folder to this folder.
    exit /b 1
)


REM 2. Parse input filename
REM ############################################################################
IF NOT "%~1" == "" (
    set "INFILE=%~1"
) else (
    echo ERROR: Missing argument inputfile.mp4
    echo Usage:   convertvideo.bat  inputfile.mp4  [outputfile.mp4]
    exit /b 2
)

REM 3. Prepare output filename
REM ############################################################################
IF NOT "%~2" == "" (
    set "OUTFILE=%~2"
) else (
    set "OUTFILE=%INFILE:~0,-4%-converted.mp4"
)


REM 4. Do conversion
REM ############################################################################
echo Calling ffmpeg to convert: %INFILE% --to--^> %OUTFILE%
ffmpeg -i "%INFILE%" ^
    -b:a 32k -ac 1 ^
    -vf scale="'w=-2:h=trunc(min(ih,480)/2)*2'" ^
    -crf 32 ^
    -profile:v baseline -level 3.0 -preset slow -v error -strict -2 -stats ^
    -y "%OUTFILE%"


echo Conversion done.
endlocal
