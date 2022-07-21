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
    "Preparing this video for it's debut in A Bugs Life 2 - Electric Boogaloo.",
    "Ant-Man could have solved the whole Thanos thing with his shrinking technology. I'm gonna shrink your video, you do the rest if the purple guy shows up OK?",
    "Will you be my pocket sage if I shrink this to pocket size for you 👉👈",
    "_Veigar voice_ It's only a short video? Is that short joke?!",
    "Chrissy will wake up when she hears this one right?",
    "With how big this video is you're gonna get me in trouble...",
    "Go wash your rice, your video will be with you in a momement.",
    "Today is $currentDay, which means that ~~Gandalf~~ I will get to ~~lick~~ serve your ~~graham cracker~~ video. It is my favourite activity",
    "Somebody once told me the world is gonna roll me. Making your video the sharpest tool in the shed.",
    "I'm leaving this TikTok in my compression algorithms for a week, or, until something interesting happens.",
    "Look at how big that thing is. It's so funny... But at the end of the day it's not that funny is it. Because there could be orphans playing in this channel and then this TikTok crushes the orphans to death. And then you had to live with the guilt of killing orphans for your whole life.",
    "I wanna gooooo hoooome. But instead I'm shrinking your TikToks, for eternity.",
    "Did you have to watch an Oodie ad to see this? If I had a nickel for every time I saw one I'd be able to make your video smaller faster, give me a minute.",
    "Твой ТикТок? НАШ ТикТок. То, что я делаю меньше для всех в этот самый момент.",
    "Welcome to the worst year ever, we're we'll get through this together. This TikTok I'm making smaller will help, I'm sure",
    ]
    
def getCompressionMessage():
    number = randrange(len(messages))
    return messages[number]
