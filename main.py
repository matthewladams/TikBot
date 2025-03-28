from calculator import calculateBitrate, calculateBitrateAudioOnly
import discord
import os
import ffmpeg
import time
import traceback
from dotenv import load_dotenv 
from downloader import download
from compressionMessages import getCompressionMessage
from validator import extractUrl, isSupportedUrl
from dbInteraction import savePost, doesPostExist
from concurrent.futures import ThreadPoolExecutor

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

def get_file_size_limit():
    try:
        size_mb = float(os.getenv('TIKBOT_FILE_SIZE_LIMIT', '8'))
        return size_mb * 1_000_000
    except ValueError:
        return 8_000_000

async def send_error_message(channel, error_message, exception=None):
    """Sends a user-friendly error message to the Discord channel"""
    base_message = f"😅 Oops! {error_message}"
    if exception:
        error_details = str(exception).split('\n')[0]  # Get first line of error
        base_message += f"\nError details: {error_details}"
    try:
        await channel.send(base_message)
    except Exception as e:
        print(f"Failed to send error message: {e}")

async def handle_audio_conversion(message, url):
    """Handles audio conversion requests in DMs"""
    try:
        await message.author.send('Attempting to turn this into a MP3 for ya.')
        
        downloadResponse = download(url)
        fileName = downloadResponse['fileName']
        duration = downloadResponse['duration']
        messages = downloadResponse['messages']

        print(f"Downloaded: {fileName} For User: {message.author}")

        if messages.startswith("Error"):
            await send_error_message(message.author, "Failed to download the audio.", messages)
            return

        audioFilename = f"audio_{fileName}.mp3"
        calcResult = calculateBitrateAudioOnly(duration)
        
        try:
            ffmpeg.input(fileName).output(audioFilename, **{
                'b:a': f"{calcResult.audioBitrate}k", 
                'threads': '1'
            }).run()
            
            with open(audioFilename, 'rb') as fp:
                await message.author.send(file=discord.File(fp, str(audioFilename)))
        except Exception as e:
            await send_error_message(
                message.author,
                "Failed to convert or send the audio file.",
                e
            )
        finally:
            # Clean up files if they exist
            for file in [fileName, audioFilename]:
                if os.path.exists(file):
                    os.remove(file)
                    
    except Exception as e:
        await send_error_message(
            message.author,
            "Something unexpected happened while processing your audio request.",
            e
        )

async def process_video(message, fileName, duration, file_size_limit, downloadResponse):
    """Processes and sends video files"""
    try:
        fileSize = os.stat(fileName).st_size
        
        # Check for unsupported codec
        probe = ffmpeg.probe(fileName)
        video_streams = [stream for stream in probe["streams"] if stream["codec_type"] == "video"]
        
        isUnsupportedCodec = any(track["codec_name"] == "hevc" for track in video_streams)
        
        if isUnsupportedCodec:
            await message.channel.send(
                "Video will not play inline without re-encoding, so I'm gonna do that for you :)", 
                delete_after=180
            )

        if fileSize < file_size_limit and not isUnsupportedCodec:
            await send_original_video(message, fileName, downloadResponse)
        else:
            await send_compressed_video(message, fileName, duration, file_size_limit, downloadResponse, isUnsupportedCodec)
            
    except Exception as e:
        await send_error_message(
            message.channel,
            "Failed to process the video file.",
            e
        )
        raise  # Re-raise to handle cleanup in the caller

async def send_original_video(message, fileName, downloadResponse):
    """Sends the original video file"""
    try:
        with open(fileName, 'rb') as fp:
            await message.channel.send(file=discord.File(fp, str(fileName)))
            try:
                savePost(message.author.name, downloadResponse['videoId'], 'MattIsLazy', message.id)
            except Exception as e:
                print(f"Warning: Failed to save post details: {e}")
    except Exception as e:
        await send_error_message(
            message.channel,
            "Failed to send the original video.",
            e
        )
        raise

async def send_compressed_video(message, fileName, duration, file_size_limit, downloadResponse, isUnsupportedCodec):
    """Compresses and sends the video file"""
    try:
        if not isUnsupportedCodec:
            await message.channel.send(getCompressionMessage(), delete_after=180)
        
        print(f"Duration = {duration}")
        compression_target = (file_size_limit / 1_000_000) - 1
        calcResult = calculateBitrate(duration)
        compressed_filename = f"small_{fileName}"
        
        try:
            # Add more robust ffmpeg settings to prevent cutoffs
            ffmpeg.input(fileName).output(
                compressed_filename,
                **{
                    'b:v': f"{calcResult.videoBitrate}k",
                    'b:a': f"{calcResult.audioBitrate}k",
                    'fs': f'{compression_target}M',
                    'preset': 'veryfast',
                    'threads': '2',
                    'maxrate': f"{calcResult.videoBitrate * 1.5}k",  # Allow some bitrate spikes
                    'bufsize': f"{calcResult.videoBitrate * 2}k",    # Increase buffer size
                    'movflags': '+faststart',                        # Optimize for streaming
                    'avoid_negative_ts': 'make_zero'                # Prevent timestamp issues
                }
            ).run()
            
            original_duration = float(ffmpeg.probe(fileName)['streams'][0]['duration'])
            compressed_duration = float(ffmpeg.probe(compressed_filename)['streams'][0]['duration'])
            
            if compressed_duration < original_duration:
                await message.channel.send(
                    f"⚠️ Warning: Video was truncated from {original_duration:.1f}s to {compressed_duration:.1f}s to maintain quality within file size limits.",
                    delete_after=180
                )
            
            with open(compressed_filename, 'rb') as fp:
                await message.channel.send(file=discord.File(fp, str(compressed_filename)))
                
                if calcResult.durationLimited:
                    await message.channel.send('Video duration was limited to keep quality above total potato.')
                
                try:
                    savePost(message.author.name, downloadResponse['videoId'], 'MattIsLazy', message.id)
                except Exception as e:
                    print(f"Warning: Failed to save post details: {e}")
                    
        except Exception as e:
            await send_error_message(
                message.channel,
                "Failed to compress or send the video. It might be too long or complex.",
                e
            )
            raise
            
    except Exception as e:
        await send_error_message(
            message.channel,
            "Failed to process the compressed video.",
            e
        )
        raise

