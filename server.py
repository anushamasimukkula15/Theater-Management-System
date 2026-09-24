from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps


app = Flask(__name__, template_folder="templates")

app.secret_key = "change-this-secret-key"

DB = "theater.db"


# ============================================================
# DATABASE CONNECTION
# ============================================================

def db():

    conn = sqlite3.connect(DB)

    conn.row_factory = sqlite3.Row
 
    return conn


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():

    conn = db()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            genre TEXT NOT NULL,
            duration INTEGER NOT NULL,
            language TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS theaters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT NOT NULL,
            seats INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS shows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_id INTEGER NOT NULL,
            theater_id INTEGER NOT NULL,
            show_date TEXT NOT NULL,
            show_time TEXT NOT NULL,
            ticket_price REAL DEFAULT 0,
            FOREIGN KEY(movie_id) REFERENCES movies(id),
            FOREIGN KEY(theater_id) REFERENCES theaters(id)
        );

        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            show_id INTEGER NOT NULL,
            customer_name TEXT NOT NULL,
            seats_booked INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(show_id) REFERENCES shows(id)
        );
    """)


    # ========================================================
    # ADD TICKET PRICE TO OLD SHOWS TABLE
    # ========================================================

    columns = conn.execute(
        "PRAGMA table_info(shows)"
    ).fetchall()

    column_names = [
        column["name"]
        for column in columns
    ]

    if "ticket_price" not in column_names:

        conn.execute(
            """
            ALTER TABLE shows
            ADD COLUMN ticket_price REAL DEFAULT 0
            """
        )


    # ========================================================
    # FIX OLD BOOKINGS COLUMN
    # ========================================================
    #
    # Older version used:
    #     seats
    #
    # Current database uses:
    #     seats_booked
    #
    # Existing data is preserved.
    # ========================================================

    booking_columns = conn.execute(
        "PRAGMA table_info(bookings)"
    ).fetchall()

    booking_column_names = [
        column["name"]
        for column in booking_columns
    ]

    if (
        "seats_booked" not in booking_column_names
        and
        "seats" in booking_column_names
    ):

        conn.execute(
            """
            ALTER TABLE bookings
            RENAME COLUMN seats TO seats_booked
            """
        )


    conn.commit()

    conn.close()


# ============================================================
# LOGIN REQUIRED
# ============================================================

def login_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if "user_id" not in session:

            flash(
                "Please login first.",
                "warning"
            )

            return redirect(
                url_for("login")
            )

        return view(*args, **kwargs)

    return wrapped


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return render_template(
        "home.html"
    )


# ============================================================
# REGISTER
# ============================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )


        if not name or not email or not password:

            flash(
                "All fields are required.",
                "danger"
            )

            return redirect(
                url_for("register")
            )


        conn = db()

        try:

            conn.execute(
                """
                INSERT INTO users(
                    name,
                    email,
                    password
                )
                VALUES (?, ?, ?)
                """,
                (
                    name,
                    email,
                    generate_password_hash(
                        password
                    )
                )
            )

            conn.commit()

            flash(
                "Registration successful. Please login.",
                "success"
            )

            return redirect(
                url_for("login")
            )


        except sqlite3.IntegrityError:

            flash(
                "Email already registered.",
                "danger"
            )


        finally:

            conn.close()


    return render_template(
        "register.html"
    )


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )


        if not email or not password:

            flash(
                "Email and password are required.",
                "danger"
            )

            return render_template(
                "login.html"
            )


        conn = db()

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        conn.close()


        if user and check_password_hash(
            user["password"],
            password
        ):

            session.clear()

            session["user_id"] = user["id"]

            session["user_name"] = user["name"]

            session["email"] = user["email"]


            flash(
                "Login successful.",
                "success"
            )

            return redirect(
                url_for("dashboard")
            )


        flash(
            "Invalid email or password.",
            "danger"
        )


    return render_template(
        "login.html"
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have logged out.",
        "info"
    )

    return redirect(
        url_for("home")
    )


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
@login_required
def dashboard():

    conn = db()


    counts = {

        "movies": conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM movies
            """
        ).fetchone()["c"],


        "theaters": conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM theaters
            """
        ).fetchone()["c"],


        "shows": conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM shows
            """
        ).fetchone()["c"],


        "bookings": conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM bookings
            WHERE user_id = ?
            """,
            (
                session["user_id"],
            )
        ).fetchone()["c"]

    }


    conn.close()


    return render_template(
        "dashboard.html",
        counts=counts
    )


# ============================================================
# MOVIES
# ============================================================

@app.route("/movies")
@login_required
def movies():

    conn = db()

    rows = conn.execute(
        """
        SELECT *
        FROM movies
        ORDER BY id ASC
        """
    ).fetchall()

    conn.close()


    return render_template(
        "movies.html",
        movies=rows
    )


# ============================================================
# ADD MOVIE
# ============================================================

@app.route(
    "/movies/add",
    methods=["GET", "POST"]
)
@login_required
def add_movie():

    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()

        genre = request.form.get(
            "genre",
            ""
        ).strip()

        duration = request.form.get(
            "duration",
            ""
        ).strip()

        language = request.form.get(
            "language",
            ""
        ).strip()


        if (
            not title
            or not genre
            or not duration
            or not language
        ):

            flash(
                "All movie fields are required.",
                "danger"
            )

            return render_template(
                "movie_form.html",
                movie=None
            )


        try:

            duration = int(duration)

            if duration <= 0:
                raise ValueError


        except ValueError:

            flash(
                "Duration must be a valid number greater than 0.",
                "danger"
            )

            return render_template(
                "movie_form.html",
                movie=None
            )


        conn = db()


        conn.execute(
            """
            INSERT INTO movies(
                name,
                genre,
                duration,
                language
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                title,
                genre,
                duration,
                language
            )
        )


        conn.commit()

        conn.close()


        flash(
            "Movie added successfully.",
            "success"
        )


        return redirect(
            url_for("movies")
        )


    return render_template(
        "movie_form.html",
        movie=None
    )


