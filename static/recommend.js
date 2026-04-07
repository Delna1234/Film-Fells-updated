// Replace 'YOUR_API_KEY' below with your API key retrieved from https://www.themoviedb.org
var myAPI = 'f29ab3f35cb7c95600c11df45583e6b9'; // global string to be consistent with future usages elsewhere

$(function () {
  $('#movie_list').css('display', 'none');

  $('#autoComplete').blur(function () {
    $('#movie_list').css('display', 'none');
  });

  // Button will be disabled until we type something inside the input field
  const source = document.getElementById('autoComplete');

  const inputHandler = function (e) {
    $('#movie_list').css('display', 'block');

    if (e.target.value == "") {
      $('.movie-button').attr('disabled', true);
    } else {
      $('.movie-button').attr('disabled', false);
    }
  };

  source.addEventListener('input', inputHandler);

  $('.fa-arrow-up').click(function () {
    $('html, body').animate({ scrollTop: 0 }, 'slow');
  });

  $('.app-title').click(function () {
    window.location.href = '/';
  });

  $('.movie-button').on('click', function () {
    var my_api_key = myAPI;
    var title = $('.movie').val();

    $('#movie_list').css('display', 'none');

    if (title == "") {
      $('.results').css('display', 'none');
      $('.fail').css('display', 'block');
      return;
    }

    $('.fail').hide();
    $('.results').show();
    load_details(my_api_key, title, true);
  });

  $(document).on('submit', '#user-review-form', function (event) {
    event.preventDefault();

    const $form = $(this);
    const $button = $form.find('button[type="submit"], button');
    const $feedback = $('#review-feedback');

    $button.prop('disabled', true).text('Submitting...');

    $.ajax({
      type: 'POST',
      url: '/submit_review',
      data: $form.serialize(),
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      success: function (response) {
        const review = response.review;
        appendUserReview(review);
        $form[0].reset();
        $feedback.text('Your review was added successfully.').show();
      },
      error: function () {
        $feedback.text('Unable to save your review right now. Please try again.').show();
      },
      complete: function () {
        $button.prop('disabled', false).text('Submit Review');
      }
    });
  });
});

// will be invoked when clicking on the recommended movie cards
function recommendcard(id) {
  $("#loader").fadeIn();
  var my_api_key = myAPI;
  load_details(my_api_key, id, false);
}

// get the details of the movie from the API (based on the name of the movie)
function load_details(my_api_key, search, isQuerySearch) {
  if (typeof search === 'string' && search.indexOf('local::') === 0) {
    load_local_details(search.substring(7));
    return;
  }

  if (!isQuerySearch) {
    $('.fail').hide();
    $('.results').show();
    get_movie_details(search, my_api_key, '', '');
    return;
  }

  let url = '/api/tmdb/search?q=' + encodeURIComponent(search);

  console.log("Calling TMDB:", url);

  $.ajax({
    type: 'GET',
    url: url,
    success: function (movie) {
      console.log("TMDB response:", movie);

      if (!movie.results || movie.results.length < 1) {
        $('.fail').show();
        $('.results').hide();
      } else {
        $('.fail').hide();
        $('.results').show();
        const first = movie.results[0];
        if (typeof first.id === 'string' && first.id.indexOf('local::') === 0) {
          load_local_details(first.id.substring(7));
        } else {
          get_movie_details(first.id, my_api_key, first.title, first.original_title);
        }
      }
    },
    error: function (xhr, status, err) {
      console.error("TMDB Error:");
      console.error("Status:", status);
      console.error("Error:", err);
      console.error("Response:", xhr.responseText);
      alert("Network error contacting TMDB. Check console.");
    }
  });
}

