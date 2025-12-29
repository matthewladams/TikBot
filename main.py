from calculator import calculateBitrate, calculateBitrateAudioOnly
import discord
import os
import ffmpeg
import traceback
import asyncio
import logging
import threading
from dotenv import load_dotenv 
from downloader import download, download_with_retries
from compressionMessages import getCompressionMessage
from validator import extractUrl, isSupportedUrl
from dbInteraction import savePost, doesPostExist
from concurrent.futures import ThreadPoolExecutor

SKIP_STRINGS = ['🙅‍♂️', '🙅‍♀️', '❌']

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
logger = logging.getLogger(__name__)

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=os.getenv("TIKBOT_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

def start_management_ui():
    enabled = os.getenv("TIKBOT_MANAGEMENT_UI_ENABLED", "true").lower() not in {"0", "false", "no"}
    if not enabled:
        return
    from management_ui import run as run_management_ui
    thread = threading.Thread(target=run_management_ui, name="management-ui", daemon=True)
    thread.start()
    logger.info("Management UI running on port %s", os.getenv("TIKBOT_MANAGEMENT_UI_PORT", "8080"))

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
        logger.warning("Failed to send error message: %s", e)

async def handle_audio_conversion(message, url):
    """Handles audio conversion requests in DMs"""
    try:
        await message.author.send('Attempting to turn this into a MP3 for ya.')
        
        downloadResponse = download(url)
        fileName = downloadResponse['fileName']
        duration = downloadResponse['duration']
        messages = downloadResponse['messages']

        logger.info("Downloaded: %s For User: %s", fileName, message.author)

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
        
        isUnsupportedCodec = not any(track["codec_name"] in ["h264", "hevc"] for track in video_streams)

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
                savePost(
                    message.author.name,
                    downloadResponse['videoId'],
                    downloadResponse.get('platform', 'unknown'),
                    message.id,
                )
            except Exception as e:
                logger.warning("Failed to save post details: %s", e)
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
        
        logger.info("Duration = %s", duration)
        if not duration:
            try:
                probe = ffmpeg.probe(fileName)
                format_duration = float(probe.get('format', {}).get('duration') or 0)
                stream_duration = 0.0
                for stream in probe.get('streams', []):
                    if stream.get('codec_type') == 'video' and stream.get('duration'):
                        stream_duration = float(stream['duration'])
                        break
                duration = format_duration or stream_duration or 0
                logger.info("Resolved duration via ffprobe: %s", duration)
            except Exception as e:
                logger.warning("Failed to probe duration for %s: %s", fileName, e)
        calcResult = calculateBitrate(duration)
        compressed_filename = os.path.join(
            os.path.dirname(fileName),
            f"small_{os.path.basename(os.path.splitext(fileName)[0])}.mp4"
        )

        try:
            # Adjust FFmpeg settings for better control
            output_kwargs = {
                'c:v': 'libx265',              # H.265 codec for better compression
                'b:v': f"{calcResult.videoBitrate}k",
                'maxrate': f"{calcResult.videoBitrate}k",  # Enforce maximum bitrate
                'c:a': 'aac',                  # AAC is widely supported for audio
                'b:a': f"{calcResult.audioBitrate}k",
                'bufsize': f"{2 * calcResult.videoBitrate}k",
                'vf': 'scale=-2:720',          # Scale to 720p while maintaining aspect ratio
                'pix_fmt': 'yuv420p',
                'profile:v': 'main',
                'tag:v': 'hvc1',               # iOS-friendly HEVC tag
                'preset': 'fast',            # Balance between speed and compression
                'fs': int(file_size_limit),    # Hard cap file length
                'movflags': '+faststart',      # Make MP4 streamable
                'f': 'mp4',                    # Container format for H.265
            }
            if calcResult.maxDuration:
                output_kwargs['t'] = calcResult.maxDuration

            ffmpeg.input(fileName).output(
                compressed_filename,
                **output_kwargs
            ).run(overwrite_output=True)
            
            # Check file size after compression
            compressed_file_size = os.stat(compressed_filename).st_size
            if compressed_file_size > file_size_limit:
                await message.channel.send(
                    f"⚠️ Error: Compressed file size is {compressed_file_size / 1_000_000:.2f}MB, exceeding the 8MB limit."
                )
                return
            
            original_probe = ffmpeg.probe(fileName)
            compressed_probe = ffmpeg.probe(compressed_filename)

            original_duration = float(original_probe.get('format', {}).get('duration') or 0)
            if not original_duration:
                original_duration = float(original_probe.get('streams', [{}])[0].get('duration', 0) or 0)

            compressed_duration = float(compressed_probe.get('format', {}).get('duration') or 0)
            if not compressed_duration:
                compressed_duration = float(compressed_probe.get('streams', [{}])[0].get('duration', 0) or 0)
            
            if compressed_duration < original_duration and compressed_duration > 1:
                # Check if the difference is greater than 1 second or 5% of the original duration
                if (original_duration - compressed_duration) > max(1, 0.05 * original_duration):
                    await message.channel.send(
                        f"⚠️ Warning: Video was truncated from {original_duration:.1f}s to {compressed_duration:.1f}s to maintain quality within file size limits."
                    )
            elif(calcResult.durationLimited):
                await message.channel.send(
                    f"⚠️ Warning: Video was truncated to maintain quality within file size limits."
                )
            
            with open(compressed_filename, 'rb') as fp:
                await message.channel.send(file=discord.File(fp, str(compressed_filename)))
                
                if calcResult.durationLimited:
                    await message.channel.send('Video duration was limited to keep quality above total potato.')
                
                try:
                    savePost(
                        message.author.name,
                        downloadResponse['videoId'],
                        downloadResponse.get('platform', 'unknown'),
                        message.id,
                    )
                except Exception as e:
                    logger.warning("Failed to save post details: %s", e)
                    
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

        logger.info("Got URL: %s For User: %s", url, message.author)

        # Skip download if any skip strings are present
        if any(skip_str in message.content for skip_str in SKIP_STRINGS):
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

        def notify_retry(_attempt, _response):
            if not silentMode:
                asyncio.get_running_loop().create_task(
                    message.channel.send('Download failed. Retrying!', delete_after=10)
                )

        try:
            downloadResponse = download_with_retries(url, retries=4, on_retry=notify_retry)
        except Exception as e:
            await send_error_message(
                message.channel,
                "Failed to download after multiple attempts.",
                e
            )
            return

        fileName = downloadResponse['fileName']
        duration = downloadResponse['duration']
        messages = downloadResponse['messages']
        repost = downloadResponse['repost']
        repostOriginalMesssageId = downloadResponse['repostOriginalMesssageId']

        logger.info("Downloaded: %s For User: %s", fileName, message.author)

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

        # Post a temporary download method note for TikTok.
        if (
            not silentMode
            and downloadResponse.get('platform') == 'tiktok'
            and messages
            and not messages.startswith("Error")
        ):
            await message.channel.send(messages, delete_after=10)

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
        logger.error("Unexpected error in handleMessage: %s", error_traceback)
        await send_error_message(
            message.channel or message.author,
            "Something unexpected happened while processing your request.",
            e
        )

@client.event
async def on_ready():
    logger.info('We have logged in as %s', client.user)

@client.event
async def on_message(message):
    await handleMessage(message)

if __name__ == "__main__":
    start_management_ui()
    client.run(os.getenv('TOKEN'))