# ============================================================
# EDIT MOVIE
# ============================================================

@app.route(
    "/movies/edit/<int:id>",
    methods=["GET", "POST"]
)
@login_required
def edit_movie(id):

    conn = db()


    movie = conn.execute(
        """
        SELECT *
        FROM movies
        WHERE id = ?
        """,
        (id,)
    ).fetchone()


    if not movie:

        conn.close()

        flash(
            "Movie not found.",
            "danger"
        )

        return redirect(
            url_for("movies")
        )


    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()

        genre = request.form.get(
            "genre",
            ""
        ).strip()

        duration = request.form.get(
            "duration",
            ""
        ).strip()

        language = request.form.get(
            "language",
            ""
        ).strip()


        if (
            not title
            or not genre
            or not duration
            or not language
        ):

            conn.close()

            flash(
                "All movie fields are required.",
                "danger"
            )

            return render_template(
                "movie_form.html",
                movie=movie
            )


        try:

            duration = int(duration)

            if duration <= 0:
                raise ValueError


        except ValueError:

            conn.close()

            flash(
                "Duration must be a valid number greater than 0.",
                "danger"
            )

            return render_template(
                "movie_form.html",
                movie=movie
            )


        conn.execute(
            """
            UPDATE movies
            SET
                name = ?,
                genre = ?,
                duration = ?,
                language = ?
            WHERE id = ?
            """,
            (
                title,
                genre,
                duration,
                language,
                id
            )
        )


        conn.commit()

        conn.close()


        flash(
            "Movie updated successfully.",
            "success"
        )


        return redirect(
            url_for("movies")
        )


    conn.close()


    return render_template(
        "movie_form.html",
        movie=movie
    )


# ============================================================
# DELETE MOVIE
# ============================================================

