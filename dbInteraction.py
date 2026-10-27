import psycopg2
from dotenv import load_dotenv
import os
from datetime import datetime

# Matches posts."videoId" varchar(50); longer IDs would abort the insert.
VIDEO_ID_MAX_LENGTH = 50

conn = None

def _connect():
	host = os.getenv('DB_HOST')
	dbUser = os.getenv('DB_USER')
	dbPass = os.getenv('DB_PASS')
	dbName = os.getenv('DB_NAME')
	return psycopg2.connect(f"host={host} dbname={dbName} user={dbUser} password={dbPass}")

try:
	load_dotenv()
	conn = _connect()
except Exception as e:
    print("Cannot load DB details, repost detection will not be available: " + str(e))

def _get_connection():
	global conn
	if conn is None or conn.closed:
		conn = _connect()
	return conn

def _run(query, params, fetch=False):
	connection = _get_connection()
	try:
		with connection.cursor() as cur:
			cur.execute(query, params)
			result = cur.fetchone() if fetch else None
		connection.commit()
		return result
	except Exception:
		# Without a rollback the shared connection stays in an aborted transaction and every later query fails.
		try:
			connection.rollback()
		except Exception:
			connection.close()
		raise

def _normalize_video_id(videoId):
	return str(videoId)[:VIDEO_ID_MAX_LENGTH]

def savePost(userId, postId, platform, messageId):
	_run("INSERT INTO posts (\"userId\", \"videoId\", \"platform\", \"postDateTime\", \"discordMessageId\") VALUES (%s, %s, %s, %s, %s)", (userId, _normalize_video_id(postId), platform, datetime.now(tz=None), messageId))

def doesPostExist(videoId, platform):
	result = _run("SELECT \"userId\", \"postDateTime\", \"discordMessageId\" FROM posts WHERE \"videoId\"=(%s) AND \"platform\"=(%s) ORDER BY \"postId\" DESC LIMIT 1", (_normalize_video_id(videoId), platform), fetch=True)
	print("Heres the result:")
	print(result)
	return result
