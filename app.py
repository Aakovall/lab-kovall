import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from models import db, User, Role, Book, Genre, Cover, Review, Collection
import hashlib
import bleach
import markdown
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)

# Конфигурация базы данных
if 'DATABASE_URL' in os.environ:
    # Для Render
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL'].replace('postgres://', 'postgresql://')
    logger.info("Using PostgreSQL database from DATABASE_URL")
else:
    # Для локальной разработки
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
    logger.info("Using SQLite database")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev')
app.config['UPLOAD_FOLDER'] = 'covers'
app.config['STATIC_COVERS_FOLDER'] = 'static/covers'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Регистрация фильтра markdown
@app.template_filter('markdown')
def markdown_filter(text):
    return markdown.markdown(text)

# Инициализация расширений
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Создание необходимых директорий
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['STATIC_COVERS_FOLDER'], exist_ok=True)

# Функция для добавления тестовых книг
def add_test_books():
    print("Начинаем добавление тестовых книг...")
    test_books = [
        {
            'title': 'Властелин колец',
            'author': 'Джон Р. Р. Толкин',
            'year': 1954,
            'publisher': 'Allen & Unwin',
            'pages': 1178,
            'description': 'Эпическая фэнтезийная трилогия о борьбе за Кольцо Всевластия и противостоянии сил добра и зла.',
            'genres': ['Фантастика', 'Приключения']
        },
        {
            'title': '1984',
            'author': 'Джордж Оруэлл',
            'year': 1949,
            'publisher': 'Secker & Warburg',
            'pages': 328,
            'description': 'Антиутопический роман о тоталитарном обществе, где правит Большой Брат.',
            'genres': ['Фантастика', 'Психологический']
        },
        {
            'title': 'Убить пересмешника',
            'author': 'Харпер Ли',
            'year': 1960,
            'publisher': 'J. B. Lippincott & Co.',
            'pages': 281,
            'description': 'Роман о расовой несправедливости и потере невинности в американском Юге.',
            'genres': ['Роман', 'Драма']
        },
        {
            'title': 'Великий Гэтсби',
            'author': 'Фрэнсис Скотт Фицджеральд',
            'year': 1925,
            'publisher': 'Charles Scribner\'s Sons',
            'pages': 180,
            'description': 'Роман о "американской мечте" и её крахе в эпоху "ревущих двадцатых".',
            'genres': ['Роман', 'Драма']
        },
        {
            'title': 'Алхимик',
            'author': 'Пауло Коэльо',
            'year': 1988,
            'publisher': 'HarperTorch',
            'pages': 208,
            'description': 'Философская притча о поиске своего предназначения и сокровищах жизни.',
            'genres': ['Роман', 'Приключения']
        },
        {
            'title': 'Тень ветра',
            'author': 'Карлос Руис Сафон',
            'year': 2001,
            'publisher': 'Planeta',
            'pages': 544,
            'description': 'Захватывающий роман о таинственной книге и её влиянии на судьбы людей.',
            'genres': ['Роман', 'Детектив']
        },
        {
            'title': 'Марсианин',
            'author': 'Энди Вейер',
            'year': 2011,
            'publisher': 'Crown',
            'pages': 369,
            'description': 'Научно-фантастический роман о выживании астронавта на Марсе.',
            'genres': ['Фантастика', 'Приключения']
        },
        {
            'title': 'Сто лет одиночества',
            'author': 'Габриэль Гарсиа Маркес',
            'year': 1967,
            'publisher': 'Editorial Sudamericana',
            'pages': 417,
            'description': 'Магический реализм в истории семьи Буэндиа на протяжении ста лет.',
            'genres': ['Роман', 'Фантастика']
        }
    ]
    
    for book_data in test_books:
        # Проверяем, существует ли уже книга с таким названием
        if not Book.query.filter_by(title=book_data['title']).first():
            print(f"Добавляем книгу: {book_data['title']}")
            book = Book(
                title=book_data['title'],
                author=book_data['author'],
                year=book_data['year'],
                publisher=book_data['publisher'],
                pages=book_data['pages'],
                description=book_data['description']
            )
            
            # Добавляем книгу в сессию перед добавлением жанров
            db.session.add(book)
            db.session.flush()  # Получаем ID книги
            
            # Добавляем жанры
            for genre_name in book_data['genres']:
                genre = Genre.query.filter_by(name=genre_name).first()
                if genre:
                    book.genres.append(genre)
                    print(f"Добавлен жанр {genre_name} к книге {book_data['title']}")
            
            try:
                db.session.commit()
                print(f"Книга {book_data['title']} успешно добавлена")
            except Exception as e:
                print(f"Ошибка при добавлении книги {book_data['title']}: {str(e)}")
                db.session.rollback()
        else:
            print(f"Книга {book_data['title']} уже существует")