async def handleMessage(message):
    """Main message handler with comprehensive error handling"""
    try:
        if message.author == client.user:
            return

        # Handle DM messages
        if isinstance(message.channel, discord.DMChannel):
            if message.content.startswith('🎵'):
                url = message.content.replace('🎵', '')
                await handle_audio_conversion(message, url)
            else:
                await message.author.send('👋')
            return

        # Only process messages in TikTok channels
        if not message.channel.name.startswith("tik-tok"):
            return

        # Handle hello command
        if message.content.startswith('$hello'):
            await message.channel.send('Hello!')
            return

        # Extract and validate URL
        try:
            extractResponse = extractUrl(message.content)
            url = extractResponse["url"]
            messages = extractResponse['messages']
            
            if messages.startswith("Error"):
                await send_error_message(
                    message.channel,
                    "Failed to extract a valid URL from your message.",
                    messages
                )
                return
        except Exception as e:
            await send_error_message(
                message.channel,
                "Failed to process the URL from your message.",
                e
            )
            return

        print(f"Got URL: {url} For User: {message.author}")

        # Skip if no download is requested
        if '🙅‍♂️' in message.content or '🙅‍♀️' in message.content:
            return

        silentMode = False

        # Validate URL unless bypassed
        if '🤖' not in message.content:
            try:
                validateResponse = isSupportedUrl(url)
                messages = validateResponse['messages']
                silentMode = validateResponse['silentMode']
                
                if messages.startswith("Error"):
                    await send_error_message(
                        message.channel,
                        "Failed to validate the URL.",
                        messages
                    )
                    return
                    
                if validateResponse['supported'] == 'false':
                    return
            except Exception as e:
                await send_error_message(
                    message.channel,
                    "Failed to validate the URL.",
                    e
                )
                return

        if not silentMode:
            await message.channel.send('TikBot downloading video now!', delete_after=10)
            if messages.startswith("Reddit"):
                await message.channel.send(messages)

        # Download with retries
        downloadResponse = {'fileName': '', 'duration': 0, 'messages': '', 'videoId': '', 'repost': False, 'repostOriginalMesssageId': ''}
        
        retries = 4
        attemptcount = 1
        
        while attemptcount <= retries:
            try:
                downloadResponse = download(url)
                messages = downloadResponse['messages']
                
                if messages.startswith("Error") and attemptcount < retries and not silentMode:
                    await message.channel.send('Download failed. Retrying!', delete_after=10)
                    retryMultiplier = os.getenv('TIKBOT_RETRY_MULTI')
                    time.sleep(int(retryMultiplier or '1') * attemptcount)
                else:
                    break
            except Exception as e:
                if attemptcount == retries:
                    await send_error_message(
                        message.channel,
                        "Failed to download after multiple attempts.",
                        e
                    )
                    return
            attemptcount += 1

        fileName = downloadResponse['fileName']
        duration = downloadResponse['duration']
        messages = downloadResponse['messages']
        repost = downloadResponse['repost']
        repostOriginalMesssageId = downloadResponse['repostOriginalMesssageId']

        print(f"Downloaded: {fileName} For User: {message.author}")

        if messages.startswith("Error"):
            if not silentMode:
                await send_error_message(
                    message.channel,
                    "Failed to download the content.",
                    messages
                )
            return

        # Handle reposts
        if repost:
            try:
                if os.path.exists(fileName):
                    os.remove(fileName)
                    
                originalPost = await message.channel.fetch_message(repostOriginalMesssageId)
                await message.channel.send(messages, reference=originalPost)
            except Exception as e:
                await message.channel.send(f'{messages} (Failed to find original post to reply to)')
            return

        # Process the video
        try:
            await process_video(message, fileName, duration, get_file_size_limit(), downloadResponse)
        finally:
            # Clean up files
            for file in [fileName, f"small_{fileName}"]:
                if os.path.exists(file):
                    os.remove(file)

    except Exception as e:
        error_traceback = traceback.format_exc()
        print(f"Unexpected error in handleMessage: {error_traceback}")
        await send_error_message(
            message.channel or message.author,
            "Something unexpected happened while processing your request.",
            e
        )

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))

@client.event
async def on_message(message):
    await handleMessage(message)

client.run(os.getenv('TOKEN'))