@app.route(
    "/movies/delete/<int:id>",
    methods=["POST"]
)
@login_required
def delete_movie(id):

    conn = db()


    linked = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM shows
        WHERE movie_id = ?
        """,
        (id,)
    ).fetchone()["total"]


    if linked > 0:

        conn.close()

        flash(
            "This movie cannot be deleted because it is used by a show.",
            "danger"
        )

        return redirect(
            url_for("movies")
        )


    conn.execute(
        """
        DELETE FROM movies
        WHERE id = ?
        """,
        (id,)
    )


    conn.commit()

    conn.close()


    flash(
        "Movie deleted.",
        "info"
    )


    return redirect(
        url_for("movies")
    )


# ============================================================
# THEATERS
# ============================================================

@app.route("/theaters")
@login_required
def theaters():

    conn = db()


    rows = conn.execute(
        """
        SELECT *
        FROM theaters
        ORDER BY id ASC
        """
    ).fetchall()


    conn.close()


    return render_template(
        "theaters.html",
        theaters=rows
    )


# ============================================================
# ADD THEATER
# ============================================================

@app.route(
    "/theaters/add",
    methods=["GET", "POST"]
)
@login_required
def add_theater():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        location = request.form.get(
            "location",
            ""
        ).strip()

        seats = request.form.get(
            "seats",
            ""
        ).strip()


        if (
            not name
            or not location
            or not seats
        ):

            flash(
                "All theater fields are required.",
                "danger"
            )

            return render_template(
                "theater_form.html",
                theater=None
            )


        try:

            seats = int(seats)

            if seats <= 0:
                raise ValueError


        except ValueError:

            flash(
                "Seats must be a valid number greater than 0.",
                "danger"
            )

            return render_template(
                "theater_form.html",
                theater=None
            )


        conn = db()


        conn.execute(
            """
            INSERT INTO theaters(
                name,
                location,
                seats
            )
            VALUES (?, ?, ?)
            """,
            (
                name,
                location,
                seats
            )
        )


        conn.commit()

        conn.close()


        flash(
            "Theater added.",
            "success"
        )


        return redirect(
            url_for("theaters")
        )


    return render_template(
        "theater_form.html",
        theater=None
    )


# ============================================================
# EDIT THEATER
# ============================================================

@app.route(
    "/theaters/edit/<int:id>",
    methods=["GET", "POST"]
)
@login_required
def edit_theater(id):

    conn = db()


    theater = conn.execute(
        """
        SELECT *
        FROM theaters
        WHERE id = ?
        """,
        (id,)
    ).fetchone()


    if not theater:

        conn.close()

        flash(
            "Theater not found.",
            "danger"
        )

        return redirect(
            url_for("theaters")
        )


    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        location = request.form.get(
            "location",
            ""
        ).strip()

        seats = request.form.get(
            "seats",
            ""
        ).strip()


        if (
            not name
            or not location
            or not seats
        ):

            conn.close()

            flash(
                "All theater fields are required.",
                "danger"
            )

            return render_template(
                "theater_form.html",
                theater=theater
            )


        try:

            seats = int(seats)

            if seats <= 0:
                raise ValueError


        except ValueError:

            conn.close()

            flash(
                "Seats must be a valid number greater than 0.",
                "danger"
            )

            return render_template(
                "theater_form.html",
                theater=theater
            )


        conn.execute(
            """
            UPDATE theaters
            SET
                name = ?,
                location = ?,
                seats = ?
            WHERE id = ?
            """,
            (
                name,
                location,
                seats,
                id
            )
        )


        conn.commit()

        conn.close()


        flash(
            "Theater updated.",
            "success"
        )


        return redirect(
            url_for("theaters")
        )


    conn.close()


    return render_template(
        "theater_form.html",
        theater=theater
    )


# ============================================================
# DELETE THEATER
# ============================================================

@app.route(
    "/theaters/delete/<int:id>",
    methods=["POST"]
)
@login_required
def delete_theater(id):

    conn = db()


    linked = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM shows
        WHERE theater_id = ?
        """,
        (id,)
    ).fetchone()["total"]


    if linked > 0:

        conn.close()

        flash(
            "This theater cannot be deleted because it is used by a show.",
            "danger"
        )

        return redirect(
            url_for("theaters")
        )


    conn.execute(
        """
        DELETE FROM theaters
        WHERE id = ?
        """,
        (id,)
    )


    conn.commit()

    conn.close()


    flash(
        "Theater deleted.",
        "info"
    )


    return redirect(
        url_for("theaters")
    )