# Создание базы данных при первом запуске
with app.app_context():
    db.create_all()
    # Создаем роли, если их нет
    if not Role.query.first():
        print("Создаем роли...")
        roles = [
            Role(name='Администратор', description='Суперпользователь, имеет полный доступ к системе'),
            Role(name='Модератор', description='Может редактировать данные книг и производить модерацию рецензий'),
            Role(name='Пользователь', description='Может оставлять рецензии')
        ]
        db.session.add_all(roles)
        db.session.commit()
        print("Роли созданы")
        
        # Создаем жанры, если их нет
        if not Genre.query.first():
            print("Создаем жанры...")
            genres = [
                'Фантастика', 'Детектив', 'Роман', 'Поэзия', 'Драма',
                'Комедия', 'Трагедия', 'Приключения', 'Исторический',
                'Биография', 'Учебная литература', 'Детская литература',
                'Психологический'
            ]
            for genre_name in genres:
                genre = Genre(name=genre_name)
                db.session.add(genre)
                print(f"Добавлен жанр: {genre_name}")
            db.session.commit()
            print("Жанры созданы")
            
            # Создаем администратора
            print("Создаем администратора...")
            admin = User(
                login='admin',
                last_name='Админ',
                first_name='Админ',
                role_id=1
            )
            admin.set_password('admin')
            db.session.add(admin)
            db.session.commit()
            print("Администратор создан")
            
            # Добавляем тестовые книги
            add_test_books()

# Маршруты для аутентификации
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login = request.form.get('login')
        password = request.form.get('password')
        remember = request.form.get('remember', False)
        
        user = User.query.filter_by(login=login).first()
        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        
        flash('Невозможно аутентифицироваться с указанными логином и паролем')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# Главная страница
@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    books = Book.query.order_by(Book.year.desc()).paginate(page=page, per_page=10)
    print(f"Найдено книг: {books.total}")
    for book in books.items:
        print(f"Книга: {book.title}, Автор: {book.author}, Год: {book.year}")
        # Рассчитываем средний рейтинг
        reviews = Review.query.filter_by(book_id=book.id).all()
        if reviews:
            book.avg_rating = sum(review.rating for review in reviews) / len(reviews)
        else:
            book.avg_rating = 0
    return render_template('index.html', books=books)

# Маршруты для работы с книгами
@app.route('/book/<int:book_id>')
def book_detail(book_id):
    book = Book.query.get_or_404(book_id)
    return render_template('book_detail.html', book=book)

@app.route('/book/new', methods=['GET', 'POST'])
@login_required
def book_new():
    if current_user.role.name != 'Администратор':
        flash('У вас недостаточно прав для выполнения данного действия')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            # Создание книги
            book = Book(
                title=request.form['title'],
                description=bleach.clean(request.form['description']),
                year=request.form['year'],
                publisher=request.form['publisher'],
                author=request.form['author'],
                pages=request.form['pages']
            )
            db.session.add(book)
            db.session.flush()  # Получаем ID книги
            
            # Обработка жанров
            genre_ids = request.form.getlist('genres')
            for genre_id in genre_ids:
                genre = Genre.query.get(genre_id)
                if genre:
                    book.genres.append(genre)
            
            # Обработка обложки
            if 'cover' in request.files:
                file = request.files['cover']
                if file.filename:
                    filename = secure_filename(file.filename)
                    file_content = file.read()
                    md5_hash = hashlib.md5(file_content).hexdigest()
                    
                    # Проверка на дубликат
                    existing_cover = Cover.query.filter_by(md5_hash=md5_hash).first()
                    if existing_cover:
                        book.cover = existing_cover
                    else:
                        cover = Cover(
                            filename=filename,
                            mime_type=file.content_type,
                            md5_hash=md5_hash,
                            book_id=book.id
                        )
                        db.session.add(cover)
                        
                        # Сохранение файла
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], str(cover.id))
                        with open(file_path, 'wb') as f:
                            f.write(file_content)
            
            db.session.commit()
            flash('Книга успешно добавлена')
            return redirect(url_for('book_detail', book_id=book.id))
            
        except Exception as e:
            db.session.rollback()
            flash('При сохранении данных возникла ошибка. Проверьте корректность введённых данных.')
            return render_template('book_form.html', book=book)
    
    genres = Genre.query.all()
    return render_template('book_form.html', genres=genres)

