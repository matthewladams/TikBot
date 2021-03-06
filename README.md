# TikBot
 A super simple Discord bot designed for helping you share TikToks without actually having to have your friends open TikTok.
 
 TikBot will download any TikTok (or other supported link in youtube-dl) linked in a Discord channel it is in, and post the video file directly. 
 In cases where the file is too large for Discord's free tier, the video will be compressed to fit first.
 
 # Installation & Usage
 Requirements: Python 2/3
 
 1. Set Discord access token into ```.env``` as ```TOKEN=$yourTokenGoesHere```
 
 2. Add the bot to the Discord server you wish to run it in.
 
 3. Setup any channel in the Discord server with a name starting with ```tik-tok```
 
 4. Ensure the bot has permission to post attachments and messages in the channel.
 
 5. Install required packages with ```pip install -r requirements.txt ```
 
 6. Run the bot ```python main.py```
 
 # Notes
 Not recommended to be available as a public bot due to the bandwidth and processing requirements of downloading and encoding videos.
