import psycopg2
from dotenv import load_dotenv
import os
from datetime import datetime

conn = None

try:
    load_dotenv()
    host = os.getenv('DB_HOST')
    dbUser = os.getenv('DB_USER')
    dbPass = os.getenv('DB_PASS')
    dbName = os.getenv('DB_NAME')
    conn = psycopg2.connect(f"host={host} dbname={dbName} user={dbUser} password={dbPass}")
except Exception as e:
    print("Cannot load DB details, repost detection will not be available: " + str(e))


def is_db_available():
    return conn is not None

def savePost(userId, postId, platform, messageId):
    if not conn:
        return

    cur = conn.cursor()

    cur.execute(
        "INSERT INTO posts (\"userId\", \"videoId\", \"platform\", \"postDateTime\", \"discordMessageId\") VALUES (%s, %s, %s, %s, %s)",
        (userId, postId, platform, datetime.now(tz=None), messageId),
    )

    conn.commit()

    cur.close()

def doesPostExist(videoId, platform):
    if not conn:
        return None

    cur = conn.cursor()
    cur.execute(
        "SELECT \"userId\", \"postDateTime\", \"discordMessageId\" FROM posts WHERE \"videoId\"=(%s) AND \"platform\"=(%s) ORDER BY \"postId\" DESC LIMIT 1",
        (videoId, platform),
    )
    result = cur.fetchone()
    print("Heres the result:")
    print(result)

    cur.close()
    return result


def fetchPosts(limit=50):
    if not conn:
        return []
    cur = conn.cursor()
    cur.execute(
        "SELECT \"postId\", \"userId\", \"videoId\", \"platform\", \"postDateTime\", \"discordMessageId\" FROM posts ORDER BY \"postId\" DESC LIMIT %s",
        (limit,),
    )
    rows = cur.fetchall()
    cur.close()
    return rows


def deletePost(post_id):
    if not conn:
        return False
    cur = conn.cursor()
    cur.execute("DELETE FROM posts WHERE \"postId\"=(%s)", (post_id,))
    deleted = cur.rowcount > 0
    conn.commit()
    cur.close()
    return deleted