@app.route('/book/<int:book_id>/edit', methods=['GET', 'POST'])
@login_required
def book_edit(book_id):
    if current_user.role.name != 'Администратор':
        flash('У вас недостаточно прав для выполнения данного действия')
        return redirect(url_for('index'))
    
    book = Book.query.get_or_404(book_id)
    
    if request.method == 'POST':
        try:
            book.title = request.form['title']
            book.description = bleach.clean(request.form['description'])
            book.year = request.form['year']
            book.publisher = request.form['publisher']
            book.author = request.form['author']
            book.pages = request.form['pages']
            
            # Обработка жанров
            book.genres.clear()
            genre_ids = request.form.getlist('genres')
            for genre_id in genre_ids:
                genre = Genre.query.get(genre_id)
                if genre:
                    book.genres.append(genre)
            
            # Обработка обложки
            if 'cover' in request.files:
                file = request.files['cover']
                if file.filename:
                    filename = secure_filename(file.filename)
                    file_content = file.read()
                    
                    # Удаляем старую обложку, если она есть
                    if book.cover:
                        old_cover_path = os.path.join(app.config['UPLOAD_FOLDER'], book.cover.filename)
                        if os.path.exists(old_cover_path):
                            os.remove(old_cover_path)
                        db.session.delete(book.cover)
                    
                    cover = Cover(
                        filename=filename,
                        mime_type=file.content_type,
                        md5_hash=filename,  # Используем имя файла как хеш
                        book_id=book.id
                    )
                    db.session.add(cover)
                    
                    # Сохранение файла
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    with open(file_path, 'wb') as f:
                        f.write(file_content)
            
            db.session.commit()
            flash('Книга успешно обновлена')
            return redirect(url_for('book_detail', book_id=book.id))
            
        except Exception as e:
            db.session.rollback()
            flash('При сохранении данных возникла ошибка. Проверьте корректность введённых данных.')
    
    genres = Genre.query.all()
    return render_template('book_form.html', book=book, genres=genres)

@app.route('/book/<int:book_id>/delete', methods=['POST'])
@login_required
def book_delete(book_id):
    if current_user.role.name != 'Администратор':
        flash('У вас недостаточно прав для выполнения данного действия')
        return redirect(url_for('index'))
    
    book = Book.query.get_or_404(book_id)
    
    try:
        # Удаляем обложку, если она есть
        if book.cover:
            cover_path = os.path.join(app.config['UPLOAD_FOLDER'], book.cover.md5_hash)
            if os.path.exists(cover_path):
                os.remove(cover_path)
        
        db.session.delete(book)
        db.session.commit()
        flash('Книга успешно удалена')
    except Exception as e:
        db.session.rollback()
        flash('При удалении книги возникла ошибка')
    
    return redirect(url_for('index'))

# Маршруты для работы с рецензиями
@app.route('/book/<int:book_id>/review', methods=['GET', 'POST'])
@login_required
def review_new(book_id):
    book = Book.query.get_or_404(book_id)
    
    # Проверка, не оставлял ли пользователь уже рецензию
    existing_review = Review.query.filter_by(book_id=book_id, user_id=current_user.id).first()
    if existing_review:
        flash('Вы уже оставили рецензию на эту книгу')
        return redirect(url_for('book_detail', book_id=book_id))
    
    if request.method == 'POST':
        try:
            rating = int(request.form.get('rating', 0))
            text = request.form.get('text', '').strip()
            
            if not text:
                flash('Текст рецензии не может быть пустым')
                return render_template('review_form.html', book=book)
            
            if rating < 0 or rating > 5:
                flash('Некорректная оценка')
                return render_template('review_form.html', book=book)
            
            review = Review(
                book_id=book_id,
                user_id=current_user.id,
                rating=rating,
                text=bleach.clean(text)
            )
            db.session.add(review)
            db.session.commit()
            flash('Рецензия успешно добавлена')
            return redirect(url_for('book_detail', book_id=book_id))
        except Exception as e:
            print(f"Ошибка при сохранении рецензии: {str(e)}")
            db.session.rollback()
            flash('При сохранении рецензии возникла ошибка')
            return render_template('review_form.html', book=book)
    
    return render_template('review_form.html', book=book)

