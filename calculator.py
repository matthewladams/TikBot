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

    # Total data budget in kilobits (23500 kilobytes * 8)
    totalDataBudgetKilobits = 23500 * 8

    # Calculate video bitrate first
    if duration != 0:
        bitrateKilobits = totalDataBudgetKilobits / duration
        # Ensure bitrate is not below 200 kbps
        if bitrateKilobits < 200:
            result.durationLimited = True
            bitrateKilobits = 200
        result.videoBitrate = round(bitrateKilobits)

    # Calculate audio bitrate
    if duration != 0:
        # Remaining data for audio in kilobits
        remainingDataKilobits = totalDataBudgetKilobits - (result.videoBitrate * duration)
        calcedAudioBitrate = remainingDataKilobits / duration
        # Ensure audio bitrate is within 32-320 kbps
        calcedAudioBitrate = max(64, min(calcedAudioBitrate, 320))
        result.audioBitrate = round(calcedAudioBitrate)

    return result

def calculateBitrateAudioOnly(duration: int) -> CalculationResult:
    result = CalculationResult()

    # Set defaults
    result.videoBitrate = 1
    result.audioBitrate = 320
    result.durationLimited = False

    # Now calculate audio based on our remaining bitrate
    if(duration != 0):
        calcedAudioBitrate = (23700 * 8)/duration
        roundedCalcedBitrate = round(calcedAudioBitrate)
        # Don't set silly high or low
        if(roundedCalcedBitrate > 320):
            roundedCalcedBitrate = 320
        if(roundedCalcedBitrate < 32):
            roundedCalcedBitrate = 32
        result.audioBitrate = roundedCalcedBitrate

    return result
