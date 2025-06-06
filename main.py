# Импорт необходимых модулей
import sys  # доступ к системным функциям и аргументам командной строки
import os  # работа с файловой системой
import time  # функции для работы со временем
import sqlite3  # встроенная БД SQLite
import requests  # выполнение HTTP-запросов для получения данных
import logging  # журналирование событий и ошибок
from datetime import datetime  # работа с датой и временем
import matplotlib.dates as mdates  # форматирование дат на графиках
import mplcursors  # добавление подсказок на графики

# Импорт виджетов из PyQt5 для создания интерфейса
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QComboBox, QCheckBox, QProgressBar, QToolButton, QSizeGrip
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QSize  # базовые классы и сигналы
from PyQt5.QtGui import QPalette, QColor, QIcon  # стилизация и иконки
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas  # холст для рисования графиков
from matplotlib.figure import Figure  # создание фигуры для графика

# Настройка логирования: уровень INFO, формат с датой и временем
logging.basicConfig(
    level=logging.INFO,  # уровень логирования
    format='[%(asctime)s] %(levelname)s: %(message)s',  # формат сообщений
    datefmt='%Y-%m-%d %H:%M:%S'  # формат даты/времени
)

def resource_path(relative_path):
    """
    Возвращает корректный путь к файлу при использовании в сборке PyInstaller.
    Если приложение упаковано, поиск в _MEIPASS, иначе текущая директория.
    """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

class ProductUpdateWorker(QObject):
    # Сигналы для обновления строки таблицы, отображения ошибки, прогресса и завершения
    update_row = pyqtSignal(int, dict)
    show_error = pyqtSignal(int)
    progress = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self, ids):
        super().__init__()
        self.ids = ids  # список ID товаров для обновления

    def run(self):
        """
        Последовательное обновление каждого товара из списка self.ids.
        Получает данные и отправляет сигналы для обновления интерфейса.
        """
        total = len(self.ids)  # общее количество товаров
        for idx, pid in enumerate(self.ids):
            product = get_product_info(pid)  # получаем информацию о товаре
            if product:
                self.update_row.emit(idx, product)  # emitir сигнал для обновления строки
            else:
                self.show_error.emit(idx)  # сигнал об ошибке при получении данных
            # обновляем прогресс-бар
            self.progress.emit(int((idx + 1) / total * 100))
            time.sleep(2)  # задержка между запросами
        self.finished.emit()  # сигнал о завершении работы

def get_product_info(card_id):
    """
    Запрашивает информацию о товаре с API Wildberries по его артикулу.
    Возвращает словарь с данными или None при ошибке.
    """
    url = f"https://card.wb.ru/cards/detail?appType=1&curr=rub&dest=-1257786&nm={card_id}"
    try:
        response = requests.get(url, timeout=10)  # выполняем GET-запрос с таймаутом
        response.raise_for_status()  # выброс исключения при ошибочном коде ответа
        data = response.json()['data']['products'][0]  # получаем первый продукт из ответа
        price_raw = data.get("salePriceU")  # цена в копейках
        price = price_raw // 100 if price_raw else None  # конвертация в рубли
        return {
            "id": data["id"],  # артикул товара
            "name": data["name"],  # название товара
            "brand": data.get("brand", ""),  # бренд товара (если есть)
            "price": price  # цена товара (или None)
        }
    except Exception as e:
        # логируем ошибку и возвращаем None
        logging.error(f"Ошибка получения товара {card_id}: {e}")
        return None

