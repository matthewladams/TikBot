from calculator import calculateBitrate, calculateBitrateAudioOnly
import discord
import os
import ffmpeg
import time
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

async def handleMessage(message):
    # Ignore our own messages
    if message.author == client.user:
        return

    fileName = ""
    duration = 0
    messages = ""

    # Do special things in DMs
    if(type(message.channel) is discord.DMChannel):
        if message.content.startswith('🎵'):
            url = message.content.replace('🎵', '')
            await message.author.send('Attempting to turn this into a MP3 for ya.')

            downloadResponse = download(url)
            fileName = downloadResponse['fileName']
            duration = downloadResponse['duration']
            messages = downloadResponse['messages']

            print("Downloaded: " + fileName + " For User: " + str(message.author))

            if(messages.startswith("Error")):
                await message.author.send('TikBot has failed you. Consider berating my human if this was not expected.\nMessage: ' + messages)
                return

            audioFilename = "audio_" + fileName + ".mp3"
            calcResult = calculateBitrateAudioOnly(duration)
            try:
                ffmpeg.input(fileName).output(audioFilename, **{'b:a': str(calcResult.audioBitrate) + 'k', 'threads': '1'}).run()
                with open(audioFilename, 'rb') as fp:
                    await message.author.send(file=discord.File(fp, str(audioFilename)))
            except Exception as e:
                print(f"Exception sending audio only DM: {e}")
                await message.channel.send('Something about your link defeated my compression mechanism! Link is probably too long. Exception Details: ' + str(e))

            # Delete the compressed and original file
            os.remove(fileName)
            os.remove(audioFilename)
        else:
            await message.author.send('👋')

        return

    # Only do anything in TikTok channels
    if(not message.channel.name.startswith("tik-tok")):
        return

    # Be polite!
    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')

    # Extract and validate the request 
    extractResponse = extractUrl(message.content)
    url = extractResponse["url"]
    messages = extractResponse['messages']
    if(messages.startswith("Error")):
        await message.channel.send('TikBot encountered an error determing a URL. Consider berating my human if this was not expected.\nMessage: ' + messages)
        return

    print("Got URL: " + url + " For User: " + str(message.author))

    # Allow to force not downloading
    if('🙅‍♂️' in message.content or '🙅‍♀️' in message.content):
        return
    
    silentMode = False

    if('🤖' not in message.content):
        # Validate unless we've been reqeuested not to
        validateResponse = isSupportedUrl(url)
        messages = validateResponse['messages']
        if(validateResponse['silentMode']):
            silentMode = True
        if(messages.startswith("Error")):
            await message.channel.send('TikBot encountered an error validating the URL. Consider berating my human if this was not expected.\nMessage: ' + messages)
            return
        if(validateResponse['supported'] == 'false'):
            # Unsupported URL, return silently without doing anything
            return

    if(not silentMode):
        await message.channel.send('TikBot downloading video now!', delete_after=10)
    
    if(not silentMode and messages.startswith("Reddit")):
        await message.channel.send(messages)

    downloadResponse = {'fileName':  '', 'duration':  0, 'messages': '', 'videoId': '', 'repost': False, 'repostOriginalMesssageId': ''}

    retries = 4
    attemptcount = 1
    # Retry because TikTok breaks for no good reason sometimes
    while attemptcount <= retries:
        downloadResponse = download(url)
        messages = downloadResponse['messages']
        if(messages.startswith("Error") and attemptcount < retries and not silentMode):
            await message.channel.send('Download failed. Retrying!', delete_after=10)
            retryMultiplier = os.getenv('TIKBOT_RETRY_MULTI')
            if(retryMultiplier != None):
                time.sleep(int(retryMultiplier) * attemptcount)
            else:
                time.sleep(attemptcount)
        else:
            break
        attemptcount += 1

    fileName = downloadResponse['fileName']
    duration = downloadResponse['duration']
    messages = downloadResponse['messages']
    repost = downloadResponse['repost']
    repostOriginalMesssageId = downloadResponse['repostOriginalMesssageId']

    print("Downloaded: " + fileName + " For User: " + str(message.author))

    if(messages.startswith("Error") and not silentMode):
        await message.channel.send('TikBot has failed you. Consider berating my human if this was not expected.\nMessage: ' + messages)
        return

    if(messages.startswith("Error") and silentMode):
        return
    
    if(repost == True):
        os.remove(fileName) # Don't keep the video
        try:
            originalPost = await message.channel.fetch_message(repostOriginalMesssageId)
            await message.channel.send(messages, reference=originalPost)
            return
        except:
            await message.channel.send(messages + ' (Failed to find original post to reply to)')
            return

    # Check file size, if it's small enough just send it!
    fileSize = os.stat(fileName).st_size

    # ...Unless it's not h264 and the downloader failed us (TikTok has developed a habit of saying a video is h264 in the API but serve a h265 encoded file)
    probe = ffmpeg.probe(fileName)
    video_streams = [stream for stream in probe["streams"] if stream["codec_type"] == "video"]

    isUnsupportedCodec = False
    for track in video_streams:
        if(track["codec_name"] == "hevc"):
            await message.channel.send("Video will not play inline without re-encoding, so I'm gonna do that for you :)", delete_after=180)
            isUnsupportedCodec = True

    if(fileSize < 24000000 and not isUnsupportedCodec):
        with open(fileName, 'rb') as fp:
            await message.channel.send(file=discord.File(fp, str(fileName)))
            #Only save a post if we managed to send it
            try:
                savePost(message.author.name, downloadResponse['videoId'], 'MattIsLazy', message.id)
            except Exception as e:
                print(f"Exception saving post details: {e}")

        os.remove(fileName)

    else:
        # We need to compress the file below 8MB or discord will make a sad
        compressionMessage = getCompressionMessage()
        if not isUnsupportedCodec:
            await message.channel.send(compressionMessage, delete_after=180)
        print("Duration = " + str(duration))
        # Give us 24MB files with VBR encoding to allow for some overhead
        calcResult = calculateBitrate(duration)

        try:
            ffmpeg.input(fileName).output("small_" + fileName, **{'b:v': str(calcResult.videoBitrate) + 'k', 'b:a': str(calcResult.audioBitrate) + 'k', 'fs': '23.9M',  'preset': 'superfast', 'threads': '2'}).run()
            with open("small_" + fileName, 'rb') as fp:
                    await message.channel.send(file=discord.File(fp, str("small_" + fileName)))
                    if(calcResult.durationLimited):
                        await message.channel.send('Video duration was limited to keep quality above total potato.')
                    try:
                        savePost(message.author.name, downloadResponse['videoId'], 'MattIsLazy', message.id)
                    except Exception as e:
                        print(f"Exception saving post details: {e}")
        except Exception as e:
            print(f"Exception posting compressed file: {e}")
            await message.channel.send('Something about your link defeated my compression mechanism! Video is probably too long')
            return # Do not delete these so we can see what was wrong with them later

        # Delete the compressed and original file
        os.remove(fileName)
        os.remove("small_" + fileName)

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))

@client.event
async def on_message(message):
    await handleMessage(message)

client.run(os.getenv('TOKEN'))