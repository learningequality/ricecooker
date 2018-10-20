#!/usr/bin/env bash
# Video conversion and compression script                 Learning Equality 2018
# Usage:
#   ./convertvideo.sh  inputfile.mp4  [outputfile.mp4]
#
# This script will perform the following conversion steps:
#   - Apply CRF 32 compression (very aggressive; may need to adjust below)
#   - Limit the audio track to 32k/sec
#   - Resize the video to max_height=480
# You can manually edit the command below to customize the oprations performed.
set -e


# 1. Check we have ffmpeg
################################################################################
if [ ! -x "$(command -v ffmpeg)" ]
then
  echo "Error: ffmpeg not installed. Please download from https://www.ffmpeg.org/"
  exit 1
fi

# 2. Parse input filename 
################################################################################
if [ ! -z "$1" ]
then
    INFILE=$1;
else
    echo "ERROR: Missing argument <inputfile.mp4>"
    echo "Usage:   ./convertvideo.sh  inputfile.mp4  [outputfile.mp4]"
    exit 2
fi

# 3. Prepare output filename
################################################################################
DEFULTPREFIX="converted-"
if [ ! -z "$2" ]
then
    OUTFILE=$2;
else
    filename=$(basename -- "$INFILE");
    filename="${filename%.*}";
    extension="${filename##*.}";
    OUTFILE=$DEFULTPREFIX"$filename"".mp4";
fi


# 4. Do conversion
################################################################################
echo "Calling ffmpeg to convert: $INFILE --> $OUTFILE"
ffmpeg -i "$INFILE" \
    -b:a 32k -ac 1 \
    -vf scale="'w=-2:h=trunc(min(ih,480)/2)*2'" \
    -crf 32 \
    -profile:v baseline -level 3.0 -preset slow -v error -strict -2 -stats \
    -y "$OUTFILE"


echo "Conversion done."