# ============================================================
# SHOWS
# ============================================================

@app.route("/shows")
@login_required
def shows():

    conn = db()


    rows = conn.execute(
        """
        SELECT

            shows.id,

            shows.movie_id,

            shows.theater_id,

            shows.show_date,

            shows.show_time,

            shows.ticket_price,


            movies.name AS movie_name,

            movies.name AS movie_title,


            theaters.name AS theater_name,

            theaters.location AS theater_location,

            theaters.location AS location,

            theaters.seats AS total_seats,


            COALESCE(
                (
                    SELECT SUM(
                        b.seats_booked
                    )
                    FROM bookings b
                    WHERE b.show_id = shows.id
                ),
                0
            ) AS seats_booked,


            COALESCE(
                (
                    SELECT SUM(
                        b2.seats_booked
                    )
                    FROM bookings b2
                    WHERE b2.show_id = shows.id
                ),
                0
            ) AS booked_seats,


            (
                theaters.seats

                -

                COALESCE(
                    (
                        SELECT SUM(
                            b3.seats_booked
                        )
                        FROM bookings b3
                        WHERE b3.show_id = shows.id
                    ),
                    0
                )
            ) AS available_seats


        FROM shows


        JOIN movies

        ON shows.movie_id = movies.id


        JOIN theaters

        ON shows.theater_id = theaters.id


        ORDER BY shows.id ASC

        """
    ).fetchall()


    conn.close()


    return render_template(
        "shows.html",
        shows=rows
    )


# ============================================================
# ADD SHOW
# ============================================================

