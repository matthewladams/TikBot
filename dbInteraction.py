import psycopg2
from dotenv import load_dotenv 
import os
from datetime import datetime

load_dotenv()
host = os.getenv('DB_HOST')
dbUser = os.getenv('DB_USER')
dbPass = os.getenv('DB_PASS')
dbName = os.getenv('DB_NAME')

conn = psycopg2.connect(f"host={host} dbname={dbName} user={dbUser} password={dbPass}")

def savePost(userId, postId, platform):

	cur = conn.cursor()

	cur.execute("INSERT INTO posts (\"userId\", \"videoId\", \"platform\", \"postDateTime\") VALUES (%s, %s, %s, %s)", (userId, postId, platform, datetime.now(tz=None)))

	conn.commit()

	cur.close()

def doesPostExist(videoId, platform):
	cur = conn.cursor()

	cur.execute("SELECT \"userId\", \"postDateTime\" FROM posts WHERE \"videoId\"=(%s) AND \"platform\"=(%s) ORDER BY \"postId\" DESC LIMIT 1", (videoId, platform))
	result = cur.fetchone()
	print("Heres the result.......:")
	print(result)

	cur.close()
	return result