# Маршруты для работы с подборками
@app.route('/collections')
@login_required
def collections():
    if current_user.role.name != 'Пользователь':
        flash('У вас недостаточно прав для выполнения данного действия')
        return redirect(url_for('index'))
    
    collections = Collection.query.filter_by(user_id=current_user.id).order_by(Collection.created_at.desc()).all()
    return render_template('collections.html', collections=collections)

@app.route('/collection/new', methods=['POST'])
@login_required
def collection_new():
    if current_user.role.name != 'Пользователь':
        flash('У вас недостаточно прав для выполнения данного действия')
        return redirect(url_for('index'))
    
    name = request.form.get('name', '').strip()
    if not name:
        flash('Название подборки не может быть пустым')
        return redirect(url_for('collections'))
    
    collection = Collection(name=name, user_id=current_user.id)
    db.session.add(collection)
    db.session.commit()
    
    flash('Подборка успешно создана')
    return redirect(url_for('collections'))

@app.route('/collection/<int:collection_id>')
@login_required
def collection_detail(collection_id):
    collection = Collection.query.get_or_404(collection_id)
    
    if collection.user_id != current_user.id:
        flash('У вас нет доступа к этой подборке')
        return redirect(url_for('collections'))
    
    # Рассчитываем средний рейтинг для каждой книги
    for book in collection.books:
        reviews = Review.query.filter_by(book_id=book.id).all()
        if reviews:
            book.avg_rating = sum(review.rating for review in reviews) / len(reviews)
        else:
            book.avg_rating = 0
    
    return render_template('collection_detail.html', collection=collection)

@app.route('/book/<int:book_id>/add-to-collection', methods=['POST'])
@login_required
def add_to_collection(book_id):
    if current_user.role.name != 'Пользователь':
        flash('У вас недостаточно прав для выполнения данного действия')
        return redirect(url_for('book_detail', book_id=book_id))
    
    collection_id = request.form.get('collection_id')
    if not collection_id:
        flash('Не выбрана подборка')
        return redirect(url_for('book_detail', book_id=book_id))
    
    book = Book.query.get_or_404(book_id)
    collection = Collection.query.get_or_404(collection_id)
    
    if collection.user_id != current_user.id:
        flash('У вас нет доступа к этой подборке')
        return redirect(url_for('book_detail', book_id=book_id))
    
    if book not in collection.books:
        collection.books.append(book)
        db.session.commit()
        flash('Книга успешно добавлена в подборку')
    else:
        flash('Книга уже есть в этой подборке')
    
    return redirect(url_for('book_detail', book_id=book_id))

@app.route('/collection/<int:collection_id>/book/<int:book_id>/remove', methods=['POST'])
@login_required
def remove_from_collection(collection_id, book_id):
    collection = Collection.query.get_or_404(collection_id)
    
    if collection.user_id != current_user.id:
        flash('У вас нет доступа к этой подборке')
        return redirect(url_for('collections'))
    
    book = Book.query.get_or_404(book_id)
    if book in collection.books:
        collection.books.remove(book)
        db.session.commit()
        flash('Книга успешно удалена из подборки')
    
    return redirect(url_for('collection_detail', collection_id=collection_id))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            # Проверяем, не занят ли логин
            if User.query.filter_by(login=request.form['login']).first():
                flash('Пользователь с таким логином уже существует')
                return render_template('register.html')
            
            # Создаем нового пользователя
            user = User(
                login=request.form['login'],
                last_name=request.form['last_name'],
                first_name=request.form['first_name'],
                role_id=3  # Роль "Пользователь"
            )
            user.set_password(request.form['password'])
            
            db.session.add(user)
            db.session.commit()
            
            flash('Регистрация успешна! Теперь вы можете войти.')
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            flash('При регистрации возникла ошибка')
            return render_template('register.html')
    
    return render_template('register.html')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_hash(file):
    """Вычисляет MD5 хеш файла"""
    md5_hash = hashlib.md5()
    for chunk in iter(lambda: file.read(4096), b""):
        md5_hash.update(chunk)
    file.seek(0)  # Сбрасываем указатель файла в начало
    return md5_hash.hexdigest()