function load_local_details(title) {
  $.ajax({
    type:'POST',
    data:{ title:title },
    url:"/recommend/local",
    dataType:'html',
    complete: function(){
      $("#loader").delay(500).fadeOut();
    },
    success: function(response) {
      $('.fail').hide();
      $('.results').show();
      $('.results').html(response);
      $('#autoComplete').val('');
      $('.footer').css('position','absolute');
      $(window).scrollTop(0);
    },
    error: function(xhr) {
      console.error("Local fallback error:", xhr.responseText);
      $('.fail').show();
      $('.results').hide();
    }
  });
}


// get all the details of the movie using the movie id.
function get_movie_details(movie_id, my_api_key, movie_title, movie_title_org) {
  console.log("Fetching movie details for ID:", movie_id);

  $.ajax({
    type: 'GET',
    url: '/api/tmdb/movie/' + encodeURIComponent(movie_id),
    success: function (movie_details) {
      console.log("Movie details fetched:", movie_details);
      var resolvedTitle = movie_title || movie_details.title || "";
      var resolvedOriginalTitle = movie_title_org || movie_details.original_title || resolvedTitle;

      // Fetch cast details
      $.ajax({
        type: 'GET',
        url: '/api/tmdb/movie/' + encodeURIComponent(movie_id) + '/credits',
        success: function (credits) {
          console.log("Cast details fetched:", credits);
          var movie_cast = build_movie_cast_from_credits(credits);
          fetch_individual_cast(movie_cast).then(function(ind_cast) {
            show_details(
              movie_details,
              resolvedTitle,
              my_api_key,
              movie_id,
              resolvedOriginalTitle,
              credits,
              ind_cast,
              movie_cast
            );
          });
        },
        error: function (xhr) {
          console.error("Error fetching credits:", xhr && xhr.responseText ? xhr.responseText : xhr);
          show_details(movie_details, resolvedTitle, my_api_key, movie_id, resolvedOriginalTitle, { cast: [] });
        }
      });
    },
    error: function (xhr) {
      console.error("Error fetching movie details:", xhr && xhr.responseText ? xhr.responseText : xhr);
      $("#loader").delay(500).fadeOut();
    }
  });
}


// function show_details(movie_details, movie_title, my_api_key, movie_id, movie_title_org, credits) {

//   console.log("Movie:", movie_details);
//   console.log("Credits:", credits);

//   const topCast = credits.cast.slice(0, 10);

//   const cast_ids = topCast.map(c => c.id);
//   const cast_names = topCast.map(c => c.name);
//   const cast_chars = topCast.map(c => c.character);
//   const cast_profiles = topCast.map(c => 
//     c.profile_path 
//       ? 'https://image.tmdb.org/t/p/w500' + c.profile_path 
//       : '/static/default_profile.jpg'
//   );

// }


// passing all the details to python's flask for displaying and scraping the movie reviews using imdb id
function build_movie_cast_from_credits(credits) {
  var cast_ids = [];
  var cast_names = [];
  var cast_chars = [];
  var cast_profiles = [];
  var castList = (credits && credits.cast) ? credits.cast : [];
  var limit = Math.min(castList.length, 10);

  for (var i = 0; i < limit; i++) {
    var castMember = castList[i];
    cast_ids.push(castMember.id);
    cast_names.push(castMember.name || "Unknown");
    cast_chars.push(castMember.character || "Cast member");
    if (castMember.profile_path) {
      cast_profiles.push("https://image.tmdb.org/t/p/original" + castMember.profile_path);
    } else {
      cast_profiles.push("/static/movie_placeholder.jpeg");
    }
  }

  return {cast_ids:cast_ids, cast_names:cast_names, cast_chars:cast_chars, cast_profiles:cast_profiles};
}

function build_default_individual_cast(movie_cast) {
  var cast_bdays = [];
  var cast_ddays = [];
  var cast_bios = [];
  var cast_places = [];
  var cast_departments = [];
  var cast_aliases = [];
  var cast_imdb_ids = [];

  for (var i = 0; i < movie_cast.cast_ids.length; i++) {
    cast_bdays.push("Not available");
    cast_ddays.push("Not available");
    cast_bios.push("Biography not available.");
    cast_places.push("Not available");
    cast_departments.push("Not available");
    cast_aliases.push("Not available");
    cast_imdb_ids.push("");
  }

  return {
    cast_bdays:cast_bdays,
    cast_ddays:cast_ddays,
    cast_bios:cast_bios,
    cast_places:cast_places,
    cast_departments:cast_departments,
    cast_aliases:cast_aliases,
    cast_imdb_ids:cast_imdb_ids
  };
}

