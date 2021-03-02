import discord
import os
import ffmpeg
from dotenv import load_dotenv 
from downloader import download

load_dotenv()

client = discord.Client()

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')

    if message.content.startswith('https'):
        await message.channel.send('TikBot downloading video now!')
        downloadResult = download(message.content)
        print(downloadResult)

        if(downloadResult.startswith("Error")):
            await message.channel.send('TikBot has failed you. Consider berating my human if this was not expected.')
            return

    # Check file size, if it's small enough just send it!
    fileSize = os.stat(downloadResult).st_size

    if(fileSize < 8000000):
        with open(downloadResult, 'rb') as fp:
            await message.channel.send(file=discord.File(fp, str(downloadResult)))
        os.remove(downloadResult)

    else:
        # We need to compress the file below 8MB or discord will make a sad
        await message.channel.send('TikBot will compress your video for you as it is too chonky, please give me a sec.')
        ffmpeg.input(downloadResult).output("small_" + downloadResult, **{'b:v': '1000k'}).run()
        with open("small_" + downloadResult, 'rb') as fp:
            await message.channel.send(file=discord.File(fp, str("small_" + downloadResult)))
        # Delete the compressed and original file
        os.remove(downloadResult)
        os.remove("small_" + downloadResult)


client.run(os.getenv('TOKEN'))
