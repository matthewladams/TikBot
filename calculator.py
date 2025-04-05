class CalculationResult:
    videoBitrate: int
    audioBitrate: int
    durationLimited: bool

def calculateBitrate(duration: int) -> CalculationResult:
    result = CalculationResult()

    # Set defaults
    result.videoBitrate = 800
    result.audioBitrate = 64
    result.durationLimited = False

    # Total data budget in kilobits (7.5 MB * 8 bits per byte / 1000 to convert to kilobits)
    totalDataBudgetKilobits = (7.5 * 1024 * 1024 * 8) / 1000

    if duration != 0:
        # Calculate maximum allowable total bitrate
        maxTotalBitrate = totalDataBudgetKilobits / duration

        # Calculate minimum acceptable bitrate
        minTotalBitrate = 150 + 32  # Minimum video + minimum audio

        # Check if we're duration limited
        if maxTotalBitrate < minTotalBitrate:
            result.videoBitrate = 150
            result.audioBitrate = 32
            result.durationLimited = True
            return result

        # Reserve 10% of the total bitrate for audio
        maxAudioBitrate = maxTotalBitrate * 0.1
        maxVideoBitrate = maxTotalBitrate * 0.9

        # Ensure audio bitrate is within 32-320 kbps
        result.audioBitrate = max(32, min(round(maxAudioBitrate), 320))

        # Ensure video bitrate is not below 150 kbps and does not exceed its budget
        result.videoBitrate = max(150, min(round(maxVideoBitrate), 800))

        # Recalculate total bitrate and adjust if necessary
        totalBitrate = result.videoBitrate + result.audioBitrate
        if totalBitrate > maxTotalBitrate:
            excessBitrate = totalBitrate - maxTotalBitrate
            result.videoBitrate = max(150, result.videoBitrate - round(excessBitrate))

            # Mark as duration limited if video bitrate was reduced to the minimum
            if result.videoBitrate == 150 and result.audioBitrate == 32:
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
