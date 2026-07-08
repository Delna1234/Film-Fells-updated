import html
import json
import os
import re
from difflib import get_close_matches
from datetime import date, datetime
from functools import wraps
from urllib.request import ProxyHandler, Request, build_opener, urlopen

import bs4 as bs
import joblib
import numpy as np
import pandas as pd
import requests
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import pickle

TMDB_KEY = os.getenv("TMDB_KEY", "f29ab3f35cb7c95600c11df45583e6b9").strip()
IMDB_PROXY_URL = os.getenv("IMDB_PROXY_URL", "").strip()
IMDB_COOKIE = os.getenv("IMDB_COOKIE", "").strip()
TMDB_TIMEOUT = 8

# Load NLP model
vectorizer = joblib.load("transform.pkl")
clf = joblib.load("nlp_model.pkl")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret-in-production")

APP_LOGIN_USERNAME = os.getenv("APP_LOGIN_USERNAME", "admin")
APP_LOGIN_PASSWORD = os.getenv("APP_LOGIN_PASSWORD", "admin123")

REVIEW_FILE = "user_reviews.json"

LOCAL_DATA = pd.read_csv("main_data.csv").fillna("")
local_count = CountVectorizer(stop_words="english")
local_vectors = local_count.fit_transform(LOCAL_DATA["comb"])

# Create review file if not exists
if not os.path.exists(REVIEW_FILE):
    with open(REVIEW_FILE, "w") as f:
        json.dump({}, f)


# Convert list of string
def convert_to_list(my_list):
    my_list = my_list.split('","')
    my_list[0] = my_list[0].replace('["', '')
    my_list[-1] = my_list[-1].replace('"]', '')
    return my_list


# Convert list numbers
def convert_to_list_num(my_list):
    my_list = my_list.split(',')
    my_list[0] = my_list[0].replace("[", "")
    my_list[-1] = my_list[-1].replace("]", "")
    return my_list


# Movie suggestions
def get_suggestions():
    return list(LOCAL_DATA['movie_title'].str.capitalize())


def parse_json_list(raw_value):
    if not raw_value:
        return []
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        return []


def safe_string(value, default=""):
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def normalize_title(value):
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


LOCAL_TITLE_TO_INDEX = {
    normalize_title(row["movie_title"]): index
    for index, row in LOCAL_DATA.iterrows()
    if normalize_title(row["movie_title"])
}


def find_best_local_title(query):
    normalized_query = normalize_title(query)
    if not normalized_query:
        return None

    suggestions = get_suggestions()
    normalized_map = {normalize_title(title): title for title in suggestions}
    normalized_titles = list(normalized_map.keys())

    # Prefer partial and prefix matches first for speed and relevance.
    for n_title in normalized_titles:
        if normalized_query == n_title or normalized_query in n_title or n_title.startswith(normalized_query):
            return normalized_map[n_title]

    close = get_close_matches(normalized_query, normalized_titles, n=1, cutoff=0.72)
    if close:
        return normalized_map[close[0]]
    return None


def get_local_movie_row(title):
    normalized_title = normalize_title(title)
    if not normalized_title:
        return None, None

    index = LOCAL_TITLE_TO_INDEX.get(normalized_title)
    if index is None:
        return None, None
    return index, LOCAL_DATA.iloc[index]


def build_local_overview(row):
    actors = ", ".join(
        actor for actor in [row.get("actor_1_name", ""), row.get("actor_2_name", ""), row.get("actor_3_name", "")]
        if actor
    )
    genres = str(row.get("genres", "")).replace(" ", ", ")
    director = row.get("director_name", "Unknown director")
    title = str(row.get("movie_title", "")).title()
    return (
        f"{title} is available from the local movie dataset. "
        f"It is directed by {director} and features {actors or 'cast information not available'}. "
        f"Genres: {genres or 'Not available'}."
    )