function fetch_individual_cast(movie_cast) {
  var ind_cast = build_default_individual_cast(movie_cast);
  var requests = [];

  for (var i = 0; i < movie_cast.cast_ids.length; i++) {
    (function(index) {
      var personId = movie_cast.cast_ids[index];
      if (!personId && personId !== 0) {
        return;
      }

      var req = $.ajax({
        type: 'GET',
        url: '/api/tmdb/person/' + encodeURIComponent(personId),
        dataType: 'json'
      }).then(function(person) {
        if (!person || person.error) {
          return;
        }

        ind_cast.cast_bdays[index] = person.birthday || "Not available";
        ind_cast.cast_ddays[index] = person.deathday || "Not available";
        ind_cast.cast_bios[index] = person.biography || "Biography not available.";
        ind_cast.cast_places[index] = person.place_of_birth || "Not available";
        ind_cast.cast_departments[index] = person.known_for_department || "Not available";
        if (person.also_known_as && person.also_known_as.length) {
          ind_cast.cast_aliases[index] = person.also_known_as.slice(0, 5).join(", ");
        }
        ind_cast.cast_imdb_ids[index] = person.imdb_id || "";
      }).catch(function() {
        // Keep defaults if fetching person details fails.
      });

      requests.push(req);
    })(i);
  }

  return Promise.all(requests).then(function() {
    return ind_cast;
  });
}

