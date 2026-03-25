MAX_TRANSCODE_DURATION_SECONDS = 181
TRANSCODE_DATA_BUDGET_KILOBITS = (7 * 1024 * 1024 * 8) / 1000
MIN_VIDEO_BITRATE_KBPS = 150
MIN_AUDIO_BITRATE_KBPS = 32
MAX_VIDEO_BITRATE_KBPS = 800
MAX_AUDIO_BITRATE_KBPS = 320
MIN_DURATION_LIMITED_VIDEO_BITRATE_KBPS = 256
MIN_DURATION_LIMITED_AUDIO_BITRATE_KBPS = 64

class CalculationResult:
    videoBitrate: int
    audioBitrate: int
    durationLimited: bool
    maxDuration: int

def calculateBitrate(duration: int) -> CalculationResult:
    result = CalculationResult()

    # Set defaults
    result.videoBitrate = 1500
    result.audioBitrate = 96
    result.durationLimited = False
    result.maxDuration = duration  # Default to the input duration

    effectiveDuration = duration

    if duration > MAX_TRANSCODE_DURATION_SECONDS:
        result.durationLimited = True
        result.maxDuration = MAX_TRANSCODE_DURATION_SECONDS
        effectiveDuration = MAX_TRANSCODE_DURATION_SECONDS

    if effectiveDuration != 0:
        # Calculate maximum allowable total bitrate
        maxTotalBitrate = TRANSCODE_DATA_BUDGET_KILOBITS / effectiveDuration
        minAudioBitrate = (
            MIN_DURATION_LIMITED_AUDIO_BITRATE_KBPS
            if result.durationLimited
            else MIN_AUDIO_BITRATE_KBPS
        )
        minVideoBitrate = (
            MIN_DURATION_LIMITED_VIDEO_BITRATE_KBPS
            if result.durationLimited
            else MIN_VIDEO_BITRATE_KBPS
        )

        # Calculate minimum acceptable bitrate
        minTotalBitrate = (
            MIN_DURATION_LIMITED_VIDEO_BITRATE_KBPS
            + MIN_DURATION_LIMITED_AUDIO_BITRATE_KBPS
        )

        # Check if we're duration limited
        if maxTotalBitrate < minTotalBitrate:
            result.videoBitrate = MIN_DURATION_LIMITED_VIDEO_BITRATE_KBPS
            result.audioBitrate = MIN_DURATION_LIMITED_AUDIO_BITRATE_KBPS
            result.durationLimited = True
            result.maxDuration = min(
                MAX_TRANSCODE_DURATION_SECONDS,
                int(TRANSCODE_DATA_BUDGET_KILOBITS / minTotalBitrate),
            )
            return result

        # Reserve 10% of the total bitrate for audio
        maxAudioBitrate = maxTotalBitrate * 0.1
        maxVideoBitrate = maxTotalBitrate * 0.9

        # Ensure audio bitrate is within 32-320 kbps
        result.audioBitrate = max(
            minAudioBitrate,
            min(round(maxAudioBitrate), MAX_AUDIO_BITRATE_KBPS),
        )

        # Ensure video bitrate is not below 150 kbps and does not exceed its budget
        result.videoBitrate = max(
            minVideoBitrate,
            min(round(maxVideoBitrate), MAX_VIDEO_BITRATE_KBPS),
        )

        # Recalculate total bitrate and adjust if necessary
        totalBitrate = result.videoBitrate + result.audioBitrate
        if totalBitrate > maxTotalBitrate:
            excessBitrate = totalBitrate - maxTotalBitrate
            result.videoBitrate = max(
                minVideoBitrate,
                result.videoBitrate - round(excessBitrate),
            )

            # Mark as duration limited if video bitrate was reduced to the minimum
            if (
                result.videoBitrate == minVideoBitrate
                and result.audioBitrate == minAudioBitrate
            ):
                result.durationLimited = True

    return result

def calculateBitrateAudioOnly(duration: int) -> CalculationResult:
    result = CalculationResult()

    # Set defaults
    result.videoBitrate = 1
    result.audioBitrate = 320
    result.durationLimited = False

    # Now calculate audio based on our remaining bitrate
    if(duration != 0):
        # Use 80% of the total budget for audio to leave some headroom
        calcedAudioBitrate = (8000 * 8 * 0.8)/duration
        roundedCalcedBitrate = round(calcedAudioBitrate)
        # Don't set silly high or low
        if(roundedCalcedBitrate > 320):
            roundedCalcedBitrate = 320
        if(roundedCalcedBitrate < 32):
            roundedCalcedBitrate = 32
        result.audioBitrate = roundedCalcedBitrate

    return result