def get_local_recommendations(index, limit=12):
    similarity_scores = cosine_similarity(local_vectors[index], local_vectors).flatten()
    ranked_indexes = np.argsort(similarity_scores)[::-1]

    recommendations = []
    for other_index in ranked_indexes:
        if other_index == index:
            continue
        row = LOCAL_DATA.iloc[other_index]
        title = str(row["movie_title"]).title()
        recommendations.append({
            "title": title,
            "original_title": title,
            "vote_average": "N/A",
            "year": "N/A",
            "id": f"local::{row['movie_title']}",
            "poster": "/static/movie_placeholder.jpeg"
        })
        if len(recommendations) >= limit:
            break
    return recommendations


def build_local_movie_context(title):
    index, row = get_local_movie_row(title)
    if row is None:
        matched_title = find_best_local_title(title)
        if matched_title:
            index, row = get_local_movie_row(matched_title)

    if row is None:
        return None

    movie_title = str(row["movie_title"]).title()
    genres_string = str(row.get("genres", "")).replace(" ", ", ")
    overview = build_local_overview(row)

    movie_cards = {}
    for rec_index, rec in enumerate(get_local_recommendations(index)):
        movie_cards[f"{rec['poster']}?local={rec_index}"] = [
            rec["title"],
            rec["original_title"],
            rec["vote_average"],
            rec["year"],
            rec["id"]
        ]

    casts = []
    for cast_index, actor_name in enumerate(
        [row.get("actor_1_name", ""), row.get("actor_2_name", ""), row.get("actor_3_name", "")]
    ):
        if actor_name:
            casts.append({
                "id": f"local-cast-{cast_index}",
                "name": actor_name,
                "character": "Cast member",
                "profile": "/static/movie_placeholder.jpeg",
                "birthday": "Not available",
                "deathday": "Not available",
                "place": "Not available",
                "bio": f"{actor_name} appears in the local dataset entry for {movie_title}.",
                "known_for_department": "Not available",
                "also_known_as": "Not available",
                "imdb_id": "",
                "modal_id": make_modal_id(actor_name, f"local-{cast_index}", cast_index)
            })

    review_cards = build_sample_imdb_reviews(movie_title, overview, genres_string or "Drama")
    for review in get_user_reviews(movie_title):
        review_cards.append({
            "review": review["review"],
            "status": "User",
            "source": "You",
            "user": review.get("user", "Anonymous"),
            "date": review.get("date", "")
        })

    return {
        "title": movie_title,
        "imdb_id": "",
        "poster": "/static/movie_placeholder.jpeg",
        "overview": overview,
        "vote_average": "N/A",
        "vote_count": "Local dataset",
        "release_date": "Not available",
        "runtime": "Not available",
        "status": "Available locally",
        "genres": genres_string or "Not available",
        "movie_cards": movie_cards,
        "reviews": review_cards,
        "casts": casts,
        "imdb_review_error": "TMDB is unavailable, so this page is showing data from the local movie dataset."
    }


def make_modal_id(name, cast_id=None, index=0):
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "cast").lower()).strip("-")
    suffix = cast_id if cast_id not in (None, "", "null") else index
    return f"cast-{slug or 'member'}-{suffix}"


