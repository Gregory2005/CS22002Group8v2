from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity, get_jwt
from flask_jwt_extended import verify_jwt_in_request
from flask_jwt_extended.exceptions import NoAuthorizationError
import requests

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///movie_site.db'
app.config['JWT_SECRET_KEY'] = 'Test1Geniuelly'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)

#tables working
class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    poster_url = db.Column(db.String(300), nullable=True)
    tmdb_id = db.Column(db.Integer, unique=True, nullable=False)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey('movie.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)

#Routing stuff working 
@app.route('/') 
def index():
    return render_template('loginFlask.html')

@app.route('/signup')
def signup():
    return render_template('signupFlask.html')

@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/settings')
def settings():
    return render_template('settings.html')

@app.route('/users')
def users():
    return render_template('users.html')

@app.route('/moviepage')
def moviepage():
    return render_template('movies.html')

#login and register working
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"error": "Username and password are required"}), 400
    user = User.query.filter_by(username=data['username']).first()
    if user and bcrypt.check_password_hash(user.password, data['password']):
        access_token = create_access_token(identity={'id': user.id, 'is_admin': user.is_admin})
        return jsonify({
            "message": "Login successful",
            "token": access_token,
            "is_admin": user.is_admin
        }), 200
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"error": "Username and password are required"}), 400

    hashed_password = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    user = User(username=data['username'], password=hashed_password)
    try:
        db.session.add(user)
        db.session.commit()
        return jsonify({"message": "register successful,"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

#home page stuff working
@app.route('/movies/search', methods=['GET'])
def search_movies():
    query = request.args.get('query', '').lower()
    if not query:
        return jsonify([]), 200

    movies = Movie.query.filter(
        Movie.title.ilike(f'%{query}%') | 
        Movie.description.ilike(f'%{query}%')
    ).all()

    movies_list = [
        {
            "id": movie.id,
            "title": movie.title,
            "description": movie.description,
            "poster_url": movie.poster_url,
            "tmdb_id": movie.tmdb_id,
        } for movie in movies
    ]
    
    return jsonify(movies_list), 200

@app.route('/movies', methods=['GET'])
def get_movies():
    movies = Movie.query.all()
    movies_list = [
        {
            "id": movie.id,
            "title": movie.title,
            "description": movie.description,
            "poster_url": movie.poster_url,
            "tmdb_id": movie.tmdb_id,
        } for movie in movies
    ]
    return jsonify(movies_list)

TMDB_API_KEY = "5aaa417b9434ffc999ba2c0215becaa6"

@app.route('/populate', methods=['POST'])
def populate_movies():
    url = "https://api.themoviedb.org/3/movie/popular"
    params = {
        "api_key": TMDB_API_KEY,
        "language": "en-US",
        "page": 1
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
    except requests.RequestException as e:
        return jsonify({"error": f"Failed to fetch data from TMDb: {str(e)}"}), 500

    try:
        data = response.json()
        added = 0
        for item in data.get("results", []):
            tmdb_id = item["id"]
            title = item["title"]
            description = item["overview"]
            poster_path = item.get("poster_path")
            poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None

            if Movie.query.filter_by(tmdb_id=tmdb_id).first():
                continue

            movie = Movie(
                title=title,
                description=description,
                poster_url=poster_url,
                tmdb_id=tmdb_id
            )
            db.session.add(movie)
            added += 1

        db.session.commit()
        return jsonify({"message": f"{added} movies added from TMDb"}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to save movies to the database: {str(e)}"}), 500

#not working
@app.route('/password-update', methods=['PUT'])
@jwt_required()
def password_update():
    try:
        user_data = get_jwt_identity()
        user_id = user_data["id"]
        user = User.query.get(user_id)

        if not user:
            return jsonify({"error": "User not found."}), 404

        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')

        if not current_password or not new_password:
            return jsonify({"error": "Both current and new passwords are required."}), 400

        if not bcrypt.check_password_hash(user.password, current_password):
            return jsonify({"error": "Current password is incorrect."}), 401

        user.password = bcrypt.generate_password_hash(new_password).decode('utf-8')
        db.session.commit()
        return jsonify({"message": "Password updated successfully!"}), 200

    except Exception as e:
        print("Exception during password update:", str(e))
        return jsonify({"error": f"Internal error: {str(e)}"}), 500

@app.route('/api/users', methods=['GET'])
@jwt_required()
def get_users():
    current_user = get_jwt_identity()
    if not current_user["is_admin"]:
        return jsonify({"error": "admins only"}), 403

    users = User.query.all()
    users_data = [
        {
            "id": user.id,
            "username": user.username,
        }
        for user in users
    ]
    return jsonify(users_data), 200


@app.route('/users/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_user(id):
    claims = get_jwt()
    user_data = get_jwt_identity()
    user_id = user_data["id"]
    if not claims.get("is_admin"):
        return jsonify({"error": "Access denied – admin only"}), 403
    if int(user_id) == id:
        return jsonify({"error": "Admin can't delete own account"}), 400
    user = User.query.get(id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    try:
        db.session.delete(user)
        db.session.commit()
        return jsonify({"message": "User deleted successfully."}), 200
    except:
        return jsonify({"error": "User deletion failed."}), 500


@app.route('/movies', methods=['POST'])
@jwt_required()
def add_movie():
    claims = get_jwt()
    if not claims.get("is_admin"):
        return jsonify({"error": "Access denied – admin only"}), 403

    data = request.get_json()

    if not data.get('title') or not data.get('description') or not data.get('tmdb_id'):
        return jsonify({"error": "Missing required fields"}), 400

    if Movie.query.filter_by(tmdb_id=data['tmdb_id']).first():
        return jsonify({"error": "Movie already exists"}), 400

    try:
        new_movie = Movie(
            title=data['title'],
            description=data['description'],
            poster_url=data.get('poster_url'),
            tmdb_id=data['tmdb_id']
        )
        db.session.add(new_movie)
        db.session.commit()
        return jsonify({"message": "Movie added"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/movies/<int:id>', methods=['PUT'])
@jwt_required()
def update_movie(id):
    claims = get_jwt()
    if not claims.get("is_admin"):
        return jsonify({"error": "Access denied – admin only"}), 403
    try:
        movie = Movie.query.get_or_404(id)
        data = request.get_json()
        movie.title = data.get('title', movie.title)
        movie.description = data.get('description', movie.description)
        movie.poster_url = data.get('poster_url', movie.poster_url)
        db.session.commit()
        return jsonify({"message": "Movie updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/movies/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_movie(id):
    claims = get_jwt()
    if not claims.get("is_admin"):
        return jsonify({"error": "Access denied – admin only"}), 403

    movie = Movie.query.get(id)
    if not movie:
        return jsonify({"error": "Movie not found"}), 404

    movie_title = movie.title
    db.session.delete(movie)
    db.session.commit()
    return jsonify({"message": f"Movie '{movie_title}' deleted"}), 200


#create admin and start up all working
def create_admin_account():
    if User.query.filter_by(is_admin=True).first() is None:
        hashed_password = bcrypt.generate_password_hash("adminpassword").decode("utf-8")
        admin_user = User(username="admin", password=hashed_password, is_admin=True)
        db.session.add(admin_user)
        db.session.commit()
        return jsonify({"message": "admin account created"}), 201
    else:
        return jsonify({"message": "admin not created"}), 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_admin_account()
    app.run(debug=True)
