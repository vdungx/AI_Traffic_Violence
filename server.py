"""Flask web server - Dashboard xem vi phạm giao thông qua trình duyệt."""

import os
import socket
import sys
import threading
import webbrowser

from flask import (
    Flask, request, jsonify, redirect, url_for,
    render_template, send_from_directory,
)

# ── Xác định base directory ──
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

STATIC_DIR = os.path.join(BASE_DIR, "database", "static")

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=STATIC_DIR,
)


# ── Helpers ──

def find_available_port(starting_port: int = 5000) -> int:
    port = starting_port
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("localhost", port)) != 0:
                return port
            port += 1


def _datalog_conn():
    import sqlite3
    db_path = os.path.join(BASE_DIR, "database", "datalog.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _login_conn():
    import sqlite3
    db_path = os.path.join(BASE_DIR, "database", "login.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def speed_limitation(speed: float, max_speed: float) -> str:
    if speed <= 5:
        return "không phát hiện"
    elif speed >= max_speed * 2:
        return "ngoài phạm vi"
    return f"{speed} km/h"


# ── Routes ──

@app.route("/")
def login_page():
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username", "")
    password = data.get("password", "")

    conn = _login_conn()
    user = conn.execute(
        "SELECT * FROM login WHERE user = ? AND password = ?", (username, password)
    ).fetchone()
    conn.close()

    if user:
        new_token = user["token"]
        conn2 = _login_conn()
        conn2.execute("UPDATE login SET token = ? WHERE id = ?", (new_token, user["id"]))
        conn2.commit()
        conn2.close()
        resp = jsonify({"status": "success", "token": new_token})
        resp.set_cookie("token", new_token, httponly=True)
        return resp

    return jsonify({"status": "fail", "message": "Tên đăng nhập hoặc mật khẩu không hợp lệ"}), 401


@app.route("/dashboard")
def dashboard():
    filter_date = request.args.get("date", "")
    conn = _datalog_conn()
    query = "SELECT * FROM datalog"
    params: list = []
    if filter_date:
        query += " WHERE date LIKE ?"
        params.append(f"%{filter_date}%")
    data = conn.execute(query, params).fetchall()
    conn.close()
    return render_template("dashboard.html", data=data)


@app.route("/photo/<int:id>")
def photo(id: int):
    conn = _datalog_conn()
    row = conn.execute("SELECT * FROM datalog WHERE id = ?", (id,)).fetchone()
    conn.close()

    if not row:
        return redirect("/dashboard")

    inspeed = float(row["speed"])
    inmaxspeed = float(row["max_speed"])
    speed = speed_limitation(inspeed, inmaxspeed)
    location = row["location"]

    return render_template(
        "photo.html",
        data=row,
        image_path=row["open_photo"],
        plat_license_path=row["plat_license"],
        location=location,
        speed=speed,
    )


@app.route("/delete/<int:id>", methods=["DELETE"])
def delete(id: int):
    conn = _datalog_conn()
    row = conn.execute(
        "SELECT open_photo, plat_license FROM datalog WHERE id = ?", (id,)
    ).fetchone()

    if row:
        conn.execute("DELETE FROM datalog WHERE id = ?", (id,))
        conn.commit()
        conn.close()

        # Xóa file ảnh
        for col in ("open_photo", "plat_license"):
            fp = os.path.join(STATIC_DIR, row[col]) if row[col] else ""
            if fp and os.path.isfile(fp):
                try:
                    os.remove(fp)
                except OSError:
                    pass
        return "", 204

    conn.close()
    return "", 404


@app.route("/logout", methods=["POST"])
def logout():
    resp = jsonify({"status": "logged out"})
    resp.set_cookie("token", "", expires=0)
    return resp


@app.route("/change-user", methods=["GET", "POST"])
def change_user():
    message = ""
    if request.method == "POST":
        last_u = request.form["last_username"]
        last_p = request.form["last_password"]
        new_u = request.form["new_username"]
        new_p = request.form["new_password"]

        conn = _login_conn()
        user = conn.execute(
            "SELECT * FROM login WHERE user = ? AND password = ?", (last_u, last_p)
        ).fetchone()

        if user:
            conn.execute(
                "UPDATE login SET user = ?, password = ? WHERE id = ?",
                (new_u, new_p, user["id"]),
            )
            conn.commit()
            message = "Tên đăng nhập và mật khẩu đã được cập nhật thành công!"
        else:
            message = "Tên đăng nhập hoặc mật khẩu không hợp lệ."
        conn.close()

    return render_template("change_user.html", message=message)


# ── Static file serving ──

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(STATIC_DIR, filename)


# ── Main ──

def open_browser(port: int):
    webbrowser.open(f"http://127.0.0.1:{port}", new=2)


if __name__ == "__main__":
    port = find_available_port(5000)
    show_port = port if port <= 5000 else port - 1
    # Chỉ mở trình duyệt lần đầu (tránh reloader chạy 2 lần)
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        threading.Timer(1, open_browser, args=(show_port,)).start()
    app.run(debug=True, port=port)
