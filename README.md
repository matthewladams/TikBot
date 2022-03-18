# TikBot
 A super simple Discord bot designed for helping you share TikToks without actually having to have your friends open TikTok.
 
 TikBot will download any TikTok (or other supported link in yt_dlp) linked in a Discord channel it is in, and post the video file directly. 
 In cases where the file is too large for Discord's free tier, the video will be compressed to fit first.
 
 # Installation & Usage
 Requirements: Python 3.9+
 
 1. Set Discord access token into ```.env``` as ```TOKEN=$yourTokenGoesHere```
 
 2. Add the bot to the Discord server you wish to run it in.
 
 3. Setup any channel in the Discord server with a name starting with ```tik-tok```
 
 4. Ensure the bot has permission to post attachments and messages in the channel.
 
 5. Install required packages with ```pip install -r requirements.txt ```
 
 6. Run the bot ```python main.py```

## Automatic Domain Configuration
By default the bot will post where a link is from ```'youtube', 'tiktok', 'instagram', 'reddit', 'redd.it'```, or if a 🤖 emoji is included in the message.

If you'd like to modify this list, you can set the ```TIKBOT_AUTO_DOMAINS``` environment variable in ```.env```. Supply a space separated list. 

For example to add Twitter to the automatic set of posts

```TIKBOT_AUTO_DOMAINS=youtube tiktok instagram reddit redd.it twitter```

## Extra Config
### Repost Detection
The bot is capable of detecing reposts if supplied with postgres database credentials. 
Set ```DB_NAME, DB_HOST, DB_USER, DB_PASS, TIKBOT_TIMEZONE`` in ```.env```. Timezone is the IANA name

Only a single table is used, see ```maintenance/create_posts_table.sql``` for a create script for the table.

### Silent Mode
For domains with a mix of supported and unsupported content (e.g. Twitter), you may want the bot to try to post items, but only send a message if it actually gets a video to post.
Set the domains you want this behaviour on as a space separated list in the ```TIKBOT_SILENT_DOMAINS``` environment variable.

For example to only post Twitter videos and have the bot not show anything for text tweets:

```TIKBOT_SILENT_DOMAINS=twitter```

Note that this will also suppress any other messages (aside from repost detection) for these domains as well. Errors will still be logged to the console however.

 # Notes
 Not recommended to be available as a public bot due to the bandwidth and processing requirements of downloading and encoding videos.
