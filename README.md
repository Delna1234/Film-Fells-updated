# The-Movie-Cinema

![Python](https://img.shields.io/badge/Python-3.8-blueviolet)
![Framework](https://img.shields.io/badge/Framework-Flask-red)
![Frontend](https://img.shields.io/badge/Frontend-HTML/CSS/JS-green)
![API](https://img.shields.io/badge/API-TMDB-fcba03)

This application provides all the details of the requested movie such as overview, genre, release date, rating, runtime, top cast, reviews, recommended movies, etc.

The details of the movies(title, genre, runtime, rating, poster, etc) are fetched using an API by TMDB, https://www.themoviedb.org/documentation/api, and using the IMDB id of the movie in the API, I did web scraping to get the reviews given by the user in the IMDB site using `beautifulsoup4` and performed sentiment analysis on those reviews.

## Link to the application

Check out the live demo: https://tmc.kishanlal.dev/

If you can't find the movie you're searching for through auto-suggestions while typing, there's no need to worry. Simply type the name of the movie and press "enter". Even if you make some typos, it should still work fine.

## 'Invalid Request' Error

If you're getting invalid request error in your application, kindly go through this issue - https://github.com/kishan0725/The-Movie-Cinema/issues/2

## How to get the API key?

Create an account in https://www.themoviedb.org/, click on the `API` link from the left hand sidebar in your account settings and fill all the details to apply for API key. If you are asked for the website URL, just give "NA" if you don't have one. You will see the API key in your `API` sidebar once your request is approved.

## How to run the project?

1. Clone this repository in your local system.
2. Install all the libraries mentioned in the [requirements.txt](https://github.com/kishan0725/The-Movie-Cinema/blob/master/requirements.txt) file with the command `pip install -r requirements.txt`.
3. Replace YOUR_API_KEY at line no. 2 of `static/recommend.js` file.
4. Open your terminal/command prompt from your project directory and run the `main.py` file by executing the command `python main.py`.
5. Go to your browser and type `http://127.0.0.1:5000/` in the address bar.
6. Hurray! That's it.

## IMDb review scraping on restricted networks

If IMDb reviews are blocked on your network, the app can now use a proxy for the IMDb scraping request.

1. Set the environment variable `IMDB_PROXY_URL` before starting the app.
2. Use a proxy URL such as `http://username:password@host:port` or `http://host:port`.
3. Start the Flask app normally with `python main.py`.

Example in PowerShell:

```powershell
$env:IMDB_PROXY_URL="http://host:port"
python main.py
```

Without a working proxy, the app will continue to show sample IMDb-style reviews as a fallback.

### Sources of the datasets 

1. [IMDB 5000 Movie Dataset](https://www.kaggle.com/carolzhangdc/imdb-5000-movie-dataset)
2. [The Movies Dataset](https://www.kaggle.com/rounakbanik/the-movies-dataset)
3. [List of movies in 2018](https://en.wikipedia.org/wiki/List_of_American_films_of_2018)
4. [List of movies in 2019](https://en.wikipedia.org/wiki/List_of_American_films_of_2019)
5. [List of movies in 2020](https://en.wikipedia.org/wiki/List_of_American_films_of_2020)

Please do ⭐ the repository, if it helped you in anyway.

# Project_Cinema





11-feb
##### Incase nework error occur
1. go to the cntrl panel
2. select 'Network and Sharing Center'
3. in connections->properties
4. disable ipv6 and in properties of ipv4 use custom dns-preffered-'1.1.1.1' and alternaive as '1.0.0.1'
5. if IMDb is still blocked, start the app with `IMDB_PROXY_URL` set to a reachable proxy
