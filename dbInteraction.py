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
except Exception as e:
    print("Cannot load DB details, repost detection will not be available: " + str(e))

def _get_cursor():
    if 'conn' not in globals() or conn is None:
        raise RuntimeError("Database connection not initialized")
    return conn.cursor()

def savePost(userId, postId, platform, messageId):

	cur = _get_cursor()

	cur.execute("INSERT INTO posts (\"userId\", \"videoId\", \"platform\", \"postDateTime\", \"discordMessageId\") VALUES (%s, %s, %s, %s, %s)", (userId, postId, platform, datetime.now(tz=None), messageId))

	conn.commit()

	cur.close()

def doesPostExist(videoId, platform):
	cur = _get_cursor()
	cur.execute("SELECT \"userId\", \"postDateTime\", \"discordMessageId\" FROM posts WHERE \"videoId\"=(%s) AND \"platform\"=(%s) ORDER BY \"postId\" DESC LIMIT 1", (videoId, platform))
	result = cur.fetchone()
	print("Heres the result:")
	print(result)

	cur.close()
	return result

def get_posts(limit=200):
    cur = _get_cursor()
    cur.execute(
        "SELECT \"postId\", \"userId\", \"videoId\", \"platform\", \"postDateTime\", \"discordMessageId\" "
        "FROM posts ORDER BY \"postId\" DESC LIMIT %s",
        (limit,)
    )
    rows = cur.fetchall()
    cur.close()
    return rows

def get_post_by_id(post_id):
    cur = _get_cursor()
    cur.execute(
        "SELECT \"postId\", \"userId\", \"videoId\", \"platform\", \"postDateTime\", \"discordMessageId\" "
        "FROM posts WHERE \"postId\" = %s",
        (post_id,)
    )
    row = cur.fetchone()
    cur.close()
    return row

def update_post(post_id, user_id, video_id, platform, post_datetime, discord_message_id):
    cur = _get_cursor()
    cur.execute(
        "UPDATE posts SET \"userId\" = %s, \"videoId\" = %s, \"platform\" = %s, \"postDateTime\" = %s, "
        "\"discordMessageId\" = %s WHERE \"postId\" = %s",
        (user_id, video_id, platform, post_datetime, discord_message_id, post_id)
    )
    conn.commit()
    cur.close()
