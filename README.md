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

## Docker & Deno support
The provided `Dockerfile` builds the bot on a slim Python image and also installs `ffmpeg` and the Deno JavaScript runtime.

Note: The container image includes Deno so the bot can optionally use Deno to run yt-dlp remote components.

## Docker Hub publishing from GitHub Actions
This repo includes a GitHub Actions workflow to build and push the Docker image to Docker Hub on pushes to `master`, and on version tags like `v1.2.3`.

Setup in GitHub:
1. Create Docker Hub credentials (use a personal access token).
2. Add repo secrets:
   - `DOCKERHUB_USERNAME`
   - `DOCKERHUB_TOKEN`
3. Add a repo variable:
   - `DOCKERHUB_REPOSITORY` (example: `yourname/tikbot`)


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

### Management UI (local only)
Run a lightweight web UI to view and edit repost tracking entries. It is restricted to localhost by default.

1. Install dependencies: ```pip install -r requirements.txt```
2. Start the UI: ```python management_ui.py```
3. Open ```http://127.0.0.1:5001/posts```

Optional environment overrides:
- ```TIKBOT_MANAGEMENT_HOST``` (default ```127.0.0.1```)
- ```TIKBOT_MANAGEMENT_PORT``` (default ```5001```)

To run the UI alongside the Discord bot:
1. Set ```TIKBOT_MANAGEMENT_UI=true```
2. Start the bot as usual with ```python main.py```

If you're running in Docker and want to access it from your host machine, set
```TIKBOT_MANAGEMENT_HOST=0.0.0.0``` and map the port (e.g. ```-p 5001:5001```).

### Silent Mode
For domains with a mix of supported and unsupported content (e.g. Twitter), you may want the bot to try to post items, but only send a message if it actually gets a video to post.
Set the domains you want this behaviour on as a space separated list in the ```TIKBOT_SILENT_DOMAINS``` environment variable.

For example to only post Twitter videos and have the bot not show anything for text tweets:

```TIKBOT_SILENT_DOMAINS=twitter```

Note that this will also suppress any other messages (aside from repost detection) for these domains as well. Errors will still be logged to the console however.

 # Notes
 Not recommended to be available as a public bot due to the bandwidth and processing requirements of downloading and encoding videos.
