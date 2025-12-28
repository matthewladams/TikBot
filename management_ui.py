from datetime import datetime
import os

from flask import Flask, abort, redirect, render_template, request, url_for

from dbInteraction import get_post_by_id, get_posts, update_post

app = Flask(__name__)
app.secret_key = os.getenv("TIKBOT_MANAGEMENT_SECRET", "local-only")

@app.route("/")
def index():
    return redirect(url_for("posts"))


@app.route("/posts")
def posts():
    limit_raw = request.args.get("limit", "200")
    try:
        limit = max(1, min(int(limit_raw), 1000))
    except ValueError:
        limit = 200
    error = None
    rows = []
    try:
        rows = get_posts(limit=limit)
    except RuntimeError as exc:
        error = str(exc)
    return render_template("posts.html", rows=rows, limit=limit, error=error)


@app.route("/posts/<int:post_id>", methods=["GET", "POST"])
def edit_post(post_id):
    error = None
    if request.method == "POST":
        user_id = request.form.get("userId", "").strip() or None
        video_id = request.form.get("videoId", "").strip() or None
        platform = request.form.get("platform", "").strip() or None
        discord_message_id = request.form.get("discordMessageId", "").strip() or None
        post_datetime_raw = request.form.get("postDateTime", "").strip()

        post_datetime = None
        if post_datetime_raw:
            try:
                post_datetime = datetime.fromisoformat(post_datetime_raw)
            except ValueError:
                error = "Invalid date/time format. Use YYYY-MM-DD HH:MM:SS or ISO format."

        if error is None:
            try:
                update_post(
                    post_id=post_id,
                    user_id=user_id,
                    video_id=video_id,
                    platform=platform,
                    post_datetime=post_datetime,
                    discord_message_id=discord_message_id,
                )
                return redirect(url_for("posts"))
            except RuntimeError as exc:
                error = str(exc)

    try:
        row = get_post_by_id(post_id)
    except RuntimeError as exc:
        row = None
        error = str(exc)

    if row is None:
        if error:
            row = (post_id, "", "", "", "", "")
        else:
            abort(404)

    return render_template("edit_post.html", row=row, error=error)


if __name__ == "__main__":
    host = os.getenv("TIKBOT_MANAGEMENT_HOST", "127.0.0.1")
    port = int(os.getenv("TIKBOT_MANAGEMENT_PORT", "5001"))
    app.run(host=host, port=port)


def run_server(host=None, port=None):
    resolved_host = host or os.getenv("TIKBOT_MANAGEMENT_HOST", "127.0.0.1")
    resolved_port = port or int(os.getenv("TIKBOT_MANAGEMENT_PORT", "5001"))
    app.run(host=resolved_host, port=resolved_port)