@app.route(
    "/shows/add",
    methods=["GET", "POST"]
)
@login_required
def add_show():

    conn = db()


    movies = conn.execute(
        """
        SELECT *
        FROM movies
        ORDER BY id ASC
        """
    ).fetchall()


    theaters = conn.execute(
        """
        SELECT *
        FROM theaters
        ORDER BY id ASC
        """
    ).fetchall()


    if request.method == "POST":

        movie_id = request.form.get(
            "movie_id"
        )

        theater_id = request.form.get(
            "theater_id"
        )

        show_date = request.form.get(
            "show_date"
        )

        show_time = request.form.get(
            "show_time"
        )

        ticket_price_value = request.form.get(
            "ticket_price",
            "0"
        ).strip()


        if (
            not movie_id
            or not theater_id
            or not show_date
            or not show_time
        ):

            conn.close()

            flash(
                "Please fill all required show fields.",
                "danger"
            )

            return render_template(
                "show_form.html",
                movies=movies,
                theaters=theaters,
                show=None,
                edit_mode=False
            )


        try:

            ticket_price = float(
                ticket_price_value or 0
            )

            if ticket_price < 0:
                raise ValueError


        except ValueError:

            conn.close()

            flash(
                "Ticket price must be a valid number.",
                "danger"
            )

            return render_template(
                "show_form.html",
                movies=movies,
                theaters=theaters,
                show=None,
                edit_mode=False
            )


        conn.execute(
            """
            INSERT INTO shows(
                movie_id,
                theater_id,
                show_date,
                show_time,
                ticket_price
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                movie_id,
                theater_id,
                show_date,
                show_time,
                ticket_price
            )
        )


        conn.commit()

        conn.close()


        flash(
            "Show added.",
            "success"
        )


        return redirect(
            url_for("shows")
        )


    conn.close()


    return render_template(
        "show_form.html",
        movies=movies,
        theaters=theaters,
        show=None,
        edit_mode=False
    )
# ============================================================
# EDIT SHOW
# ============================================================

@app.route(
    "/shows/edit/<int:id>",
    methods=["GET", "POST"]
)
@login_required
def edit_show(id):

    conn = db()


    show = conn.execute(
        """
        SELECT *
        FROM shows
        WHERE id = ?
        """,
        (id,)
    ).fetchone()


    if not show:

        conn.close()

        flash(
            "Show not found.",
            "danger"
        )

        return redirect(
            url_for("shows")
        )


    movies = conn.execute(
        """
        SELECT *
        FROM movies
        ORDER BY id ASC
        """
    ).fetchall()


    theaters = conn.execute(
        """
        SELECT *
        FROM theaters
        ORDER BY id ASC
        """
    ).fetchall()


    if request.method == "POST":

        movie_id = request.form.get(
            "movie_id"
        )

        theater_id = request.form.get(
            "theater_id"
        )

        show_date = request.form.get(
            "show_date"
        )

        show_time = request.form.get(
            "show_time"
        )

        ticket_price_value = request.form.get(
            "ticket_price",
            "0"
        ).strip()


        if (
            not movie_id
            or not theater_id
            or not show_date
            or not show_time
        ):

            conn.close()

            flash(
                "Please fill all required show fields.",
                "danger"
            )

            return render_template(
                "show_form.html",
                show=show,
                movies=movies,
                theaters=theaters,
                edit_mode=True
            )


        try:

            ticket_price = float(
                ticket_price_value or 0
            )

            if ticket_price < 0:
                raise ValueError


        except ValueError:

            conn.close()

            flash(
                "Ticket price must be a valid number.",
                "danger"
            )

            return render_template(
                "show_form.html",
                show=show,
                movies=movies,
                theaters=theaters,
                edit_mode=True
            )


        conn.execute(
            """
            UPDATE shows

            SET
                movie_id = ?,
                theater_id = ?,
                show_date = ?,
                show_time = ?,
                ticket_price = ?

            WHERE id = ?
            """,
            (
                movie_id,
                theater_id,
                show_date,
                show_time,
                ticket_price,
                id
            )
        )


        conn.commit()

        conn.close()


        flash(
            "Show updated successfully.",
            "success"
        )


        return redirect(
            url_for("shows")
        )


    conn.close()


    return render_template(
        "show_form.html",
        show=show,
        movies=movies,
        theaters=theaters,
        edit_mode=True
    )


# ============================================================
# DELETE SHOW
# ============================================================

@app.route(
    "/shows/delete/<int:id>",
    methods=["POST"]
)
@login_required
def delete_show(id):

    conn = db()


    booking_count = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM bookings
        WHERE show_id = ?
        """,
        (id,)
    ).fetchone()["total"]


    if booking_count > 0:

        conn.close()

        flash(
            "This show cannot be deleted because it has bookings.",
            "danger"
        )

        return redirect(
            url_for("shows")
        )


    conn.execute(
        """
        DELETE FROM shows
        WHERE id = ?
        """,
        (id,)
    )


    conn.commit()

    conn.close()


    flash(
        "Show deleted.",
        "info"
    )


    return redirect(
        url_for("shows")
    )


# ============================================================
# BOOKINGS
# ============================================================