@app.route('/book/<int:book_id>/cover', methods=['POST'])
@login_required
def upload_cover(book_id):
    if current_user.role.name != 'Администратор':
        flash('У вас недостаточно прав для выполнения данного действия')
        return redirect(url_for('book_detail', book_id=book_id))
    
    book = Book.query.get_or_404(book_id)
    
    if 'cover' not in request.files:
        flash('Файл не выбран')
        return redirect(url_for('book_detail', book_id=book_id))
    
    file = request.files['cover']
    if file.filename == '':
        flash('Файл не выбран')
        return redirect(url_for('book_detail', book_id=book_id))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        mime_type = file.content_type
        
        # Удаляем старую обложку, если она есть
        if book.cover:
            old_cover_path = os.path.join(app.config['UPLOAD_FOLDER'], book.cover.filename)
            if os.path.exists(old_cover_path):
                os.remove(old_cover_path)
            db.session.delete(book.cover)
        
        # Сохраняем файл с оригинальным именем
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Создаем запись в базе данных
        cover = Cover(
            filename=filename,
            mime_type=mime_type,
            md5_hash=filename,  # Используем имя файла как хеш
            book_id=book.id
        )
        db.session.add(cover)
        db.session.commit()
        
        flash('Обложка успешно добавлена')
        return redirect(url_for('book_detail', book_id=book_id))
    
    flash('Недопустимый формат файла')
    return redirect(url_for('book_detail', book_id=book_id))

@app.route('/covers/<filename>')
def get_cover(filename):
    """Маршрут для получения обложки"""
    logger.info(f"Запрос обложки: {filename}")
    
    # Декодируем имя файла из URL
    filename = filename.replace('_', ' ')  # Заменяем подчеркивания на пробелы
    logger.info(f"Декодированное имя файла: {filename}")
    
    # Сначала ищем в директории пользовательских загрузок
    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    logger.info(f"Проверяем путь: {upload_path}")
    if os.path.exists(upload_path):
        logger.info(f"Обложка найдена в {upload_path}")
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    
    # Если не нашли, ищем в директории статических файлов
    static_path = os.path.join(app.config['STATIC_COVERS_FOLDER'], filename)
    logger.info(f"Проверяем путь: {static_path}")
    if os.path.exists(static_path):
        logger.info(f"Обложка найдена в {static_path}")
        return send_from_directory(app.config['STATIC_COVERS_FOLDER'], filename)
    
    # Если файл не найден, пробуем найти его без учета регистра и с разными вариантами подчеркиваний
    for root, dirs, files in os.walk(app.config['STATIC_COVERS_FOLDER']):
        for file in files:
            logger.info(f"Сравниваем с файлом: {file}")
            # Нормализуем имена файлов для сравнения
            normalized_request = filename.lower().replace('__', '_').replace('_', '')
            normalized_file = file.lower().replace('__', '_').replace('_', '')
            if normalized_file == normalized_request:
                logger.info(f"Обложка найдена (после нормализации): {file}")
                return send_from_directory(root, file)
    
    logger.error(f"Обложка не найдена: {filename}")
    return "Обложка не найдена", 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    db.session.rollback()
    return render_template('error.html', error="Внутренняя ошибка сервера"), 500

@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', error="Страница не найдена"), 404

@app.route('/test-db')
def test_db():
    try:
        # Проверяем подключение к базе данных
        db.session.execute('SELECT 1')
        # Проверяем наличие таблиц
        tables = db.engine.table_names()
        return {
            'status': 'success',
            'message': 'Database connection successful',
            'tables': tables
        }
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }, 500