def build_cast_members(form_data):
    cast_ids = parse_json_list(form_data.get("cast_ids"))
    cast_names = parse_json_list(form_data.get("cast_names"))
    cast_chars = parse_json_list(form_data.get("cast_chars"))
    cast_profiles = parse_json_list(form_data.get("cast_profiles"))
    cast_bdays = parse_json_list(form_data.get("cast_bdays"))
    cast_ddays = parse_json_list(form_data.get("cast_ddays"))
    cast_bios = parse_json_list(form_data.get("cast_bios"))
    cast_places = parse_json_list(form_data.get("cast_places"))
    cast_departments = parse_json_list(form_data.get("cast_departments"))
    cast_aliases = parse_json_list(form_data.get("cast_aliases"))
    cast_imdb_ids = parse_json_list(form_data.get("cast_imdb_ids"))

    cast_members = []

    for index, name in enumerate(cast_names):
        cast_id = cast_ids[index] if index < len(cast_ids) else ""
        cast_members.append({
            "id": cast_id,
            "name": name,
            "character": cast_chars[index] if index < len(cast_chars) else "Not available",
            "profile": cast_profiles[index] if index < len(cast_profiles) and cast_profiles[index] else "/static/movie_placeholder.jpeg",
            "birthday": cast_bdays[index] if index < len(cast_bdays) and cast_bdays[index] else "Not available",
            "deathday": cast_ddays[index] if index < len(cast_ddays) and cast_ddays[index] else "Not available",
            "place": cast_places[index] if index < len(cast_places) and cast_places[index] else "Not available",
            "bio": cast_bios[index] if index < len(cast_bios) and cast_bios[index] else "Biography not available.",
            "known_for_department": cast_departments[index] if index < len(cast_departments) and cast_departments[index] else "Not available",
            "also_known_as": cast_aliases[index] if index < len(cast_aliases) and cast_aliases[index] else "Not available",
            "imdb_id": cast_imdb_ids[index] if index < len(cast_imdb_ids) and cast_imdb_ids[index] else "",
            "modal_id": make_modal_id(name, cast_id, index)
        })

    return cast_members


def get_user_reviews(movie_title):
    with open(REVIEW_FILE) as f:
        user_reviews = json.load(f)

    return user_reviews.get(movie_title, [])


def login_required(route_func):
    @wraps(route_func)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return route_func(*args, **kwargs)

    return wrapper


def build_sample_imdb_reviews(title, overview, genres):
    review_texts = [
        (
            f"{title} delivers an engaging experience with strong moments throughout. "
            f"The storytelling feels polished, the performances work well, and the {genres.lower()} elements keep the movie entertaining from start to finish."
        ),
        (
            f"{title} has an interesting setup, but it feels uneven in a few places. "
            f"Some scenes stand out nicely, though the pacing and emotional payoff could have been stronger overall."
        ),
        (
            f"For viewers who enjoy {genres.lower()}, {title} offers memorable visuals and a clear mood. "
            f"The central idea from the story summary, {overview[:120].strip()}..., makes it easy to stay invested."
        )
    ]

    sample_reviews = []

    for review_text in review_texts:
        movie_review_list = np.array([review_text])
        movie_vector = vectorizer.transform(movie_review_list)
        pred = clf.predict(movie_vector)

        sample_reviews.append({
            "review": review_text,
            "status": 'Positive' if pred[0] == 1 else 'Negative',
            "source": "Sample IMDb",
            "user": "Sample reviewer",
            "date": ""
        })

    return sample_reviews


