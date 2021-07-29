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

    bitrateKilobits = result.videoBitrate
    # Calc video first
    if(duration != 0):
        bitrateKilobits = (7000 * 8)/duration
        result.videoBitrate = round(bitrateKilobits)

    # Don't ever drop to full potato
    if(bitrateKilobits < 200):
        result.durationLimited = True
        bitrateKilobits = 200
    
    # Now calculate audio based on our remaining bitrate  
    if(duration != 0):
        remainingKiloBytes = 7800 - (result.videoBitrate/8) * duration
        print("Bits remaining for audio= " + str(remainingKiloBytes))
        calcedAudioBitrate = (remainingKiloBytes*8)/duration
        roundedCalcedBitrate = round(calcedAudioBitrate)
        # Don't set silly high or low
        if(roundedCalcedBitrate > 320):
            roundedCalcedBitrate = 320
        if(roundedCalcedBitrate < 32):
            roundedCalcedBitrate = 32
        result.audioBitrate = roundedCalcedBitrate

    print("Bitrate Calcs: Duration=" + str(duration) + "     Video=" + str(result.videoBitrate) + "       Audio=" + str(result.audioBitrate))
    return result

def calculateBitrateAudioOnly(duration: int) -> CalculationResult:
    result = CalculationResult()

    # Set defaults
    result.videoBitrate = 1
    result.audioBitrate = 320
    result.durationLimited = False

    # Now calculate audio based on our remaining bitrate
    if(duration != 0):
        calcedAudioBitrate = (7500 * 8)/duration
        roundedCalcedBitrate = round(calcedAudioBitrate)
        # Don't set silly high or low
        if(roundedCalcedBitrate > 320):
            roundedCalcedBitrate = 320
        if(roundedCalcedBitrate < 32):
            roundedCalcedBitrate = 32
        result.audioBitrate = roundedCalcedBitrate

    return result