function show_details(movie_details,movie_title,my_api_key,movie_id,movie_title_org,credits,ind_cast,movie_cast){
  var imdb_id = movie_details.imdb_id;
  var poster;
  if(movie_details.poster_path){
    poster = 'https://image.tmdb.org/t/p/original'+movie_details.poster_path;
  }
  else {
    poster = '/static/default.jpg';
  }
  var overview = movie_details.overview;
  var genres = movie_details.genres;
  var rating = movie_details.vote_average;
  var vote_count = movie_details.vote_count;
  var release_date = movie_details.release_date || "";
  var runtime = parseInt(movie_details.runtime || 0);
  var status = movie_details.status || "Unknown";
  var genre_list = []
  for (var genre in genres){
    genre_list.push(genres[genre].name);
  }
  var my_genre = genre_list.join(", ");
  if (!runtime || isNaN(runtime)) {
    runtime = "Not available";
  }
  else if(runtime%60==0){
    runtime = Math.floor(runtime/60)+" hour(s)"
  }
  else {
    runtime = Math.floor(runtime/60)+" hour(s) "+(runtime%60)+" min(s)"
  }

  movie_cast = movie_cast || build_movie_cast_from_credits(credits);
  ind_cast = ind_cast || build_default_individual_cast(movie_cast);

  // calling `get_recommendations` to get the recommended movies for the given movie id from the TMDB API
  var recommendations = get_recommendations(movie_id, my_api_key);
  
  var details = {
      'title':movie_title,
      'movie_id':movie_id,
      'cast_ids':JSON.stringify(movie_cast.cast_ids),
      'cast_names':JSON.stringify(movie_cast.cast_names),
      'cast_chars':JSON.stringify(movie_cast.cast_chars),
      'cast_profiles':JSON.stringify(movie_cast.cast_profiles),
      'cast_bdays':JSON.stringify(ind_cast.cast_bdays),
      'cast_ddays':JSON.stringify(ind_cast.cast_ddays),
      'cast_bios':JSON.stringify(ind_cast.cast_bios),
      'cast_places':JSON.stringify(ind_cast.cast_places),
      'cast_departments':JSON.stringify(ind_cast.cast_departments),
      'cast_aliases':JSON.stringify(ind_cast.cast_aliases),
      'cast_imdb_ids':JSON.stringify(ind_cast.cast_imdb_ids),
      'imdb_id':imdb_id,
      'poster':poster,
      'genres':my_genre,
      'overview':overview,
      'rating':rating,
      'vote_count':(vote_count || 0).toLocaleString(),
      'rel_date':release_date,  
      'release_date':release_date ? new Date(release_date).toDateString().split(' ').slice(1).join(' ') : "Not available",
      'runtime':runtime,
      'status':status,
      'rec_movies':JSON.stringify(recommendations.rec_movies),
      'rec_posters':JSON.stringify(recommendations.rec_posters),
      'rec_movies_org':JSON.stringify(recommendations.rec_movies_org),
      'rec_year':JSON.stringify(recommendations.rec_year),
      'rec_vote':JSON.stringify(recommendations.rec_vote),
      'rec_ids':JSON.stringify(recommendations.rec_ids)
  }

  $.ajax({
    type:'POST',
    data:details,
    url:"/recommend",
    dataType: 'html',
    complete: function(){
      $("#loader").delay(500).fadeOut();
    },
    success: function(response) {
      $('.results').html(response);
      $('#autoComplete').val('');
      $('.footer').css('position','absolute');
      if ($('.movie-content')) {
        $('.movie-content').after('<div class="gototop"><i title="Go to Top" class="fa fa-arrow-up"></i></div>');
      }
      $(window).scrollTop(0);
    }
  });
}

  // getting recommendations
  function get_recommendations(movie_id, my_api_key) {
    var rec_movies = [];
    var rec_posters = [];
    var rec_movies_org = [];
    var rec_year = [];
    var rec_vote = [];
    var rec_ids = [];
    
    $.ajax({
      type: 'GET',
      url: "/api/tmdb/movie/"+encodeURIComponent(movie_id)+"/recommendations",
      async: false,
      success: function(recommend) {
        for(var recs in (recommend.results || [])) {
          rec_movies.push(recommend.results[recs].title);
          rec_movies_org.push(recommend.results[recs].original_title);
          rec_year.push(recommend.results[recs].release_date ? new Date(recommend.results[recs].release_date).getFullYear() : "N/A");
          rec_vote.push(recommend.results[recs].vote_average);
          rec_ids.push(recommend.results[recs].id)
          if(recommend.results[recs].poster_path){
            rec_posters.push("https://image.tmdb.org/t/p/original"+recommend.results[recs].poster_path);
          }
          else {
            rec_posters.push("/static/default.jpg");
          }
        }
      },
      error: function(xhr) {
        console.error("Unable to fetch recommendations:", xhr && xhr.responseText ? xhr.responseText : xhr);
      }
    });
    return {rec_movies:rec_movies,rec_movies_org:rec_movies_org,rec_posters:rec_posters,rec_year:rec_year,rec_vote:rec_vote,rec_ids:rec_ids};
  }

function appendUserReview(review) {
  if (!$('#reviews-table').length) {
    $('#empty-reviews').after(
      '<table class="table table-dark table-hover" id="reviews-table">' +
      '<thead><tr><th>Reviewer</th><th>Comment</th><th>Sentiment</th></tr></thead>' +
      '<tbody id="reviews-table-body"></tbody></table>'
    );
  }

  $('#empty-reviews').hide();
  $('#reviews-table').show();

  $('#reviews-table-body').prepend(
    '<tr>' +
      '<td class="reviewer-index"></td>' +
      '<td>' + escapeHtml(review.review) + '</td>' +
      '<td><span style="color:#00BFFF;">User</span></td>' +
    '</tr>'
  );

  renumberReviews();
}

function escapeHtml(text) {
  return $('<div>').text(text || '').html();
}

function renumberReviews() {
  $('#reviews-table-body .reviewer-index').each(function(index) {
    $(this).text(index + 1);
  });
}