def fetch_imdb_reviews(imdb_id):
    urls = [
        f"https://www.imdb.com/title/{imdb_id}/reviews?ref_=tt_ov_rt",
        f"https://www.imdb.com/title/{imdb_id}/reviews/_ajax",
        f"https://www.imdb.com/title/{imdb_id}/reviews/_ajax?ref_=undefined"
    ]
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"https://www.imdb.com/title/{imdb_id}/"
    }
    if IMDB_COOKIE:
        headers["Cookie"] = IMDB_COOKIE

    proxies = None

    if IMDB_PROXY_URL:
        proxies = {
            "http": IMDB_PROXY_URL,
            "https": IMDB_PROXY_URL
        }

    selectors = [
        'div[data-testid="review-content"]',
        'div[data-testid^="review-card"] div.ipc-html-content-inner-div',
        'div.ipc-html-content-inner-div',
        ".review-container .content .text",
        ".lister-item-content .content .text",
        ".text.show-more__control"
    ]

    reviews = []
    seen = set()
    all_page_text = []
    waf_challenge_seen = False

    def add_review(review_text):
        normalized = re.sub(r"\s+", " ", review_text).strip()
        if not normalized or len(normalized) < 40 or normalized in seen:
            return
        seen.add(normalized)
        reviews.append(normalized)

    for url in urls:
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=30,
                proxies=proxies,
                allow_redirects=True
            )
        except requests.RequestException:
            continue

        if (
            response.status_code == 202 and
            str(response.headers.get("x-amzn-waf-action", "")).lower() == "challenge"
        ):
            waf_challenge_seen = True
            continue

        if response.status_code >= 400:
            continue

        page_text = response.text or ""
        all_page_text.append(page_text)
        soup = bs.BeautifulSoup(page_text, "lxml")

        for selector in selectors:
            for review_div in soup.select(selector):
                review_text = " ".join(review_div.stripped_strings)
                add_review(review_text)

        if len(reviews) >= 10:
            return reviews[:10]

    if not reviews:
        for url in urls:
            try:
                req = Request(url, headers=headers)
                if proxies:
                    opener = build_opener(ProxyHandler(proxies))
                    sauce = opener.open(req, timeout=30).read()
                else:
                    sauce = urlopen(req, timeout=30).read()
                fallback_text = sauce.decode("utf-8", errors="ignore")
                all_page_text.append(fallback_text)
            except Exception:
                continue

    if not reviews:
        regex_patterns = [
            r'"reviewText":"(.*?)"',
            r'"body":"(.*?)"'
        ]

        for page_text in all_page_text:
            for pattern in regex_patterns:
                for match in re.findall(pattern, page_text):
                    cleaned = html.unescape(match)
                    cleaned = cleaned.encode("utf-8").decode("unicode_escape")
                    cleaned = cleaned.replace('\\"', '"').replace("\\n", " ")
                    add_review(cleaned)

                if reviews:
                    break
            if reviews:
                break

    if not reviews and waf_challenge_seen:
        raise RuntimeError("IMDB_WAF_CHALLENGE")

    return reviews[:10]


def fetch_tmdb_reviews(movie_id):
    if not movie_id or str(movie_id) in {"0", "None", "null", ""}:
        return []

    url = f"https://api.themoviedb.org/3/movie/{movie_id}/reviews?api_key={TMDB_KEY}&language=en-US&page=1"
    response = requests.get(url, timeout=TMDB_TIMEOUT)
    response.raise_for_status()

    payload = response.json() or {}
    results = payload.get("results", [])
    reviews = []

    for item in results:
        content = (item.get("content") or "").strip()
        if len(content) < 40:
            continue
        reviews.append({
            "user": (item.get("author") or "TMDB user").strip(),
            "review": re.sub(r"\s+", " ", content),
            "date": (item.get("created_at") or "")[:10],
            "source": "TMDB"
        })
        if len(reviews) >= 10:
            break

    return reviews


# =========================
# LOGIN CONFIGURATION
# =========================

users = {}

# =========================
# ROOT PAGE
# =========================

@app.route("/")
def root():
    if session.get("logged_in"):
        return redirect(url_for("home"))
    return redirect(url_for("login"))


