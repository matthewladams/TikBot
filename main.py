from calculator import calculateBitrate, calculateBitrateAudioOnly
import discord
import os
import ffmpeg
from dotenv import load_dotenv 
from downloader import download
from compressionMessages import getCompressionMessage
from validator import extractUrl, isSupportedUrl
from dbInteraction import savePost, doesPostExist
from concurrent.futures import ThreadPoolExecutor

load_dotenv()

client = discord.Client()

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
    
    if('🤖' not in message.content):
        # Validate unless we've been reqeuested not to
        validateResponse = isSupportedUrl(url)
        messages = validateResponse['messages']
        if(messages.startswith("Error")):
            await message.channel.send('TikBot encountered an error validating the URL. Consider berating my human if this was not expected.\nMessage: ' + messages)
            return
        if(validateResponse['supported'] == 'false'):
            # Unsupported URL, return silently without doing anything
            return

    await message.channel.send('TikBot downloading video now!', delete_after=10)
    downloadResponse = download(url)
    fileName = downloadResponse['fileName']
    duration = downloadResponse['duration']
    messages = downloadResponse['messages']
    repost = downloadResponse['repost']
    repostOriginalMesssageId = downloadResponse['repostOriginalMesssageId']

    print("Downloaded: " + fileName + " For User: " + str(message.author))

    if(messages.startswith("Error")):
        await message.channel.send('TikBot has failed you. Consider berating my human if this was not expected.\nMessage: ' + messages)
        return

    if(repost == True):
        try:
            originalPost = await message.channel.fetch_message(repostOriginalMesssageId)
            await message.channel.send(messages, reference=originalPost)
            return
        except:
            await message.channel.send(messages + ' (Failed to find original post to reply to)')
            return

    # Check file size, if it's small enough just send it!
    fileSize = os.stat(fileName).st_size

    if(fileSize < 8000000):
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
        await message.channel.send(compressionMessage)
        print("Duration = " + str(duration))
        # Give us 7MB files with VBR encoding to allow for some overhead
        calcResult = calculateBitrate(duration)

        try:
            ffmpeg.input(fileName).output("small_" + fileName, **{'b:v': str(calcResult.videoBitrate) + 'k', 'b:a': str(calcResult.audioBitrate) + 'k', 'fs': '7.5M', 'threads': '4'}).run()
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