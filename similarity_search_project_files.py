# similarity_search/settings.py
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'your-secret-key-here'
DEBUG = True
ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'similarity_search_app.apps.SimilaritySearchAppConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'similarity_search.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'similarity_search.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    },
    'admin_db': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'admin.db',
    },
    'it_db': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'it.db',
    },
    'finance_db': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'finance.db',
    },
    'hr_db': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'hr.db',
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'similarity_search_app.CustomUser'

# similarity_search/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('similarity_search_app.urls')),
]

# similarity_search_app/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    username = None

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

class Source(models.Model):
    id = models.IntegerField(primary_key=True)
    source_text = models.TextField()
    author = models.CharField(max_length=100)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'source_tbl'

# similarity_search_app/signals.py
from django.db.backends.signals import connection_created

def load_sqlite_vec(sender, connection, **kwargs):
    if connection.vendor == 'sqlite' and connection.alias in ['admin_db', 'it_db', 'finance_db', 'hr_db']:
        connection.connection.enable_load_extension(True)
        connection.connection.load_extension('/path/to/vec0')  # Update with actual path

# similarity_search_app/apps.py
from django.apps import AppConfig

class SimilaritySearchAppConfig(AppConfig):
    name = 'similarity_search_app'

    def ready(self):
        from .signals import load_sqlite_vec
        connection_created.connect(load_sqlite_vec)

# similarity_search_app/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('signup/', views.signup, name='signup'),
    path('signin/', views.signin, name='signin'),
    path('signout/', views.signout, name='signout'),
    path('search/', views.search, name='search'),
    path('paginate/', views.paginate_search, name='paginate_search'),
]

# similarity_search_app/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import make_password
from django.http import JsonResponse
from django.db import connections
from sentence_transformers import SentenceTransformer
import json

model = SentenceTransformer('all-mpnet-base-v2')

def signup(request):
    if request.method == 'POST':
        email = request.POST['email']
        password = request.POST['password']
        user = CustomUser(email=email, password=make_password(password))
        user.save()
        return redirect('signin')
    return render(request, 'signup.html')

def signin(request):
    if request.method == 'POST':
        email = request.POST['email']
        password = request.POST['password']
        user = authenticate(request, email=email, password=password)
        if user is not None:
            login(request, user)
            return redirect('home')
    return render(request, 'signin.html')

def signout(request):
    logout(request)
    return redirect('signin')

def home(request):
    if not request.user.is_authenticated:
        return redirect('signin')
    return render(request, 'home.html')

def search(request):
    if not request.user.is_authenticated:
        return redirect('signin')
    if request.method == 'POST':
        source_type = request.POST['source_type'].lower()
        keyword = request.POST['keyword']
        db_alias = f"{source_type}_db"
        query_embedding = model.encode(keyword).tobytes()
        conn = connections[db_alias]
        cursor = conn.cursor()
        cursor.execute("""
            SELECT rowid, distance
            FROM embedding_tbl
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT 25
        """, (query_embedding,))
        results = cursor.fetchall()
        request.session['search_results'] = results
        request.session['source_type'] = source_type
        page = 1
        start = (page - 1) * 5
        end = start + 5
        current_results = results[start:end]
        rowids = [rowid for rowid, _ in current_results]
        sources = Source.objects.using(db_alias).filter(id__in=rowids)
        source_dict = {s.id: s for s in sources}
        ordered_sources_with_distance = [(source_dict[rowid], distance) for rowid, distance in current_results if rowid in source_dict]
        return render(request, 'search_results.html', {
            'sources_with_distance': ordered_sources_with_distance,
            'page': page,
            'total_pages': (len(results) + 4) // 5
        })
    return redirect('home')

def paginate_search(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=403)
    page = int(request.GET.get('page', 1))
    results = request.session.get('search_results', [])
    source_type = request.session.get('source_type', '')
    if not results or not source_type:
        return JsonResponse({'error': 'No search results'}, status=400)
    db_alias = f"{source_type}_db"
    start = (page - 1) * 5
    end = start + 5
    current_results = results[start:end]
    rowids = [rowid for rowid, _ in current_results]
    sources = Source.objects.using(db_alias).filter(id__in=rowids)
    source_dict = {s.id: s for s in sources}
    ordered_sources_with_distance = [(source_dict[rowid], distance) for rowid, distance in current_results if rowid in source_dict]
    data = [{
        'id': source.id,
        'source_text': source.source_text,
        'distance': distance,
        'author': source.author,
        'created_at': source.created_at.strftime('%Y-%m-%d %H:%M:%S')
    } for source, distance in ordered_sources_with_distance]
    return JsonResponse({'sources': data})

# similarity_search_app/management/commands/populate_data.py
from django.core.management.base import BaseCommand
from faker import Faker
from sentence_transformers import SentenceTransformer
from django.db import connections

fake = Faker()
model = SentenceTransformer('all-mpnet-base-v2')

