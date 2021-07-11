import psycopg2
from dotenv import load_dotenv 
import os
from datetime import datetime

try:
	load_dotenv()
	host = os.getenv('DB_HOST')
	dbUser = os.getenv('DB_USER')
	dbPass = os.getenv('DB_PASS')
	dbName = os.getenv('DB_NAME')
	conn = psycopg2.connect(f"host={host} dbname={dbName} user={dbUser} password={dbPass}")
except:
	print("Cannot load DB details, repost detection will not be available")


def savePost(userId, postId, platform, messageId):

	cur = conn.cursor()

	cur.execute("INSERT INTO posts (\"userId\", \"videoId\", \"platform\", \"postDateTime\", \"discordMessageId\") VALUES (%s, %s, %s, %s, %s)", (userId, postId, platform, datetime.now(tz=None), messageId))

	conn.commit()

	cur.close()

def doesPostExist(videoId, platform):
	cur = conn.cursor()

	cur.execute("SELECT \"userId\", \"postDateTime\", \"discordMessageId\" FROM posts WHERE \"videoId\"=(%s) AND \"platform\"=(%s) ORDER BY \"postId\" DESC LIMIT 1", (videoId, platform))
	result = cur.fetchone()
	print("Heres the result.......:")
	print(result)

	cur.close()
	return result

