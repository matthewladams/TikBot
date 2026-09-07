import os
from datetime import datetime
from flask import Flask, redirect, render_template_string, request, url_for
from dbInteraction import deletePost, fetchPosts, is_db_available

TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>TikBot Management</title>
    <script src="https://cdn.tailwindcss.com"></script>
  </head>
  <body class="bg-slate-950 text-slate-100">
    <div class="min-h-screen">
      <header class="border-b border-slate-800">
        <div class="mx-auto max-w-6xl px-6 py-6">
          <h1 class="text-2xl font-semibold">TikBot Management</h1>
          <p class="mt-1 text-sm text-slate-400">Review saved posts and delete reposts during testing.</p>
        </div>
      </header>

      <main class="mx-auto max-w-6xl px-6 py-8">
        {% if not db_available %}
          <div class="rounded-lg border border-amber-500/40 bg-amber-500/10 p-4 text-amber-100">
            Database connection not available. Configure DB_HOST, DB_USER, DB_PASS, and DB_NAME to manage reposts.
          </div>
        {% else %}
          <div class="overflow-hidden rounded-lg border border-slate-800">
            <div class="bg-slate-900/60 px-4 py-3 text-sm text-slate-300">Showing the most recent {{ posts|length }} posts</div>
            <div class="overflow-x-auto">
              <table class="min-w-full divide-y divide-slate-800 text-sm">
                <thead class="bg-slate-900/80 text-left text-xs uppercase tracking-wider text-slate-400">
                  <tr>
                    <th class="px-4 py-3">Post ID</th>
                    <th class="px-4 py-3">Platform</th>
                    <th class="px-4 py-3">Video ID</th>
                    <th class="px-4 py-3">User</th>
                    <th class="px-4 py-3">Discord Message</th>
                    <th class="px-4 py-3">Posted</th>
                    <th class="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-900/70">
                  {% for post in posts %}
                  <tr class="hover:bg-slate-900/50">
                    <td class="px-4 py-3 font-medium text-slate-200">{{ post.post_id }}</td>
                    <td class="px-4 py-3 text-slate-300">{{ post.platform or '-' }}</td>
                    <td class="px-4 py-3 text-slate-300">{{ post.video_id }}</td>
                    <td class="px-4 py-3 text-slate-300">{{ post.user_id or '-' }}</td>
                    <td class="px-4 py-3 text-slate-300">{{ post.discord_message_id or '-' }}</td>
                    <td class="px-4 py-3 text-slate-300">{{ post.posted_at }}</td>
                    <td class="px-4 py-3 text-right">
                      <form method="post" action="{{ url_for('delete_post', post_id=post.post_id) }}" onsubmit="return confirm('Delete this repost entry?');">
                        <button class="rounded-md bg-rose-600 px-3 py-1 text-xs font-semibold text-white hover:bg-rose-500">Delete</button>
                      </form>
                    </td>
                  </tr>
                  {% endfor %}
                  {% if posts|length == 0 %}
                  <tr>
                    <td class="px-4 py-6 text-center text-slate-400" colspan="7">No posts saved yet.</td>
                  </tr>
                  {% endif %}
                </tbody>
              </table>
            </div>
          </div>
        {% endif %}
      </main>
    </div>
  </body>
</html>
"""


def create_app():
    app = Flask(__name__)

    @app.route("/")
    def index():
        posts = []
        if is_db_available():
            rows = fetchPosts(limit=int(os.getenv("TIKBOT_MANAGEMENT_UI_LIMIT", "50")))
            posts = [
                {
                    "post_id": row[0],
                    "user_id": row[1],
                    "video_id": row[2],
                    "platform": row[3],
                    "posted_at": format_post_time(row[4]),
                    "discord_message_id": row[5],
                }
                for row in rows
            ]
        return render_template_string(TEMPLATE, posts=posts, db_available=is_db_available())

    @app.post("/delete/<int:post_id>")
    def delete_post(post_id):
        if is_db_available():
            deletePost(post_id)
        return redirect(url_for("index"))

    return app


def format_post_time(value):
    if not value:
        return "-"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def run():
    app = create_app()
    port = int(os.getenv("TIKBOT_MANAGEMENT_UI_PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    run()