class Command(BaseCommand):
    help = 'Populate sample data into source type databases'

    def handle(self, *args, **kwargs):
        for source_type in ['admin', 'it', 'finance', 'hr']:
            db_alias = f"{source_type}_db"
            conn = connections[db_alias]
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS source_tbl (
                    id INTEGER PRIMARY KEY,
                    source_text TEXT,
                    author TEXT,
                    created_at TIMESTAMP
                )
            """)
            cursor.execute("CREATE VIRTUAL TABLE IF NOT EXISTS embedding_tbl USING vec0(embedding float[768])")
            sources = [(fake.paragraph(), fake.name(), fake.date_time_this_decade()) for _ in range(1000)]
            cursor.executemany("INSERT INTO source_tbl (source_text, author, created_at) VALUES (?, ?, ?)", sources)
            cursor.execute("SELECT id FROM source_tbl ORDER BY id DESC LIMIT 1000")
            ids = [row[0] for row in cursor.fetchall()]
            embeddings = [(id, model.encode(src[0]).tobytes()) for id, src in zip(ids, sources)]
            cursor.executemany("INSERT INTO embedding_tbl (rowid, embedding) VALUES (?, ?)", embeddings)
            conn.commit()
            self.stdout.write(self.style.SUCCESS(f"Populated {source_type}_db"))

# templates/base.html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Similarity Search</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-light bg-light">
        <div class="container-fluid">
            <a class="navbar-brand" href="{% url 'home' %}">Similarity Search</a>
            <div class="collapse navbar-collapse">
                <ul class="navbar-nav me-auto mb-2 mb-lg-0">
                    <li class="nav-item"><a class="nav-link" href="{% url 'home' %}">Home</a></li>
                    {% if user.is_authenticated %}
                        <li class="nav-item"><a class="nav-link" href="{% url 'signout' %}">Sign Out</a></li>
                    {% else %}
                        <li class="nav-item"><a class="nav-link" href="{% url 'signup' %}">Sign Up</a></li>
                        <li class="nav-item"><a class="nav-link" href="{% url 'signin' %}">Sign In</a></li>
                    {% endif %}
                </ul>
            </div>
        </div>
    </nav>
    <div class="container mt-4">
        {% block content %}{% endblock %}
    </div>
    <footer class="bg-light text-center py-3 mt-4">
        <p>&copy; 2023 Similarity Search</p>
    </footer>
</body>
</html>

# templates/home.html
{% extends 'base.html' %}
{% block content %}
    <h2>Similarity Search</h2>
    <form method="post" action="{% url 'search' %}">
        {% csrf_token %}
        <div class="mb-3">
            <label for="source_type" class="form-label">Source Type</label>
            <select class="form-select" id="source_type" name="source_type">
                <option value="ADMIN">ADMIN</option>
                <option value="IT">IT</option>
                <option value="FINANCE">FINANCE</option>
                <option value="HR">HR</option>
            </select>
        </div>
        <div class="mb-3">
            <label for="keyword" class="form-label">Search Keyword</label>
            <input type="text" class="form-control" id="keyword" name="keyword" required>
        </div>
        <button type="submit" class="btn btn-primary">Search</button>
    </form>
{% endblock %}

# templates/signup.html
{% extends 'base.html' %}
{% block content %}
    <h2>Sign Up</h2>
    <form method="post">
        {% csrf_token %}
        <div class="mb-3">
            <label for="email" class="form-label">Email</label>
            <input type="email" class="form-control" id="email" name="email" required>
        </div>
        <div class="mb-3">
            <label for="password" class="form-label">Password</label>
            <input type="password" class="form-control" id="password" name="password" required>
        </div>
        <button type="submit" class="btn btn-primary">Sign Up</button>
    </form>
{% endblock %}

# templates/signin.html
{% extends 'base.html' %}
{% block content %}
    <h2>Sign In</h2>
    <form method="post">
        {% csrf_token %}
        <div class="mb-3">
            <label for="email" class="form-label">Email</label>
            <input type="email" class="form-control" id="email" name="email" required>
        </div>
        <div class="mb-3">
            <label for="password" class="form-label">Password</label>
            <input type="password" class="form-control" id="password" name="password" required>
        </div>
        <button type="submit" class="btn btn-primary">Sign In</button>
    </form>
{% endblock %}

# templates/search_results.html
{% extends 'base.html' %}
{% block content %}
    <h2>Search Results</h2>
    <table class="table">
        <thead>
            <tr>
                <th>Source Text</th>
                <th>Distance</th>
            </tr>
        </thead>
        <tbody id="resultsTable">
            {% for source, distance in sources_with_distance %}
                <tr>
                    <td><a href="#" onclick="showSourceDetails('{{ source.id }}')" data-source-id="{{ source.id }}">{{ source.source_text }}</a></td>
                    <td>{{ distance }}</td>
                </tr>
            {% endfor %}
        </tbody>
    </table>
    <nav>
        <ul class="pagination">
            {% if page > 1 %}
                <li class="page-item"><a class="page-link" href="#" onclick="loadPage({{ page|add:-1 }})">Previous</a></li>
            {% endif %}
            {% for i in total_pages|times %}
                <li class="page-item {% if page == i|add:1 %}active{% endif %}">
                    <a class="page-link" href="#" onclick="loadPage({{ i|add:1 }})">{{ i|add:1 }}</a>
                </li>
            {% endfor %}
            {% if page < total_pages %}
                <li class="page-item"><a class="page-link" href="#" onclick="loadPage({{ page|add:1 }})">Next</a></li>
            {% endif %}
        </ul>
    </nav>
    <div class="modal" id="sourceModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Source Details</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body" id="modalBody"></div>
            </div>
        </div>
    </div>
    <script>
        var source_details = {
            {% for source, _ in sources_with_distance %}
                "{{ source.id }}": {
                    "source_text": "{{ source.source_text|escapejs }}",
                    "author": "{{ source.author|escapejs }}",
                    "created_at": "{{ source.created_at|date:'Y-m-d H:i:s'|escapejs }}"
                },
            {% endfor %}
        };
        function showSourceDetails(sourceId) {
            var details = source_details[sourceId];
            var content = '<p><strong>Source Text:</strong> ' + details.source_text + '</p>' +
                          '<p><strong>Author:</strong> ' + details.author + '</p>' +
                          '<p><strong>Created At:</strong> ' + details.created_at + '</p>';
            document.getElementById('modalBody').innerHTML = content;
            var modal = new bootstrap.Modal(document.getElementById('sourceModal'));
            modal.show();
        }
        function loadPage(page) {
            fetch('/paginate/?page=' + page)
                .then(response => response.json())
                .then(data => {
                    var tbody = document.getElementById('resultsTable');
                    tbody.innerHTML = '';
                    data.sources.forEach(item => {
                        var row = '<tr>' +
                                  '<td><a href="#" onclick="showSourceDetails(\'' + item.id + '\')">' + item.source_text + '</a></td>' +
                                  '<td>' + item.distance + '</td>' +
                                  '</tr>';
                        tbody.innerHTML += row;
                        source_details[item.id] = {
                            source_text: item.source_text,
                            author: item.author,
                            created_at: item.created_at
                        };
                    });
                    window.history.pushState({}, '', '?page=' + page);
                });
        }
        // Custom filter for range
        window.times = function(n) { return Array.apply(null, {length: n}).map(Number.call, Number); };
    </script>
{% endblock %}

# README.md
# Similarity Search Project

## Prerequisites
- Python 3.8+
- SQLite with `sqlite_vec` extension (https://github.com/asg017/sqlite-vec)

## Installation Steps
1. **Install Dependencies**:
   ```bash
   pip install django sentence-transformers faker
   ```
   Build and install `sqlite-vec` extension per the GitHub instructions. Place the `vec0` file in an accessible path (e.g., `/usr/local/lib/vec0`).

2. **Create Django Project**:
   ```bash
   django-admin startproject similarity_search
   cd similarity_search
   ```

3. **Create App**:
   ```bash
   python manage.py startapp similarity_search_app
   ```

4. **Configure Settings**:
   - Update `similarity_search/settings.py` with the provided content.
   - Replace `/path/to/vec0` with the actual path to the `sqlite-vec` extension.

5. **Set Up Models and Signals**:
   - Replace `similarity_search_app/models.py`, `signals.py`, and `apps.py` with the provided code.

6. **Configure URLs**:
   - Update `similarity_search/urls.py` and create `similarity_search_app/urls.py` with the provided code.

7. **Create Templates**:
   - Create a `templates` directory in the project root.
   - Add `base.html`, `home.html`, `signup.html`, `signin.html`, and `search_results.html` with the provided code.

8. **Set Up Static Files**:
   - Create a `static` directory in the project root for any additional CSS/JS if needed (not required for this setup).

9. **Create Management Command**:
   - Create `similarity_search_app/management/commands/populate_data.py` with the provided code.

10. **Run Migrations**:
    ```bash
    python manage.py makemigrations
    python manage.py migrate
    ```

11. **Populate Sample Data**:
    ```bash
    python manage.py populate_data
    ```

12. **Run Server**:
    ```bash
    python manage.py runserver
    ```

## Usage
- Access the app at `http://127.0.0.1:8000/`.
- Sign up with an email and password.
- Sign in to access the home page.
- Select a source type, enter a keyword, and click "Search".
- View results with pagination and click source text for details in a modal.

## Notes
- Ensure `sentence-transformers` downloads the model (`all-mpnet-base-v2`) on first run.
- The `sqlite_vec` extension must be correctly installed and its path updated in `signals.py`.