@app.route(
    "/bookings",
    methods=["GET", "POST"]
)
@login_required
def bookings():

    conn = db()


    # ========================================================
    # CREATE BOOKING
    # ========================================================

    if request.method == "POST":

        show_id = request.form.get(
            "show_id"
        )

        customer_name = request.form.get(
            "customer_name",
            ""
        ).strip()

        seats_value = request.form.get(
            "seats",
            ""
        ).strip()


        if (
            not show_id
            or not customer_name
            or not seats_value
        ):

            flash(
                "All booking fields are required.",
                "danger"
            )


        else:

            try:

                seats = int(
                    seats_value
                )


                if seats < 1:

                    flash(
                        "Seats must be at least 1.",
                        "danger"
                    )


                else:

                    show = conn.execute(
                        """
                        SELECT
                            theaters.seats
                            AS total_seats

                        FROM shows

                        JOIN theaters

                        ON shows.theater_id =
                           theaters.id

                        WHERE shows.id = ?
                        """,
                        (show_id,)
                    ).fetchone()


                    if not show:

                        flash(
                            "Selected show was not found.",
                            "danger"
                        )


                    else:

                        booked = conn.execute(
                            """
                            SELECT
                                COALESCE(
                                    SUM(seats_booked),
                                    0
                                )
                                AS booked_seats

                            FROM bookings

                            WHERE show_id = ?
                            """,
                            (show_id,)
                        ).fetchone()[
                            "booked_seats"
                        ]


                        available = (
                            show["total_seats"]
                            - booked
                        )


                        if seats > available:

                            flash(
                                f"Only {available} seats are available.",
                                "danger"
                            )


                        else:

                            conn.execute(
                                """
                                INSERT INTO bookings(
                                    user_id,
                                    show_id,
                                    customer_name,
                                    seats_booked
                                )

                                VALUES (
                                    ?, ?, ?, ?
                                )
                                """,
                                (
                                    session["user_id"],
                                    show_id,
                                    customer_name,
                                    seats
                                )
                            )


                            conn.commit()


                            flash(
                                "Booking created successfully.",
                                "success"
                            )


            except ValueError:

                flash(
                    "Seats must be a valid number.",
                    "danger"
                )


    # ========================================================
    # AVAILABLE SHOWS
    # ========================================================

    available_shows = conn.execute(
        """
        SELECT

            shows.id,

            movies.name AS title,

            theaters.name AS theater_name,

            theaters.location AS theater_location,

            theaters.seats AS total_seats,

            shows.show_date,

            shows.show_time,

            shows.ticket_price,


            COALESCE(
                (
                    SELECT
                        SUM(
                            b.seats_booked
                        )

                    FROM bookings b

                    WHERE b.show_id =
                          shows.id
                ),
                0
            ) AS seats_booked,


            (
                theaters.seats

                -

                COALESCE(
                    (
                        SELECT
                            SUM(
                                b2.seats_booked
                            )

                        FROM bookings b2

                        WHERE b2.show_id =
                              shows.id
                    ),
                    0
                )
            ) AS available_seats


        FROM shows


        LEFT JOIN movies

        ON shows.movie_id =
           movies.id


        LEFT JOIN theaters

        ON shows.theater_id =
           theaters.id


        ORDER BY shows.id ASC

        """
    ).fetchall()


    # ========================================================
    # USER BOOKINGS
    # ========================================================

    rows = conn.execute(
        """
        SELECT

            bookings.id,

            bookings.user_id,

            bookings.show_id,

            bookings.customer_name,

            bookings.seats_booked,

            bookings.seats_booked
            AS seats,


            movies.name AS title,


            theaters.name AS theater_name,

            theaters.location
            AS theater_location,

            theaters.seats
            AS total_seats,


            shows.show_date,

            shows.show_time,

            shows.ticket_price,


            COALESCE(
                (
                    SELECT
                        SUM(
                            b3.seats_booked
                        )

                    FROM bookings b3

                    WHERE b3.show_id =
                          bookings.show_id
                ),
                0
            ) AS show_seats_booked,


            COALESCE(
                (
                    SELECT
                        SUM(
                            b4.seats_booked
                        )

                    FROM bookings b4

                    WHERE b4.show_id =
                          bookings.show_id
                ),
                0
            ) AS seats_booked_total,


            (
                theaters.seats

                -

                COALESCE(
                    (
                        SELECT
                            SUM(
                                b5.seats_booked
                            )

                        FROM bookings b5

                        WHERE b5.show_id =
                              bookings.show_id
                    ),
                    0
                )
            ) AS available_seats


        FROM bookings


        LEFT JOIN shows

        ON bookings.show_id =
           shows.id


        LEFT JOIN movies

        ON shows.movie_id =
           movies.id


        LEFT JOIN theaters

        ON shows.theater_id =
           theaters.id


        WHERE bookings.user_id = ?


        ORDER BY bookings.id ASC

        """,
        (
            session["user_id"],
        )
    ).fetchall()


    conn.close()


    return render_template(
        "bookings.html",
        shows=available_shows,
        bookings=rows
    )


