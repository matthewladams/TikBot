from random import randrange

messages = [
    "What a chungus of a TikTok, compressing it for you. Smaller boi incoming soon.",
    "TikBot will compress your TikTok for you as it is too chonky, please give me a sec.",
    "Taking your big TikTok and making it smaller. Just a moment.",
    "Compressing TikTok to fit in Discord's size limitation, please wait a moment.",
    "Your TikTok needs to lay off the Maccas, performing digital liposuction.",
    "That's a PATT (Phat Ass Tik Tok), squeezing it through the door for ya.",
    "That's a big TikTok, are you compensating for something? Compressing it now.",
    "Flat Is Justice. Making your video conform.",
    "Thick thighs save lives, but this thick-tok won't fit into these Discord jeans. Shrinking it down.",
    "With how much money you could make on DoorDash, you could have just had Nitro and not needed me!.",
    ]
    
def getCompressionMessage():
    number = randrange(len(messages))
    return messages[number]