class TitleBar(QWidget):
    """
    Пользовательская панель заголовка для перетаскивания и кнопок управления окном.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent  # ссылка на главное окно
        self.setFixedHeight(30)  # фиксированная высота заголовка

        layout = QHBoxLayout(self)  # горизонтальный лэйаут для кнопок
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(0)

        # Метка с заголовком приложения
        title = QLabel("Wildberries Price Tracker", self)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title, alignment=Qt.AlignCenter)

        self.btn_max = None  # кнопка разворачивания/восстановления

        # Добавляем кнопки: свернуть, развернуть/восстановить, закрыть
        for fname, handler in [
            ("minimize.svg", self.parent.showMinimized),
            ("maximize.svg", self.toggle_max_restore),
            ("close.svg", self.parent.close)
        ]:
            btn = QToolButton(self)  # создаем кнопку
            btn.setIcon(self.load_icon(fname))  # загружаем иконку
            btn.setIconSize(QSize(16, 16))
            btn.setAutoRaise(True)
            btn.clicked.connect(handler)  # связываем сигнал с обработчиком
            layout.addWidget(btn)
            if fname == "maximize.svg":
                self.btn_max = btn  # сохраняем кнопку для изменения иконки

    def load_icon(self, filename):
        """
        Загружает иконку: сначала из встроенных ресурсов, иначе из папки icons.
        """
        icon = QIcon(f":/icons/{filename}")
        if icon.isNull():
            # если не найден в ресурсах, загружаем из файловой системы
            icon = QIcon(os.path.join(os.path.dirname(__file__), "icons", filename))
        return icon

    def mousePressEvent(self, e):
        # Сохраняем позицию курсора при нажатии для перетаскивания окна
        if e.button() == Qt.LeftButton:
            self.drag_pos = e.globalPos() - self.parent.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        # Перемещаем окно при перетаскивании мыши
        if e.buttons() & Qt.LeftButton:
            self.parent.move(e.globalPos() - self.drag_pos)
            e.accept()

    def mouseDoubleClickEvent(self, e):
        # Разворачиваем/восстанавливаем окно при двойном клике
        self.toggle_max_restore()

    def toggle_max_restore(self):
        """
        Переключает состояние окна между развернутым и нормальным, обновляя иконку.
        """
        if self.parent.isMaximized():
            self.parent.showNormal()  # возвращаем к нормальному размеру
            icon = self.load_icon("maximize.svg")
        else:
            self.parent.showMaximized()  # разворачиваем окно
            icon = self.load_icon("restore.svg")
        if self.btn_max:
            self.btn_max.setIcon(icon)  # устанавливаем новую иконку

class PriceTrackerApp(QWidget):
    """
    Основной класс приложения для отслеживания цен Wildberries.
    """
    def __init__(self):
        super().__init__()
        # Устанавливаем иконку окна и убираем стандартную рамку
        self.setWindowIcon(QIcon(resource_path("icons/logo.ico")))
        self.setWindowFlag(Qt.FramelessWindowHint)

        self.conn = None  # объект подключения к БД
        self.worker_thread = None  # поток для обновления данных

        # Настраиваем тёмную тему для фона и текста
        pal = QPalette()
        pal.setColor(QPalette.Window, QColor("#121212"))
        pal.setColor(QPalette.WindowText, QColor("#ffffff"))
        self.setPalette(pal)

        # Основной вертикальный лэйаут приложения
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Добавляем нашу пользовательскую панель заголовка
        self.titlebar = TitleBar(self)
        main_layout.addWidget(self.titlebar)

        # Верхняя панель с элементами управления
        self.top_panel = QHBoxLayout()
        self.top_panel.setContentsMargins(10, 10, 10, 0)

        # Выпадающий список для выбора базы данных
        self.db_selector = QComboBox()
        self.db_reload_btn = QToolButton()  # кнопка обновления списка баз
        self.db_reload_btn.setIcon(QIcon(resource_path("icons/refresh.svg")))
        self.db_reload_btn.setIconSize(QSize(16, 16))
        self.db_reload_btn.setAutoRaise(True)
        self.db_reload_btn.setToolTip("Обновить список баз")
        self.db_reload_btn.clicked.connect(self.load_db_list)

        self.load_db_list()  # загружаем список баз данных
        self.db_selector.currentTextChanged.connect(self.change_db)

        # Добавляем элементы на верхнюю панель: кнопка, метка, выпадающий список
        self.top_panel.addWidget(self.db_reload_btn)
        self.top_panel.addWidget(QLabel("Выбор базы:"))
        self.top_panel.addWidget(self.db_selector)

        # Кнопка обновления выбранного товара
        self.update_selected_btn = QPushButton("Обновить выбранный")
        self.update_selected_btn.clicked.connect(self.update_selected_product)

        # Поле ввода артикулов для добавления/обновления
        self.input = QLineEdit()
        self.input.setPlaceholderText("Введите артикул")

        # Кнопка получения и сохранения цены для введённого артикула
        self.fetch_btn = QPushButton("Получить и сохранить цену")
        self.fetch_btn.clicked.connect(self.fetch_price)

        # Кнопка обновления всех товаров
        self.refresh_btn = QPushButton("Обновить всё")
        self.refresh_btn.clicked.connect(self.update_all_products)

        # Чекбокс для скрытия недоступных товаров
        self.hide_unavailable_checkbox = QCheckBox("Скрыть недоступные")
        self.hide_unavailable_checkbox.stateChanged.connect(self.load_product_table)

        # Добавляем кнопки и поля на верхнюю панель
        for w in [self.update_selected_btn, self.input, self.fetch_btn, self.refresh_btn, self.hide_unavailable_checkbox]:
            self.top_panel.addWidget(w)

        main_layout.addLayout(self.top_panel)  # добавляем верхнюю панель в основной лэйаут

        # Центральная часть окна: таблица и график
        self.body = QHBoxLayout()
        self.body.setContentsMargins(10, 10, 10, 10)

        # Таблица для отображения списка товаров
        self.table = QTableWidget()
        self.table.setColumnCount(5)  # количество столбцов
        self.table.setHorizontalHeaderLabels(["Артикул", "Название", "Бренд", "Цена", "Дата"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)  # скрываем номера строк
        self.table.cellClicked.connect(self.on_row_selected)

        # Добавляем таблицу в лэйаут (2 части ширины)
        self.body.addWidget(self.table, 2)

        # Настройка Matplotlib для светлой темы графика
        self.figure = Figure(facecolor="#FFFFFF")  # фон фигуры белый
        self.canvas = FigureCanvas(self.figure)  # холст для рисования
        self.ax = self.figure.add_subplot(111)  # создаём единственную ось

        self.ax.set_facecolor("#F5F5F5")  # фон области графика светло-серый
        self.ax.grid(True, color="#DDDDDD", linestyle="-", linewidth=0.5)  # сетка
        for spine in self.ax.spines.values():
            spine.set_color("#CCCCCC")  # цвет рамок графика

        # Подписи к графику: заголовок и подписи осей
        self.ax.set_title("История цены", color="#202020")
        self.ax.set_xlabel("Дата", color="#202020")
        self.ax.set_ylabel("Цена (руб.)", color="#202020")

        # Поворот подписей по оси X и цвет подписей
        self.ax.tick_params(axis="x", labelrotation=45, colors="#202020")
        self.ax.tick_params(axis="y", colors="#202020")

        # Линия графика: синие точки и линия
        self.line, = self.ax.plot([], [], color="#2962ff", marker="o", linewidth=2)
        self.cursor = mplcursors.cursor(self.line, hover=True)
        self.cursor.connect("add", self.show_tooltip)

        # Добавляем подсказки при наведении на точки графика
        self.cursor = mplcursors.cursor(self.line, hover=True)
        self.cursor.connect("add", self.show_tooltip)

        # Добавляем холст графика в лэйаут (3 части ширины)
        self.body.addWidget(self.canvas, 3)
        main_layout.addLayout(self.body)  # добавляем центральную часть в основной лэйаут

        # Полоса прогресса для обновления всех товаров
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)  # максимальное значение 100%
        self.progress_bar.setTextVisible(True)  # показывать текст с процентом
        self.progress_bar.hide()  # изначально скрыта
        main_layout.addWidget(self.progress_bar)

        # "Ручка" для изменения размера окна
        self.size_grip = QSizeGrip(self)
        main_layout.addWidget(self.size_grip, 0, Qt.AlignRight | Qt.AlignBottom)

        # Заголовок окна и начальный размер
        self.setWindowTitle("Wildberries Price Tracker")
        self.resize(1200, 600)

        # Загружаем таблицу при выборе базы данных
        self.change_db(self.db_selector.currentText())

    def load_db_list(self):
        """
        Загружает список файлов .db из папки db и заполняет выпадающий список.
        """
        os.makedirs("db", exist_ok=True)  # создаём папку db, если не существует
        self.db_selector.clear()  # очищаем текущий список
        # добавляем все файлы с расширением .db
        self.db_selector.addItems([f for f in os.listdir("db") if f.endswith(".db")])

    def init_db(self, path):
        """
        Инициализирует базу данных: создаёт необходимые таблицы, если их нет.
        """
        conn = sqlite3.connect(path)  # подключаемся к БД
        cur = conn.cursor()  # создаём курсор для выполнения запросов
        # создаём таблицу продуктов
        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                name TEXT,
                brand TEXT,
                available INTEGER DEFAULT 1
            )""")
        # создаём таблицу истории цен
        cur.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                product_id INTEGER,
                date TEXT,
                price INTEGER,
                PRIMARY KEY (product_id, date),
                FOREIGN KEY (product_id) REFERENCES products(id)
            )""")
        conn.commit()  # сохраняем изменения
        return conn  # возвращаем объект подключения

    def change_db(self, db_name):
        """
        Меняет текущую базу данных при выборе нового файла в выпадающем списке.
        """
        if not db_name:
            return  # если имя базы пустое, выходим
        if self.conn:
            self.conn.close()  # закрываем старое подключение
        # открываем новое подключение и инициализируем БД
        self.conn = self.init_db(os.path.join("db", db_name))
        self.load_product_table()  # загружаем таблицу продуктов

    def fetch_price(self):
        """
        Получает цену по введённому артикулу, сохраняет и обновляет таблицу.
        """
        card_id = self.input.text().strip()  # получаем текст из поля ввода
        if not card_id.isdigit():  # проверяем, что введены только цифры
            QMessageBox.warning(self, "Ошибка", "Введите числовой артикул")
            return
        product = get_product_info(int(card_id))  # запрашиваем данные товара
        if product:
            self.save_price(product)  # сохраняем в БД
            self.load_product_table()  # обновляем таблицу
        else:
            QMessageBox.warning(self, "Ошибка", "Не удалось получить данные")

    def save_price(self, product):
        """
        Сохраняет информацию о товаре и его цене в базу данных.
        """
        cur = self.conn.cursor()  # создаём курсор
        available = 1 if product["price"] is not None else 0  # определяем доступность
        # добавляем или обновляем запись о товаре
        cur.execute(
            'INSERT OR IGNORE INTO products (id, name, brand, available) VALUES (?, ?, ?, ?)',
            (product["id"], product["name"], product["brand"], available)
        )
        cur.execute('UPDATE products SET available = ? WHERE id = ?', (available, product["id"]))
        if product["price"] is not None:
            today = datetime.now().strftime("%Y-%m-%d")  # форматируем текущую дату
            # сохраняем цену в историю
            cur.execute(
                'REPLACE INTO price_history (product_id, date, price) VALUES (?, ?, ?)',
                (product["id"], today, product["price"])
            )
        self.conn.commit()  # фиксируем изменения

    def make_item(self, text, available=True, is_price=False):
        """
        Создаёт элемент таблицы с текстом и форматированием.
        Если товар недоступен, текст будет красным и курсивным.
        Если это цена, текст будет зелёным и жирным.
        """
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(Qt.AlignCenter)  # выравнивание по центру
        font = item.font()
        if not available:
            item.setForeground(QColor("#E57373"))  # красный цвет для недоступных
            font.setItalic(True)  # курсив для недоступных
        elif is_price:
            item.setForeground(QColor("#81C784"))  # зелёный цвет для цен
            font.setBold(True)  # жирный шрифт для цен
        item.setFont(font)
        item.setToolTip(str(text))  # подсказка при наведении
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)  # только для чтения
        return item

    def load_product_table(self):
        """
        Загружает данные о продуктах из БД и заполняет таблицу.
        """
        cur = self.conn.cursor()
        query = "SELECT id, name, brand, available FROM products"
        if self.hide_unavailable_checkbox.isChecked():
            query += " WHERE available = 1"
        else:
            query += " ORDER BY available DESC"
        cur.execute(query)  # выполняем запрос
        products = cur.fetchall()  # получаем все записи
        self.table.setRowCount(len(products))  # задаём количество строк

        for row, (pid, name, brand, available) in enumerate(products):
            # получаем последнюю цену и дату из истории
            cur.execute(
                'SELECT price, date FROM price_history WHERE product_id = ? ORDER BY date DESC LIMIT 1',
                (pid,)
            )
            price_date = cur.fetchone() or (None, "—")
            price, date = price_date

            # заполняем ячейки таблицы
            self.table.setItem(row, 0, self.make_item(pid, available))
            self.table.setItem(row, 1, self.make_item(name, available))
            self.table.setItem(row, 2, self.make_item(brand, available))
            price_text = price if price is not None else "Нет в наличии"
            self.table.setItem(row, 3, self.make_item(price_text, available, True))
            self.table.setItem(row, 4, self.make_item(date, available))

        # если есть товары, строим график для первого
        if products:
            self.plot_chart(products[0][0])

    def update_selected_product(self):
        """
        Обновляет информацию о выбранном товаре в таблице и БД.
        """
        row = self.table.currentRow()  # получаем выбранную строку
        if row < 0:
            QMessageBox.information(self, "Выбор строки", "Выберите товар в таблице")
            return
        pid = int(self.table.item(row, 0).text())  # артикул выбранного товара
        product = get_product_info(pid)  # запрашиваем данные
        if product:
            self.save_price(product)  # сохраняем в БД
            self.load_product_table()  # обновляем таблицу
            QMessageBox.information(self, "Обновлено", f"Товар {product['name']} обновлён.")

    def update_all_products(self):
        """
        Обновляет информацию по всем товарам из БД в фоновом потоке.
        """
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM products")
        ids = [r[0] for r in cur.fetchall()]  # список всех артикулов
        if not ids:
            QMessageBox.information(self, "Нет товаров", "Сначала добавьте артикулы")
            return

        self.table.setRowCount(len(ids))  # готовим таблицу к отображению процесса
        self.progress_bar.setValue(0)  # сбрасываем прогресс-бар
        self.progress_bar.show()  # показываем прогресс-бар

        # Создаём поток и воркер для обновления товаров
        self.worker_thread = QThread(self)
        self.worker = ProductUpdateWorker(ids)
        self.worker.moveToThread(self.worker_thread)
        self.worker.update_row.connect(self.handle_update_row)
        self.worker.show_error.connect(self.handle_show_error)
        self.worker.progress.connect(self.handle_progress)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.hide_progress_bar)
        self.worker.finished.connect(lambda: QMessageBox.information(self, "Готово", "Обновление завершено"))
        self.worker_thread.started.connect(self.worker.run)
        self.worker_thread.start()

    def handle_progress(self, percent):
        """
        Обновляет значение прогресса в прогресс-баре.
        """
        self.progress_bar.setValue(percent)

    def hide_progress_bar(self):
        """
        Скрывает прогресс-бар после завершения обновления.
        """
        self.progress_bar.hide()

    def handle_update_row(self, row, product):
        """
        Обрабатывает обновление данных по одному товару.
        Сохраняет в БД и обновляет соответствующую строку таблицы.
        """
        self.save_price(product)
        self.update_table_row(row, product)

    def handle_show_error(self, row):
        """
        Отображает текст 'Ошибка' в ячейке цены при неудаче получения данных.
        """
        self.table.setItem(row, 3, QTableWidgetItem("Ошибка"))

    def update_table_row(self, row, product):
        """
        Обновляет содержимое одной строки таблицы новым значением товара.
        """
        available = 1 if product["price"] is not None else 0
        self.table.setItem(row, 0, self.make_item(product["id"], available))
        self.table.setItem(row, 1, self.make_item(product["name"], available))
        self.table.setItem(row, 2, self.make_item(product["brand"], available))
        price_text = product["price"] if product["price"] is not None else "Нет в наличии"
        self.table.setItem(row, 3, self.make_item(price_text, available, True))
        date = datetime.now().strftime("%Y-%m-%d")  # текущая дата
        self.table.setItem(row, 4, self.make_item(date, available))

    def on_row_selected(self, row, col):
        """
        Вызывается при выборе строки: строит график для выбранного товара.
        """
        pid = int(self.table.item(row, 0).text())
        self.plot_chart(pid)

    def plot_chart(self, product_id):
        """
        Строит график изменения цены для указанного товара.
        """
        cur = self.conn.cursor()
        cur.execute(
            'SELECT date, price FROM price_history WHERE product_id = ? ORDER BY date',
            (product_id,)
        )
        rows = cur.fetchall()
        if not rows:
            # Очистить график, если нет данных
            self.ax.clear()
            # Повторно настроить фон и сетку (всё, как в __init__)
            self.figure.patch.set_facecolor("#FFFFFF")
            self.ax.set_facecolor("#F5F5F5")
            self.ax.grid(True, color="#DDDDDD", linestyle="-", linewidth=0.5)
            for spine in self.ax.spines.values():
                spine.set_color("#CCCCCC")
            self.canvas.draw_idle()
            return

        dates_raw, prices = zip(*rows)
        dates = [datetime.strptime(d, "%Y-%m-%d") for d in dates_raw]
        self._dates = dates_raw
        self._prices = prices

        # Вместо ax.plot — обновляем данные у существующей линии
        self.line.set_data(dates, prices)

        # Настроим оси (локатор и форматтер дат)
        self.ax.relim()  # пересчитаем границы по новым данным
        self.ax.autoscale_view()  # автоподгонка масштаба
        locator = mdates.AutoDateLocator()
        formatter = mdates.DateFormatter('%Y-%m-%d')
        self.ax.xaxis.set_major_locator(locator)
        self.ax.xaxis.set_major_formatter(formatter)

        # Подписи и сетка (если нужно, но обычно сетка уже есть из __init__)
        self.ax.set_title("История цены", color="#202020")
        self.ax.set_xlabel("Дата", color="#202020")
        self.ax.set_ylabel("Цена (руб.)", color="#202020")
        self.ax.tick_params(axis="x", labelrotation=45, colors="#202020")
        self.ax.tick_params(axis="y", colors="#202020")

        self.canvas.draw_idle()

    def show_tooltip(self, sel):
        """
        Отображает подсказку с датой и ценой при наведении на точку графика.
        """
        if not hasattr(self, "_dates") or not hasattr(self, "_prices"):
            sel.annotation.set_text("Нет данных")
            return
        index = int(sel.index)  # индекс выбранной точки
        if index >= len(self._dates):
            return
        sel.annotation.set_text(f"{self._dates[index]}\n{self._prices[index]} руб.")

if __name__ == "__main__":
    # Создание папки и базы данных по умолчанию при первом запуске
    os.makedirs("db", exist_ok=True)
    default_db_path = os.path.join("db", "prices.db")
    if not os.path.exists(default_db_path):
        conn = sqlite3.connect(default_db_path)
        cur = conn.cursor()
        # создаём таблицы, если их ещё нет
        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                name TEXT,
                brand TEXT,
                available INTEGER DEFAULT 1
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                product_id INTEGER,
                date TEXT,
                price INTEGER,
                PRIMARY KEY (product_id, date),
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)
        conn.commit()
        conn.close()

    # Запуск приложения Qt
    app = QApplication(sys.argv)
    # Загружаем стиль (QSS-файл) для тёмной темы
    with open(resource_path("light_material.qss"), "r", encoding="utf-8") as f:
        app.setStyleSheet(f.read())
    window = PriceTrackerApp()  # создаём главное окно
    window.show()  # отображаем окно
    sys.exit(app.exec_())  # запускаем главный цикл приложения