# ============================================================
# EDIT BOOKING
# ============================================================

@app.route(
    "/bookings/edit/<int:id>",
    methods=["POST"]
)
@login_required
def edit_booking(id):

    customer_name = request.form.get(
        "customer_name",
        ""
    ).strip()


    seats_value = request.form.get(
        "seats",
        ""
    ).strip()


    if (
        not customer_name
        or not seats_value
    ):

        flash(
            "Customer name and seats are required.",
            "danger"
        )

        return redirect(
            url_for("bookings")
        )


    try:

        seats = int(
            seats_value
        )


    except ValueError:

        flash(
            "Seats must be a valid number.",
            "danger"
        )

        return redirect(
            url_for("bookings")
        )


    if seats < 1:

        flash(
            "Seats must be at least 1.",
            "danger"
        )

        return redirect(
            url_for("bookings")
        )


    conn = db()


    booking = conn.execute(
        """
        SELECT

            bookings.show_id,

            bookings.seats_booked
            AS old_seats,

            theaters.seats
            AS total_seats


        FROM bookings


        LEFT JOIN shows

        ON bookings.show_id =
           shows.id


        LEFT JOIN theaters

        ON shows.theater_id =
           theaters.id


        WHERE bookings.id = ?

        AND bookings.user_id = ?

        """,
        (
            id,
            session["user_id"]
        )
    ).fetchone()


    if not booking:

        conn.close()

        flash(
            "Booking not found.",
            "danger"
        )

        return redirect(
            url_for("bookings")
        )


    other_booked = conn.execute(
        """
        SELECT

            COALESCE(
                SUM(seats_booked),
                0
            )
            AS total

        FROM bookings

        WHERE show_id = ?

        AND id != ?

        """,
        (
            booking["show_id"],
            id
        )
    ).fetchone()["total"]


    available_for_this_booking = (
        booking["total_seats"]
        - other_booked
    )


    if seats > available_for_this_booking:

        conn.close()

        flash(
            f"Only {available_for_this_booking} seats are available for this booking.",
            "danger"
        )

        return redirect(
            url_for("bookings")
        )


    conn.execute(
        """
        UPDATE bookings

        SET
            customer_name = ?,
            seats_booked = ?

        WHERE id = ?

        AND user_id = ?

        """,
        (
            customer_name,
            seats,
            id,
            session["user_id"]
        )
    )


    conn.commit()

    conn.close()


    flash(
        "Booking updated successfully.",
        "success"
    )


    return redirect(
        url_for("bookings")
    )


# ============================================================
# DELETE BOOKING
# ============================================================

@app.route(
    "/bookings/delete/<int:id>",
    methods=["POST"]
)
@login_required
def delete_booking(id):

    conn = db()


    conn.execute(
        """
        DELETE FROM bookings

        WHERE id = ?

        AND user_id = ?

        """,
        (
            id,
            session["user_id"]
        )
    )


    conn.commit()

    conn.close()


    flash(
        "Booking cancelled.",
        "info"
    )


    return redirect(
        url_for("bookings")
    )


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    init_db()

    app.run(
        debug=True
    )