@app.route('/test-cover/<int:book_id>')
def test_cover(book_id):
    """Маршрут для проверки информации об обложке"""
    book = Book.query.get_or_404(book_id)
    if book.cover:
        return {
            'book_title': book.title,
            'cover_filename': book.cover.filename,
            'cover_md5_hash': book.cover.md5_hash,
            'cover_mime_type': book.cover.mime_type
        }
    return {'error': 'У книги нет обложки'}, 404

@app.route('/update-covers')
def update_covers():
    """Обновление имен файлов обложек в базе данных"""
    covers = Cover.query.all()
    updated = []
    
    # Словарь соответствия имен файлов
    file_mapping = {
        '484-0_1.jpg': '484-0 1.jpg',
        '484-0_2.jpg': '484-0 2.jpg',
        '484-0.jpg': '484-0.jpg',
        'cf075c091f8977b5b225c4f0fe14f0a4.jpg': 'cf075c091f8977b5b225c4f0fe14f0a4.jpg',
        'cover1_w340.jpg': 'cover1w340.jpg',
        'i694450.jpg': 'i694450.jpg',
        '8348342.jpg': '8348342.jpg'
    }
    
    for cover in covers:
        logger.info(f"Обработка обложки для книги {cover.book.title}:")
        logger.info(f"Текущее имя файла в БД: {cover.filename}")
        
        # Проверяем, есть ли файл в словаре соответствия
        if cover.filename in file_mapping:
            new_filename = file_mapping[cover.filename]
            if os.path.exists(os.path.join(app.config['STATIC_COVERS_FOLDER'], new_filename)):
                cover.filename = new_filename
                cover.md5_hash = new_filename
                updated.append(f"Обновлена обложка для книги {cover.book.title}: {new_filename}")
                logger.info(f"Найдено соответствие в словаре! Обновляем на: {new_filename}")
                continue
        
        # Если файл не найден в словаре, ищем по имени без расширения
        base_name = os.path.splitext(cover.filename)[0]
        found = False
        
        for root, dirs, files in os.walk(app.config['STATIC_COVERS_FOLDER']):
            for file in files:
                file_base_name = os.path.splitext(file)[0]
                # Нормализуем имена файлов для сравнения
                normalized_base = base_name.lower().replace('__', '_').replace('_', '')
                normalized_file = file_base_name.lower().replace('__', '_').replace('_', '')
                if normalized_file == normalized_base:
                    cover.filename = file
                    cover.md5_hash = file
                    updated.append(f"Обновлена обложка для книги {cover.book.title}: {file}")
                    logger.info(f"Найдено совпадение! Обновляем на: {file}")
                    found = True
                    break
            if found:
                break
        
        if not found:
            logger.warning(f"Файл не найден для книги {cover.book.title}")
    
    if updated:
        db.session.commit()
        return {'message': 'Обложки обновлены', 'updates': updated}
    return {'message': 'Нет обложек для обновления'}

@app.route('/list-covers')
def list_covers():
    """Вывод информации о всех обложках в базе данных"""
    covers = Cover.query.all()
    result = []
    
    for cover in covers:
        result.append({
            'book_title': cover.book.title,
            'filename': cover.filename,
            'md5_hash': cover.md5_hash,
            'mime_type': cover.mime_type
        })
    
    return {'covers': result}

@app.route('/debug-covers')
def debug_covers():
    """Маршрут для отладки обложек"""
    covers = Cover.query.all()
    result = []
    for cover in covers:
        # Получаем книгу через связь cover.book
        book = cover.book
        result.append({
            'id': cover.id,
            'filename': cover.filename,
            'md5_hash': cover.md5_hash,
            'book_title': book.title if book else 'Нет привязанной книги'
        })
    return jsonify(result)

@app.route('/cleanup-books')
def cleanup_books():
    """Удаление книг без обложек"""
    books_to_remove = ['Три товарища', 'Тихий Дон']
    removed = []
    
    for title in books_to_remove:
        book = Book.query.filter_by(title=title).first()
        if book:
            db.session.delete(book)
            removed.append(title)
    
    if removed:
        db.session.commit()
        return {'message': 'Книги удалены', 'removed': removed}
    return {'message': 'Нет книг для удаления'}

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 