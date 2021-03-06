import discord
import os
import ffmpeg
from dotenv import load_dotenv 
from downloader import download
from compressionMessages import getCompressionMessage

load_dotenv()

client = discord.Client()

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))

@client.event
async def on_message(message):
    # Only do anything in TikTok channels
    if(not message.channel.name.startswith("tik-tok")):
        return

    # Ignore our own messages
    if message.author == client.user:
        return

    # Be polite!
    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')

    fileName = ""
    duration = 0
    messages = ""

    if message.content.startswith('https'):
        await message.channel.send('TikBot downloading video now!')
        downloadResponse = download(message.content)
        fileName = downloadResponse['fileName']
        duration = downloadResponse['duration']
        messages = downloadResponse['messages']

        print("Downloaded: " + fileName + " For User: " + str(message.author))

        if(messages.startswith("Error")):
            await message.channel.send('TikBot has failed you. Consider berating my human if this was not expected.\Message: ' + messages)
            return
    else:
        return

    # Check file size, if it's small enough just send it!
    fileSize = os.stat(fileName).st_size

    if(fileSize < 8000000):
        with open(fileName, 'rb') as fp:
            await message.channel.send(file=discord.File(fp, str(fileName)))
        os.remove(fileName)

    else:
        # We need to compress the file below 8MB or discord will make a sad
        compressionMessage = getCompressionMessage()
        await message.channel.send(compressionMessage)
        print("Duration = " + str(duration))
        # Give us 7MB files with VBR encoding to allow for some overhead
        bitrateKilobits = 0
        if(duration != 0):
            bitrateKilobits = (7000 * 8)/duration
            bitrateKilobits = round(bitrateKilobits)
        else:
            bitrateKilobits = 800
        print("Calced bitrate = " + str(bitrateKilobits))
        ffmpeg.input(fileName).output("small_" + fileName, **{'b:v': str(bitrateKilobits) + 'k', 'threads': '4'}).run()
        with open("small_" + fileName, 'rb') as fp:
            await message.channel.send(file=discord.File(fp, str("small_" + fileName)))
        # Delete the compressed and original file
        os.remove(fileName)
        os.remove("small_" + fileName)


client.run(os.getenv('TOKEN'))