# =========================
# LOGIN
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():

    error = ""

    if session.get("logged_in"):
        return redirect(url_for("home"))

    if request.method == "POST":

        username = request.form["username"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if email in users:

            user = users[email]

            if user["username"] == username and user["password"] == password:

                session["logged_in"] = True
                session["username"] = username
                session["email"] = email

                return redirect(url_for("home"))

        error = "Invalid Username, Email or Password."

    return render_template("login.html", error=error)

# =========================
# SIGNUP
# =========================

@app.route("/signup", methods=["GET", "POST"])
def signup():

    error = ""
    success = ""

    if request.method == "POST":

        username = request.form["username"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            error = "Passwords do not match."

        elif email in users:
            error = "Email already exists."

        else:
            users[email] = {
                "username": username,
                "password": password
            }

            success = "Account created successfully."

            return redirect(url_for("login"))

    return render_template(
        "signup.html",
        error=error,
        success=success
    )

# =========================
# LOGOUT
# =========================

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/home")
@login_required
def home():

    suggestions = get_suggestions()

    return render_template(
        "home.html",
        suggestions=suggestions
    )


# POPULATE MATCHES
@app.route("/populate-matches", methods=["POST"])
@login_required
def populate_matches():

    res = json.loads(request.get_data("data"))
    movies_list = res['movies_list']

    movie_cards = {

        "https://image.tmdb.org/t/p/original" + movies_list[i]['poster_path']
        if movies_list[i]['poster_path']
        else "/static/movie_placeholder.jpeg":

        [
            movies_list[i]['title'],
            movies_list[i]['original_title'],
            movies_list[i]['vote_average'],
            datetime.strptime(
                movies_list[i]['release_date'],
                '%Y-%m-%d'
            ).year if movies_list[i]['release_date'] else "N/A",
            movies_list[i]['id']
        ]

        for i in range(len(movies_list))
    }

    return render_template(
        'recommend.html',
        movie_cards=movie_cards
    )


@app.route("/recommend/local", methods=["POST"])
@login_required
def recommend_local():
    title = request.form.get("title", "").strip()
    context = build_local_movie_context(title)
    if not context:
        return jsonify({"ok": False, "error": "Movie not found in local dataset"}), 404
    return render_template("recommend.html", **context)


# MOVIE RECOMMENDATION PAGE
@app.route("/recommend", methods=["POST"])
@login_required
def recommend():

    title = request.form['title']
    imdb_id = request.form['imdb_id']
    poster = request.form['poster']
    genres = request.form['genres']
    overview = request.form['overview']
    vote_average = request.form['rating']
    vote_count = request.form['vote_count']
    release_date = request.form['release_date']
    runtime = request.form['runtime']
    status = request.form['status']
    movie_id = request.form.get('movie_id', 0)

    cast_members = build_cast_members(request.form)

    rec_movies = request.form['rec_movies']
    rec_posters = request.form['rec_posters']
    rec_movies_org = request.form['rec_movies_org']
    rec_year = request.form['rec_year']
    rec_vote = request.form['rec_vote']
    rec_ids = request.form['rec_ids']

    suggestions = get_suggestions()

    rec_movies_org = parse_json_list(rec_movies_org)
    rec_movies = parse_json_list(rec_movies)
    rec_posters = parse_json_list(rec_posters)

    rec_vote = parse_json_list(rec_vote)
    rec_year = parse_json_list(rec_year)
    rec_ids = parse_json_list(rec_ids)

    movie_cards = {

        safe_string(rec_posters[i], "/static/movie_placeholder.jpeg"):

        [
            safe_string(rec_movies[i], "Untitled"),
            safe_string(rec_movies_org[i], safe_string(rec_movies[i], "Untitled")),
            safe_string(rec_vote[i], "N/A"),
            safe_string(rec_year[i], "N/A"),
            safe_string(rec_ids[i], "")
        ]

        for i in range(
            min(
                len(rec_movies),
                len(rec_posters),
                len(rec_movies_org),
                len(rec_year),
                len(rec_vote),
                len(rec_ids)
            )
        )
        if safe_string(rec_movies[i]) and safe_string(rec_ids[i])
    }

    if not movie_cards:
        local_context = build_local_movie_context(title)
        if local_context:
            movie_cards = local_context.get("movie_cards", {})

    review_cards = []
    imdb_review_error = ""

    # SCRAPE IMDB REVIEWS
    if imdb_id != "":
        try:
            for review_text in fetch_imdb_reviews(imdb_id):
                movie_review_list = np.array([review_text])
                movie_vector = vectorizer.transform(movie_review_list)
                pred = clf.predict(movie_vector)

                review_cards.append({
                    "review": review_text,
                    "status": 'Positive' if pred[0] == 1 else 'Negative',
                    "source": "IMDb",
                    "user": "IMDb user",
                    "date": ""
                })
            if not any(review["source"] == "IMDb" for review in review_cards):
                imdb_review_error = "IMDb reviews are temporarily unavailable for this movie."
        except Exception as exc:
            print("IMDb review fetch failed:", exc)
            if str(exc) == "IMDB_WAF_CHALLENGE":
                imdb_review_error = (
                    "IMDb blocked this server request with a WAF challenge. "
                    "Set IMDB_PROXY_URL (and optionally IMDB_COOKIE) to fetch live IMDb reviews."
                )
            elif IMDB_PROXY_URL:
                imdb_review_error = "IMDb reviews are temporarily unavailable for this movie even with the configured proxy."
            else:
                imdb_review_error = "IMDb reviews are temporarily unavailable for this movie. Configure IMDB_PROXY_URL if your network blocks IMDb."

    # TMDB fallback reviews if IMDb is unavailable
    if not any(review["source"] == "IMDb" for review in review_cards):
        try:
            tmdb_reviews = fetch_tmdb_reviews(movie_id)
            for item in tmdb_reviews:
                movie_review_list = np.array([item["review"]])
                movie_vector = vectorizer.transform(movie_review_list)
                pred = clf.predict(movie_vector)

                review_cards.append({
                    "review": item["review"],
                    "status": 'Positive' if pred[0] == 1 else 'Negative',
                    "source": item["source"],
                    "user": item["user"],
                    "date": item["date"]
                })

            if tmdb_reviews:
                if imdb_review_error:
                    imdb_review_error += " Showing TMDB user reviews instead."
                else:
                    imdb_review_error = "Showing TMDB user reviews for this movie."
        except Exception as exc:
            print("TMDB review fetch failed:", exc)

    if not any(review["source"] in {"IMDb", "TMDB"} for review in review_cards):
        review_cards.extend(build_sample_imdb_reviews(title, overview, genres))
        if imdb_review_error:
            imdb_review_error += " Showing sample reviews instead."
        else:
            imdb_review_error = "Showing sample IMDb-style reviews for this movie."

    for review in get_user_reviews(title):
        review_cards.append({
            "review": review["review"],
            "status": "User",
            "source": "You",
            "user": review.get("user", "Anonymous"),
            "date": review.get("date", "")
        })

    return render_template(

        'recommend.html',

        title=title,
        imdb_id=imdb_id,
        poster=poster,
        overview=overview,
        vote_average=vote_average,
        vote_count=vote_count,
        release_date=release_date,
        runtime=runtime,
        status=status,
        genres=genres,

        movie_cards=movie_cards,
        reviews=review_cards,
        casts=cast_members,
        imdb_review_error=imdb_review_error
    )


# USER REVIEW SUBMISSION
@app.route("/submit_review", methods=["POST"])
@login_required
def submit_review():

    movie = request.form['movie']
    username = request.form['username']
    review = request.form['review']

    with open(REVIEW_FILE) as f:
        data = json.load(f)

    if movie not in data:
        data[movie] = []

    data[movie].append({

        "user": username,
        "review": review,
        "date": str(date.today())
    })

    with open(REVIEW_FILE, "w") as f:
        json.dump(data, f, indent=4)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({
            "ok": True,
            "review": {
                "user": username,
                "review": review,
                "date": str(date.today()),
                "status": "User"
            }
        })

    return redirect("/home")


# TMDB SEARCH API
@app.route("/api/tmdb/search")
@login_required
def tmdb_search():

    q = (request.args.get("q") or "").strip()
    if not q:
        return {"results": []}

    base_url = "https://api.themoviedb.org/3/search/movie"
    queries = [q]
    cleaned_query = re.sub(r"\s*\(\d{4}\)\s*$", "", q).strip()
    if cleaned_query and cleaned_query.lower() != q.lower():
        queries.append(cleaned_query)

    try:
        last_payload = {"results": []}

        for query in queries:
            r = requests.get(
                base_url,
                params={
                    "api_key": TMDB_KEY,
                    "query": query
                },
                timeout=TMDB_TIMEOUT
            )

            if r.status_code != 200:
                print("TMDB search HTTP error:", r.status_code, "query:", query, "body:", r.text[:250])
                continue

            payload = r.json() or {"results": []}
            last_payload = payload
            if payload.get("results"):
                return payload

        local_match = find_best_local_title(q)
        if local_match:
            return {
                "results": [{
                    "id": f"local::{local_match.lower()}",
                    "title": local_match,
                    "original_title": local_match,
                    "poster_path": None,
                    "vote_average": 0,
                    "release_date": ""
                }],
                "fallback_query": local_match,
                "source": "local"
            }

        return last_payload

    except Exception as e:

        print("TMDB connection error:", e)

        local_match = find_best_local_title(q)
        if local_match:
            return {
                "results": [{
                    "id": f"local::{local_match.lower()}",
                    "title": local_match,
                    "original_title": local_match,
                    "poster_path": None,
                    "vote_average": 0,
                    "release_date": ""
                }],
                "fallback_query": local_match,
                "source": "local"
            }

        return {"results": []}


@app.route("/api/tmdb/movie/<int:movie_id>")
@login_required
def tmdb_movie_details(movie_id):
    try:
        r = requests.get(
            f"https://api.themoviedb.org/3/movie/{movie_id}",
            params={"api_key": TMDB_KEY},
            timeout=TMDB_TIMEOUT
        )
        if r.status_code != 200:
            print("TMDB movie details HTTP error:", r.status_code, "movie_id:", movie_id, "body:", r.text[:250])
            return jsonify({"error": "Unable to fetch movie details", "results": []}), 502
        return jsonify(r.json() or {})
    except Exception as e:
        print("TMDB movie details connection error:", e)
        return jsonify({"error": "Unable to fetch movie details", "results": []}), 502


@app.route("/api/tmdb/movie/<int:movie_id>/credits")
@login_required
def tmdb_movie_credits(movie_id):
    try:
        r = requests.get(
            f"https://api.themoviedb.org/3/movie/{movie_id}/credits",
            params={"api_key": TMDB_KEY},
            timeout=TMDB_TIMEOUT
        )
        if r.status_code != 200:
            print("TMDB movie credits HTTP error:", r.status_code, "movie_id:", movie_id, "body:", r.text[:250])
            return jsonify({"cast": [], "crew": [], "error": "Unable to fetch movie credits"}), 502
        return jsonify(r.json() or {"cast": [], "crew": []})
    except Exception as e:
        print("TMDB movie credits connection error:", e)
        return jsonify({"cast": [], "crew": [], "error": "Unable to fetch movie credits"}), 502


@app.route("/api/tmdb/person/<int:person_id>")
@login_required
def tmdb_person_details(person_id):
    try:
        r = requests.get(
            f"https://api.themoviedb.org/3/person/{person_id}",
            params={"api_key": TMDB_KEY},
            timeout=TMDB_TIMEOUT
        )
        if r.status_code != 200:
            print("TMDB person details HTTP error:", r.status_code, "person_id:", person_id, "body:", r.text[:250])
            return jsonify({"error": "Unable to fetch person details"}), 502
        return jsonify(r.json() or {})
    except Exception as e:
        print("TMDB person details connection error:", e)
        return jsonify({"error": "Unable to fetch person details"}), 502


@app.route("/api/tmdb/movie/<int:movie_id>/recommendations")
@login_required
def tmdb_movie_recommendations(movie_id):
    try:
        r = requests.get(
            f"https://api.themoviedb.org/3/movie/{movie_id}/recommendations",
            params={"api_key": TMDB_KEY},
            timeout=TMDB_TIMEOUT
        )
        if r.status_code != 200:
            print("TMDB recommendations HTTP error:", r.status_code, "movie_id:", movie_id, "body:", r.text[:250])
            return jsonify({"results": [], "error": "Unable to fetch recommendations"}), 502
        return jsonify(r.json() or {"results": []})
    except Exception as e:
        print("TMDB recommendations connection error:", e)
        return jsonify({"results": [], "error": "Unable to fetch recommendations"}), 502


# RUN APP
if __name__ == '__main__':
    app.run(debug=True)
