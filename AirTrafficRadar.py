import sys
import requests
import vlc
import yt_dlp
from PyQt6.QtWidgets import QApplication, QMainWindow, QSplitter, QWidget, QVBoxLayout, QTextEdit, QSlider, QHBoxLayout, QComboBox, QLabel, QDialog, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QMessageBox, QFileDialog, QSizePolicy, QStackedWidget, QProgressBar
from PyQt6.QtCore import QUrl, QSettings, QByteArray, Qt, QTimer, QSize, QPoint, QThread, pyqtSignal, QPointF
from PyQt6.QtGui import QGuiApplication, QColor, QPixmap, QPainter, QPen
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings, QWebEngineScript, QWebEnginePage
import os
import json
from pathlib import Path
from PyQt6.QtGui import QMovie
import logging
import datetime

# Logger Setup
def setup_logger():
    """Richtet den Logger ein und räumt alte Logs auf"""
    log_dir = '_internal/logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # Alte Logs aufräumen (behalte nur die letzten 5)
    try:
        log_files = sorted([f for f in os.listdir(log_dir) if f.startswith('app_')])
        while len(log_files) >= 5:  # Behalte nur die 5 neuesten Dateien
            oldest_file = os.path.join(log_dir, log_files[0])
            os.remove(oldest_file)
            log_files = log_files[1:]
    except Exception as e:
        print(f"Fehler beim Aufräumen alter Logs: {e}")
        
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'app_{timestamp}.log')
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logging.info(f'Logger gestartet. Log-Datei: {log_file}')

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        if hasattr(sys, '_MEIPASS'):
            base_path = os.path.dirname(sys.executable)
            logging.debug(f"PyInstaller Modus - Base Path: {base_path}")
        else:
            base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
            logging.debug(f"Development Modus - Base Path: {base_path}")
            
        full_path = os.path.join(base_path, relative_path)
        logging.debug(f"Vollständiger Pfad: {full_path}")
        return full_path
    except Exception as e:
        logging.error(f"Fehler in resource_path: {e}")
        return relative_path

def check_image_exists(image_path):
    """Prüft ob ein Bild wirklich existiert"""
    logging.debug(f"\nPrüfe Bild: {image_path}")
    
    paths_to_check = []
    
    # App/Development Pfad
    if hasattr(sys, '_MEIPASS'):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        
    paths_to_check.append(os.path.join(app_dir, image_path))
    
    # Prüfe alle möglichen Pfade
    for path in paths_to_check:
        logging.debug(f"Prüfe Pfad: {path}")
        if os.path.exists(path):
            logging.debug(f"Bild gefunden in: {path}")
            return True
    
    logging.debug("Bild wurde in keinem Pfad gefunden")
    return False

# Speicherort für Cookies und LocalStorage
cookie_storage_path = os.path.join(os.path.expanduser("~"), ".adsb_storage")

METAR_URL = "http://tgftp.nws.noaa.gov/data/observations/metar/stations/KLAS.TXT"

class VolumeSlider(QSlider):
    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #999999;
                height: 4px;
                background: #4a4a4a;
                margin: 2px 0;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: white;
                border: 1px solid #999999;
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
            QSlider::sub-page:horizontal {
                background: #3498db;
                border-radius: 2px;
            }
        """)
        self.setMaximum(100)
        self.setMinimum(0)
        self.setValue(100)
        self.setFixedWidth(100)
        self.setContentsMargins(-10, 0, 0, 0)  # 10 Pixel nach links verschieben
        self.hide()

class MetarUpdater(QThread):
    metar_updated = pyqtSignal(str)  # Signal für neue METAR Daten
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self.url = METAR_URL
    
    def update_url(self, new_url):
        """Aktualisiert die METAR URL"""
        self.url = new_url
        # Sofort neue Daten abrufen
        try:
            response = requests.get(self.url, timeout=5)
            if response.ok:
                self.metar_updated.emit(response.text.strip())
        except Exception as e:
            self.metar_updated.emit(f"Fehler beim Abrufen der METAR-Daten: {e}")
    
    def run(self):
        while self.running:
            try:
                response = requests.get(self.url, timeout=5)
                if response.ok:
                    self.metar_updated.emit(response.text.strip())
            except Exception as e:
                self.metar_updated.emit(f"Fehler beim Abrufen der METAR-Daten: {e}")
            
            # Warte 15 Minuten
            for _ in range(15 * 60):  # 15 Minuten in Sekunden
                if not self.running:
                    break
                self.msleep(1000)  # 1 Sekunde schlafen

class StreamUpdater(QThread):
    stream_error = pyqtSignal(str)
    
    def __init__(self, vlc_widget, parent=None):
        super().__init__(parent)
        self.vlc_widget = vlc_widget
        self.current_url = None
        self.running = True
    
    def update_stream(self, url):
        """Aktualisiert die Stream-URL"""
        print(f"Starte Stream: {url}")
        self.current_url = url
        if not self.isRunning():
            self.start()
    
    def run(self):
        try:
            if not self.current_url:
                self.stream_error.emit("Keine Stream-URL angegeben")
                return
                
            ydl_opts = {
                'format': 'best',
                'quiet': True,
                'no_warnings': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(self.current_url, download=False)
                    if info.get("url"):
                        self.vlc_widget.play_url(info["url"])
                    else:
                        self.stream_error.emit("Keine Stream-URL gefunden")
                        
                except Exception as e:
                    self.stream_error.emit(f"Stream-Fehler: {str(e)}")
                    
        except Exception as e:
            self.stream_error.emit(str(e))
    
    def stop(self):
        """Stoppt den Thread"""
        self.running = False
        self.wait()

class LoadingSpinner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 40)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)
        self.timer.start(50)  # Aktualisiere alle 50ms
        
    def rotate(self):
        self.angle = (self.angle + 30) % 360
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Zentrum des Widgets
        center = QPointF(self.width() / 2, self.height() / 2)
        
        # Zeichne 8 Linien mit unterschiedlicher Opacity
        painter.setPen(QPen(QColor(180, 180, 180), 3, Qt.PenStyle.SolidLine))
        for i in range(8):
            opacity = 1.0 - (i * 0.8 / 8)
            painter.setOpacity(opacity)
            painter.save()
            painter.translate(center)
            painter.rotate(self.angle + (i * 45))
            painter.drawLine(0, 10, 0, 15)
            painter.restore()

class RadarApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AirTrafficRadar")
        self.setStyleSheet("""
            QMainWindow {
                background-color: #313131;
            }
            QWidget {
                background-color: #313131;
                color: white;
            }
            QComboBox {
                background-color: #444444;
                color: white;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 3px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border: none;
            }
            QPushButton {
                background-color: #444444;
                color: white;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QTextEdit {
                background-color: #1a1a1a;
                color: #0f0;
                border: 1px solid #444444;
            }
            QTableWidget {
                background-color: #313131;
                color: white;
                gridline-color: #444444;
                border: 1px solid #444444;
            }
            QTableWidget::item {
                background-color: #313131;
                color: white;
            }
            QTableWidget::item:selected {
                background-color: #444444;
            }
            QHeaderView::section {
                background-color: #444444;
                color: white;
                padding: 5px;
                border: 1px solid #555555;
            }
            QScrollBar {
                background-color: #313131;
            }
            QScrollBar::handle {
                background-color: #444444;
            }
            QLabel {
                color: white;
            }
            QSplitter::handle {
                background-color: #444444;
            }
        """)
        self.settings = QSettings('AirTrafficRadar', 'RadarApp')
        
        # Lade Flughafen-Konfiguration
        self.airports = self.load_airports()
        self.current_airport = None

        # Erstelle zuerst alle Splitter und Widgets
        self.hsplitter = QSplitter(Qt.Orientation.Horizontal)
        self.leftSplitter = QSplitter(Qt.Orientation.Vertical)

        # Toolbar Widget
        self.toolbarWidget = QWidget()
        toolbar_layout = QHBoxLayout(self.toolbarWidget)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(5)  # Kleiner Abstand zwischen den Elementen
        
        # Dropdown für Flughäfen
        self.dropdown = QComboBox()
        self.dropdown.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.dropdown.setMinimumWidth(400)
        self.dropdown.setStyleSheet("""
            QComboBox {
                background-color: #444444;
                color: white;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 3px;
            }
            QComboBox:disabled {
                background-color: #333333;
                color: #888888;
                border: 1px solid #444444;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border: none;
            }
        """)
        self.populate_airport_dropdown()
        self.dropdown.currentIndexChanged.connect(self.on_airport_changed)
        toolbar_layout.addWidget(self.dropdown)
        
        # Config Button
        config_button = QPushButton("Config")
        config_button.clicked.connect(self.show_config_dialog)
        config_button.setFixedWidth(60)  # Feste Breite für den Config Button
        toolbar_layout.addWidget(config_button)
        
        toolbar_layout.addStretch()  # Fügt Abstand am Ende hinzu
        
        # Volume Slider
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(50)  # Muss mit VLC Initial-Volume übereinstimmen
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        self.volume_slider.show()
        toolbar_layout.addWidget(self.volume_slider)
        
        # METAR Text
        self.metarText = QTextEdit()
        self.metarText.setMinimumHeight(60)  # Minimum Höhe für METAR
        self.metarText.setMinimumWidth(400)   # Minimum Breite für METAR
        self.metarText.setReadOnly(True)
        self.metarText.setStyleSheet("""
            background-color: #000;
            color: #0f0;
            font-family: monospace;
            padding: 10px;
            border: 2px solid #444;
            border-radius: 4px;
        """)

        # YouTube Livestream über VLC
        self.vlcWidget = VLCWidget()
        self.vlcWidget.setMinimumHeight(180)  # Minimum Höhe für VLC Widget (16:9 Verhältnis)
        self.vlcWidget.setMinimumWidth(400)   # Minimum Breite für VLC Widget
        
        # Linke Seite: Toolbar + Vertikaler Splitter
        left_container = QWidget()
        left_container.setMinimumWidth(400)  # Minimum Breite für linke Seite
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.toolbarWidget)
        
        # Vertikaler Splitter für METAR und VLC
        self.leftSplitter.addWidget(self.metarText)
        self.leftSplitter.addWidget(self.vlcWidget)
        left_layout.addWidget(self.leftSplitter)
        
        # Splitter-Einstellungen für beide Splitter
        for splitter in [self.hsplitter, self.leftSplitter]:
            splitter.setHandleWidth(8)  # Breiterer Griff zum Anfassen
            splitter.setChildrenCollapsible(False)  # Verhindert komplettes Zusammenklappen
            splitter.setStyleSheet("""
                QSplitter::handle {
                    background-color: #444;
                    border-radius: 2px;
                    margin: 2px;
                }
                QSplitter::handle:hover {
                    background-color: #666;
                }
                QSplitter::handle:pressed {
                    background-color: #888;
                }
            """)
        
        self.hsplitter.addWidget(left_container)
        
        # ADSB View (rechte Seite)
        self.adsbView = QWebEngineView()
        self.adsbView.setMinimumWidth(600)  # Minimum Breite für ADSB View
        self.configure_adsb_browser()
        self.adsbView.setUrl(QUrl("https://globe.adsbexchange.com/"))
        self.hsplitter.addWidget(self.adsbView)

        # Fensterlayout
        container = QWidget()
        container.setMinimumSize(1000, 600)  # Minimum Größe für Hauptfenster
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self.hsplitter)
        self.setCentralWidget(container)

        # Lade die gespeicherten Einstellungen erst NACH der Widget-Initialisierung
        self.loadSettings()

        # Verzögere den Start des Streams bis die GUI geladen ist
        QTimer.singleShot(500, self.initialize_last_airport)

        # METAR Updater initialisieren
        self.metar_updater = MetarUpdater(self)
        self.metar_updater.metar_updated.connect(self.update_metar_text)
        self.metar_updater.start()
        
        # Stream Updater initialisieren
        self.stream_updater = StreamUpdater(self.vlcWidget, self)
        self.stream_updater.stream_error.connect(self.handle_stream_error)

        # Start YouTube Stream
        self.start_youtube_stream()

        # Splitter-Änderungen überwachen
        self.hsplitter.splitterMoved.connect(self.saveSplitterSizes)
        self.leftSplitter.splitterMoved.connect(self.saveSplitterSizes)

        self.airport_change_in_progress = False  # Neue Variable für die Sperre

    def loadSettings(self):
        """Lädt alle gespeicherten Einstellungen."""
        # Fenstergeometrie laden
        if self.settings.contains("windowGeometry"):
            geometry = self.settings.value("windowGeometry")
            if isinstance(geometry, QByteArray):
                self.restoreGeometry(geometry)
            else:
                self.restoreGeometry(QByteArray(geometry))
        else:
            # Standardgröße nur wenn keine Einstellungen vorhanden
            self.resize(1280, 720)

        # Splitter-Größen laden
        hsizes = self.settings.value("hsplitter_sizes")
        if hsizes:
            try:
                if isinstance(hsizes, str):
                    import ast
                    hsizes = ast.literal_eval(hsizes)
                hsizes = [int(x) for x in hsizes]
                if all(size > 0 for size in hsizes):  # Prüfe auf gültige Größen
                    self.hsplitter.setSizes(hsizes)
            except:
                print("Fehler beim Laden der horizontalen Splitter-Größen")

        vsizes = self.settings.value("vsplitter_sizes")
        if vsizes:
            try:
                if isinstance(vsizes, str):
                    import ast
                    vsizes = ast.literal_eval(vsizes)
                vsizes = [int(x) for x in vsizes]
                if all(size > 0 for size in vsizes):  # Prüfe auf gültige Größen
                    self.leftSplitter.setSizes(vsizes)
            except:
                print("Fehler beim Laden der vertikalen Splitter-Größen")

        # Warte kurz und stelle dann sicher, dass die Splitter-Größen korrekt sind
        QTimer.singleShot(100, self.validateSplitterSizes)

    def validateSplitterSizes(self):
        """Überprüft und korrigiert die Splitter-Größen falls nötig."""
        if sum(self.hsplitter.sizes()) == 0:
            self.hsplitter.setSizes([400, 800])
        if sum(self.leftSplitter.sizes()) == 0:
            self.leftSplitter.setSizes([300, 300])

    def saveSplitterSizes(self):
        """Speichert die aktuellen Splitter-Größen."""
        # Listen explizit als Integer-Listen speichern
        self.settings.setValue("hsplitter_sizes", [int(x) for x in self.hsplitter.sizes()])
        self.settings.setValue("vsplitter_sizes", [int(x) for x in self.leftSplitter.sizes()])
        self.settings.sync()
        print("Splitter sizes saved:", self.hsplitter.sizes(), self.leftSplitter.sizes())

    def configure_adsb_browser(self):
        """Konfiguriert den Browser speziell für ADSB Exchange"""
        # Erstelle ein persistentes Profil
        app_dir = os.path.dirname(os.path.abspath(__file__))
        profile_path = os.path.join(app_dir, "browser_profile")
        
        # Erstelle ein benanntes, persistentes Profil
        profile = QWebEngineProfile("adsb_profile", self.adsbView)
        profile.setPersistentStoragePath(profile_path)
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
        
        # Erstelle eine neue Page mit dem Profil
        page = QWebEnginePage(profile, self.adsbView)
        self.adsbView.setPage(page)
        
        # Konfiguriere die Seiten-Einstellungen
        settings = page.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        
        # Verbinde Signal für neue Fenster
        page.newWindowRequested.connect(self.handle_new_window)

    def handle_new_window(self, request):
        """Behandelt neue Fenster-Anfragen"""
        # Öffne die URL im gleichen Fenster
        self.adsbView.setUrl(request.requestedUrl())

    def update_metar_text(self, text):
        """Aktualisiert den METAR Text in der GUI"""
        self.metarText.setPlainText(text)

    def handle_stream_error(self, error):
        """Behandelt Stream-Fehler"""
        print(f"Stream-Fehler: {error}")
        if self.current_airport and self.current_airport.get("image"):
            self.vlcWidget.show_image(self.current_airport["image"])
        else:
            self.vlcWidget.show_no_stream_message()

    def start_youtube_stream(self):
        """Lädt den YouTube-Livestream über VLC."""
        ydl_opts = {'format': 'best', 'quiet': True, 'no_warnings': True}
        stream_url = None
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info("https://www.youtube.com/watch?v=d5PtT7KdlKc", download=False)
                stream_url = info.get("url")
        except Exception as e:
            print(f"Fehler beim Extrahieren der YouTube-URL: {e}")

        if stream_url:
            self.vlcWidget.play_url(stream_url)
        else:
            self.vlcWidget.stop()

    def closeEvent(self, event):
        """Speichert alle Einstellungen beim Beenden."""
        self.settings.setValue("windowGeometry", self.saveGeometry())
        self.saveSplitterSizes()
        self.settings.sync()
        # Stoppe alle Threads
        self.metar_updater.running = False
        self.metar_updater.wait()
        self.stream_updater.stop()  # Neuer sauberer Stop
        event.accept()

    def load_airports(self):
        """Lädt die Flughafen-Konfiguration aus der JSON-Datei"""
        config_path = Path(__file__).parent / "airports.json"
        print(f"Versuche airports.json zu laden von: {config_path}")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                airports = data.get("airports", [])
                print(f"Geladene Flughäfen: {len(airports)}")
                return airports
        except Exception as e:
            print(f"Fehler beim Laden der Flughafen-Konfiguration: {e}")
            return []

    def populate_airport_dropdown(self):
        """Füllt das Dropdown-Menü mit den Flughäfen"""
        self.dropdown.clear()
        print(f"Fülle Dropdown mit {len(self.airports)} Flughäfen")
        for airport in self.airports:
            self.dropdown.addItem(airport["label"])
        print(f"Dropdown hat jetzt {self.dropdown.count()} Einträge")

    def on_airport_changed(self, index):
        """Wird aufgerufen, wenn ein anderer Flughafen ausgewählt wird"""
        if self.airport_change_in_progress:
            return
            
        if index < 0 or index >= len(self.airports):
            return
            
        try:
            self.airport_change_in_progress = True
            self.dropdown.setEnabled(False)
            
            # Sofort alles bereinigen
            self.vlcWidget.clear_all()
            
            self.current_airport = self.airports[index]
            print(f"Flughafen gewechselt zu: {self.current_airport['label']}")
            
            # Speichere ausgewählten Flughafen
            self.settings.setValue("last_airport", self.current_airport["label"])
            self.settings.sync()
            
            # Erstelle einen neuen Timer für die Update-Sequenz
            QTimer.singleShot(100, lambda: self.execute_airport_update(index))
            
        except Exception as e:
            print(f"Fehler beim Flughafen-Wechsel: {e}")
            self.enable_airport_selection()

    def execute_airport_update(self, index):
        """Führt die Airport-Updates sequenziell aus"""
        try:
            # 1. METAR Update
            METAR_URL = f"http://tgftp.nws.noaa.gov/data/observations/metar/stations/{self.current_airport['icao']}.TXT"
            self.metar_updater.update_url(METAR_URL)
            
            # 2. Karte aktualisieren
            lat = self.current_airport['coordinates']['lat']
            lon = self.current_airport['coordinates']['lon']
            new_url = f"https://globe.adsbexchange.com/?lat={lat}&lon={lon}&zoom=12"
            self.adsbView.setUrl(QUrl(new_url))
            
            # 3. Livestream aktualisieren (verzögert)
            QTimer.singleShot(500, lambda: self.update_livestream(self.current_airport))
            
            # 4. UI wieder aktivieren (verzögert)
            QTimer.singleShot(2000, self.enable_airport_selection)
            
        except Exception as e:
            print(f"Fehler bei Airport-Update-Sequenz: {e}")
            self.enable_airport_selection()

    def enable_airport_selection(self):
        """Aktiviert die Flughafen-Auswahl wieder"""
        try:
            self.airport_change_in_progress = False
            self.dropdown.setEnabled(True)
        except Exception as e:
            print(f"Fehler beim Aktivieren der Flughafen-Auswahl: {e}")

    def update_livestream(self, airport):
        """Aktualisiert den Livestream basierend auf dem ausgewählten Flughafen"""
        try:
            if airport.get("livestream"):
                print(f"Starte Livestream für: {airport['label']}")
                self.vlcWidget.play_url(airport["livestream"])
            elif airport.get("image"):
                self.vlcWidget.show_image(airport["image"])
            else:
                self.vlcWidget.show_no_stream_message()
        except Exception as e:
            print(f"Fehler beim Livestream-Update: {e}")
            self.vlcWidget.show_no_stream_message()

    def initialize_last_airport(self):
        """Initialisiert den letzten ausgewählten Flughafen nach dem GUI-Start"""
        last_airport = self.settings.value("last_airport")
        if last_airport:
            index = self.dropdown.findText(last_airport)
            if index >= 0:
                print(f"Setze letzten Flughafen: {last_airport}")
                self.dropdown.setCurrentIndex(index)
                # Wichtig: Explizit den Change-Handler aufrufen
                QTimer.singleShot(100, lambda: self.on_airport_changed(index))
        else:
            # Falls kein letzter Flughafen gespeichert wurde, nehme den ersten aus der Liste
            if self.dropdown.count() > 0:
                self.dropdown.setCurrentIndex(0)
                # Auch hier den Change-Handler verzögert aufrufen
                QTimer.singleShot(100, lambda: self.on_airport_changed(0))

    def show_config_dialog(self):
        """Zeigt den Konfigurations-Dialog"""
        dialog = ConfigDialog(self.airports, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Neu laden der Flughäfen
            self.airports = self.load_airports()
            self.populate_airport_dropdown()
            # Setze den aktuellen Flughafen zurück, falls er noch existiert
            if self.current_airport:
                index = self.dropdown.findText(self.current_airport["label"])
                if index >= 0:
                    self.dropdown.setCurrentIndex(index)

    def center_map_on_airport(self, airport):
        """Zentriert die ADSB-Exchange Karte auf den Flughafen"""
        # Baue die neue URL
        lat = airport['coordinates']['lat']
        lon = airport['coordinates']['lon']
        new_url = f"https://globe.adsbexchange.com/?lat={lat}&lon={lon}&zoom=12"
        
        # Prüfe ob die aktuelle URL anders ist als die neue URL
        current_url = self.adsbView.url().toString()
        if current_url != new_url:
            print(f"Zentriere Karte auf: {airport['label']} bei {lat}, {lon}")
            
            def handle_load_finished(ok):
                try:
                    # Versuche den Handler zu entfernen, fange Fehler ab wenn nicht verbunden
                    self.adsbView.loadFinished.disconnect(handle_load_finished)
                except TypeError:
                    pass  # Ignoriere Fehler wenn Handler nicht verbunden war
                
                if not ok:
                    print(f"Fehler beim Laden der Karte für: {airport['label']}")
            
            # Setze Timeout für die Navigation
            QTimer.singleShot(10000, lambda: handle_load_finished(False))
            self.adsbView.loadFinished.connect(handle_load_finished)
            self.adsbView.setUrl(QUrl(new_url))

    def show_adsb_login(self):
        """Öffnet das ADSB Exchange Login-Fenster in einem externen Browser"""
        import webbrowser
        
        # Öffne Login-Seite im Standard-Browser
        webbrowser.open("https://account.adsbexchange.com/")
        
        # Zeige Hinweis-Dialog
        QMessageBox.information(
            self,
            "ADSB Exchange Login",
            "Die Login-Seite wurde in Ihrem Browser geöffnet.\n\n"
            "1. Bitte loggen Sie sich dort ein\n"
            "2. Schließen Sie den Browser-Tab\n"
            "3. Klicken Sie hier auf OK\n"
            "4. Die App prüft dann den Login-Status"
        )
        
        # Prüfe nach kurzer Verzögerung den Login-Status mehrmals
        for delay in [3000, 6000, 9000]:  # Prüfe nach 3, 6 und 9 Sekunden
            QTimer.singleShot(delay, self.check_adsb_login_status)

    def check_adsb_login_status(self):
        """Prüft den ADSB Exchange Login-Status durch Prüfen der Account-Seite"""
        # Speichere aktuelle URL
        current_url = self.adsbView.url()
        
        def check_account_page(ok):
            # Entferne den Handler sofort nach dem ersten Aufruf
            self.adsbView.loadFinished.disconnect(check_account_page)
            
            if not ok:
                print("Konnte Account-Seite nicht laden")
                return
            
            check_script = """
            (function() {
                // Prüfe ob ein Login-Formular existiert
                const loginForm = document.querySelector('form[action*="login"]') || 
                                document.querySelector('input[type="password"]');
                
                // Wenn ein Login-Formular existiert, sind wir nicht eingeloggt
                const isLoggedIn = !loginForm;
                console.log('Login form found:', !!loginForm);
                console.log('Is logged in:', isLoggedIn);
                
                return isLoggedIn;
            })();
            """
            
            def handle_check(is_logged_in):
                if is_logged_in:
                    print("Login erfolgreich!")
                    self.adsb_login_button.setText("Logged In")
                    self.adsb_login_button.setStyleSheet("background-color: #4CAF50; color: white;")
                else:
                    print("Nicht eingeloggt")
                    self.adsb_login_button.setText("Login")
                    self.adsb_login_button.setStyleSheet("")
                
                # Zurück zur vorherigen Seite
                self.adsbView.setUrl(current_url)
            
            self.adsbView.page().runJavaScript(check_script, handle_check)
        
        # Lade Account-Seite und prüfe Status
        self.adsbView.loadFinished.connect(check_account_page)
        self.adsbView.setUrl(QUrl("https://account.adsbexchange.com/account"))

    def on_volume_changed(self, volume):
        """Wird aufgerufen, wenn die Lautstärke geändert wird"""
        self.vlcWidget.set_volume(volume)

class VLCWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Grundlegende Attribute initialisieren
        self.instance = None
        self.mediaplayer = None
        self.current_volume = 50
        self.is_loading = False
        
        # Layout erstellen
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Stack-Widget für Video und Labels
        self.stack = QStackedWidget(self)
        self.layout.addWidget(self.stack)
        
        # Video-Container
        self.video_container = QWidget()
        self.video_container.setStyleSheet("background-color: black;")
        self.video_container.setMinimumSize(320, 180)
        self.stack.addWidget(self.video_container)

        # "Kein Livestream" Container
        self.no_stream_container = QWidget()
        self.no_stream_container.setStyleSheet("background-color: black;")
        no_stream_layout = QVBoxLayout(self.no_stream_container)
        self.no_stream_label = QLabel("Kein Livestream verfügbar")
        self.no_stream_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_stream_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 16px;
                padding: 20px;
            }
        """)
        no_stream_layout.addWidget(self.no_stream_label)
        self.stack.addWidget(self.no_stream_container)

        # Loading Container
        self.loading_container = QWidget()
        self.loading_container.setStyleSheet("background-color: black;")
        loading_layout = QVBoxLayout(self.loading_container)
        
        # Loading Spinner
        self.spinner = LoadingSpinner()
        loading_layout.addWidget(self.spinner, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Loading Label
        self.loading_label = QLabel("Lade Stream...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet("""
            QLabel {
                color: #b4b4b4;
                font-size: 14px;
                margin-top: 10px;
            }
        """)
        loading_layout.addWidget(self.loading_label)
        
        # Zentriere die Loading-Elemente
        loading_layout.addStretch()
        loading_layout.insertStretch(0)
        
        self.stack.addWidget(self.loading_container)

        # Image Container
        self.image_container = QWidget()
        self.image_container.setStyleSheet("background-color: black;")
        image_layout = QVBoxLayout(self.image_container)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: black;")
        image_layout.addWidget(self.image_label)
        self.stack.addWidget(self.image_container)

    def show_loading(self):
        """Zeigt die Ladeanimation"""
        print("Zeige Ladeanimation")
        self.stack.setCurrentWidget(self.loading_container)
        self.spinner.timer.start()

    def hide_loading(self):
        """Versteckt die Ladeanimation"""
        self.spinner.timer.stop()
        if self.stack.currentWidget() == self.loading_container:
            self.stack.setCurrentWidget(self.video_container)

    def initialize_vlc(self):
        """Initialisiert VLC komplett neu"""
        try:
            self.cleanup_vlc()
            
            self.instance = vlc.Instance('--quiet')
            if not self.instance:
                raise Exception("VLC Instance konnte nicht erstellt werden")
            
            self.mediaplayer = self.instance.media_player_new()
            if not self.mediaplayer:
                raise Exception("VLC Media Player konnte nicht erstellt werden")
            
            self.mediaplayer.audio_set_volume(self.current_volume)
            return True
            
        except Exception as e:
            print(f"Fehler bei VLC-Initialisierung: {e}")
            self.cleanup_vlc()
            return False

    def cleanup_vlc(self):
        """Beendet VLC komplett"""
        try:
            if self.mediaplayer:
                self.mediaplayer.stop()
                self.mediaplayer.release()
                self.mediaplayer = None
            if self.instance:
                self.instance.release()
                self.instance = None
        except Exception as e:
            print(f"Fehler beim VLC Cleanup: {e}")
            self.mediaplayer = None
            self.instance = None

    def set_volume(self, volume):
        """Setzt die Lautstärke sicher"""
        try:
            self.current_volume = volume
            if self.mediaplayer:
                self.mediaplayer.audio_set_volume(volume)
        except Exception as e:
            print(f"Fehler beim Setzen der Lautstärke: {e}")

    def show_no_stream_message(self):
        """Zeigt die 'Kein Stream' Nachricht"""
        print("Zeige 'Kein Stream verfügbar' Nachricht")
        self.cleanup_vlc()
        self.stack.setCurrentWidget(self.no_stream_container)
        self.no_stream_container.show()
        self.no_stream_label.show()

    def play_url(self, url):
        """Spielt eine URL ab"""
        if not url:
            self.show_no_stream_message()
            return

        try:
            print(f"Starte Stream: {url}")
            self.show_loading()  # Zeige Ladeanimation
            
            # YouTube URL zu direktem Stream konvertieren
            if 'youtube.com' in url or 'youtu.be' in url:
                try:
                    from yt_dlp import YoutubeDL
                    ydl_opts = {
                        'format': 'best',
                        'quiet': True,
                    }
                    with YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        url = info['url']
                except Exception as e:
                    print(f"Fehler bei YouTube-URL Extraktion: {e}")
                    self.hide_loading()
                    self.show_no_stream_message()
                    return
            
            # Stelle sicher dass VLC läuft
            if not self.initialize_vlc():
                self.hide_loading()
                self.show_no_stream_message()
                return
            
            # Zeige Video-Container
            self.hide_loading()
            self.stack.setCurrentWidget(self.video_container)
            
            # Media erstellen
            media = self.instance.media_new(url)
            self.mediaplayer.set_media(media)
            
            # Window Handle setzen
            if sys.platform == "win32":
                self.mediaplayer.set_hwnd(int(self.video_container.winId()))
            elif sys.platform.startswith('linux'):
                self.mediaplayer.set_xwindow(self.video_container.winId())
            elif sys.platform == "darwin":
                self.mediaplayer.set_nsobject(int(self.video_container.winId()))
            
            # Abspielen
            if self.mediaplayer.play() == -1:
                print("Fehler beim Starten des Streams")
                self.show_no_stream_message()
                return
            
        except Exception as e:
            print(f"Fehler beim Stream-Start: {e}")
            self.hide_loading()
            self.show_no_stream_message()

    def stop(self):
        """Stoppt die Wiedergabe"""
        self.cleanup_vlc()
        self.show_no_stream_message()

    def clear_all(self):
        """Bereinigt die Anzeige sofort"""
        print("Bereinige Anzeige")
        self.cleanup_vlc()
        self.hide_loading()
        self.show_loading()  # Zeige Ladeanimation während des Wechsels

    def show_image(self, image_path):
        """Zeigt ein Bild an"""
        print(f"\nVersuche Bild zu zeigen: {image_path}")
        try:
            if image_path and check_image_exists(image_path):
                print(f"Bild existiert, lade: {image_path}")
                pixmap = QPixmap(resource_path(image_path))
                # Skaliere das Bild proportional auf die Widget-Größe
                scaled_pixmap = pixmap.scaled(
                    self.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                print(f"Bild geladen: {not pixmap.isNull()}")
                self.image_label.setPixmap(scaled_pixmap)
                self.stack.setCurrentWidget(self.image_container)
            else:
                print(f"Bild nicht gefunden: {image_path}")
                self.show_no_stream_message()
        except Exception as e:
            print(f"Fehler beim Laden des Bildes: {e}")
            self.show_no_stream_message()

    def handle_stream_error(self, error):
        """Behandelt Stream-Fehler"""
        print(f"Stream-Fehler: {error}")
        if self.current_airport and self.current_airport.get("image"):
            self.show_image(self.current_airport["image"])
        else:
            self.show_no_stream_message()

class ConfigDialog(QDialog):
    def __init__(self, airports, parent=None):
        super().__init__(parent)
        self.airports = airports
        self.setWindowTitle("Airport Konfiguration")
        self.setMinimumSize(800, 400)
        
        layout = QVBoxLayout(self)
        
        # Tabelle erstellen
        self.table = QTableWidget()
        self.table.setColumnCount(5)  # Eine zusätzliche Spalte für Bilder
        
        # Fette Überschriften
        headers = ["Label", "Latitude", "Longitude", "Livestream URL", "Fallback Bild"]
        bold_headers = []
        for header in headers:
            item = QTableWidgetItem(header)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            bold_headers.append(item)
        
        self.table.setHorizontalHeaderLabels(headers)
        
        # Spaltenbreiten
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Label
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)    # Lat
        self.table.setColumnWidth(1, 100)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)    # Lon
        self.table.setColumnWidth(2, 100)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # URL
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)    # Bild
        self.table.setColumnWidth(4, 100)
        
        layout.addWidget(self.table)
        
        # Buttons
        button_layout = QHBoxLayout()
        add_button = QPushButton("Hinzufügen")
        remove_button = QPushButton("Entfernen")
        save_button = QPushButton("Speichern")
        
        add_button.clicked.connect(self.add_row)
        remove_button.clicked.connect(self.remove_row)
        save_button.clicked.connect(self.save_config)
        
        button_layout.addWidget(add_button)
        button_layout.addWidget(remove_button)
        button_layout.addWidget(save_button)
        layout.addLayout(button_layout)
        
        # Liste für zu löschende Bilder
        self.images_to_delete = set()

        self.load_data()

    def load_data(self):
        """Lädt die Flughafen-Daten in die Tabelle"""
        self.table.setRowCount(len(self.airports))
        for i, airport in enumerate(self.airports):
            # Label (nur Text)
            label_item = QTableWidgetItem(airport["label"])
            self.table.setItem(i, 0, label_item)
            
            # Koordinaten
            self.table.setItem(i, 1, QTableWidgetItem(str(airport["coordinates"]["lat"])))
            self.table.setItem(i, 2, QTableWidgetItem(str(airport["coordinates"]["lon"])))
            
            # Livestream URL
            stream_url = airport.get("livestream", "")
            self.table.setItem(i, 3, QTableWidgetItem(stream_url))
            
            # Container für Bild-Buttons
            button_container = QWidget()
            button_layout = QHBoxLayout(button_container)
            button_layout.setContentsMargins(2, 2, 2, 2)
            button_layout.setSpacing(2)
            
            # Bild-Button
            button = QPushButton("Bild wählen")
            if airport.get("image"):
                if check_image_exists(airport["image"]):
                    button.setText("Bild gewählt")
                    button.setToolTip(airport["image"])
                else:
                    button.setText("Bild wählen")
                    button.setToolTip("")
            button.clicked.connect(lambda checked, row=i: self.choose_image(row))
            button_layout.addWidget(button)
            
            # Entfernen-Button
            remove_button = QPushButton("×")
            remove_button.setFixedSize(20, 20)
            remove_button.setStyleSheet("""
                QPushButton {
                    color: white;
                    background-color: #d32f2f;
                    border-radius: 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #b71c1c;
                }
            """)
            remove_button.clicked.connect(lambda checked, row=i: self.remove_image(row))
            if not airport.get("image") or not os.path.exists(resource_path(airport["image"])):
                remove_button.hide()
            button_layout.addWidget(remove_button)
            
            button_layout.addStretch()
            self.table.setCellWidget(i, 4, button_container)

    def remove_image(self, row):
        """Markiert ein Bild zum Löschen"""
        button_container = self.table.cellWidget(row, 4)
        if button_container:
            button = button_container.layout().itemAt(0).widget()
            remove_button = button_container.layout().itemAt(1).widget()
            
            # Hole den Bildpfad und merke ihn zum späteren Löschen vor
            image_path = button.toolTip()
            if image_path:
                # Konstruiere den vollen Pfad zur Datei
                full_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), image_path)
                self.images_to_delete.add(full_path)
            
            # Nur UI zurücksetzen
            button.setText("Bild wählen")
            button.setToolTip("")
            remove_button.hide()

    def choose_image(self, row):
        """Öffnet einen Datei-Dialog zum Auswählen eines Bildes"""
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Bild auswählen", "", 
            "Bilder (*.png *.jpg *.jpeg *.bmp);;Alle Dateien (*.*)"
        )
        if file_name:
            try:
                # Erstelle _internal/images-Ordner im selben Verzeichnis wie die EXE/Script
                app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
                images_dir = os.path.join(app_dir, '_internal', 'images')
                if not os.path.exists(images_dir):
                    os.makedirs(images_dir)
                
                # Kopiere das Bild
                base_name = os.path.basename(file_name)
                new_path = os.path.join(images_dir, base_name)
                import shutil
                shutil.copy2(file_name, new_path)
                
                # Speichere relativen Pfad
                rel_path = os.path.join("_internal", "images", base_name)
                
                # Aktualisiere Buttons
                button_container = self.table.cellWidget(row, 4)
                if button_container:
                    button = button_container.layout().itemAt(0).widget()
                    remove_button = button_container.layout().itemAt(1).widget()
                    button.setText("Bild gewählt")
                    button.setToolTip(rel_path)  # Speichere relativen Pfad
                    remove_button.show()
                
            except Exception as e:
                QMessageBox.critical(self, "Fehler", f"Fehler beim Speichern des Bildes: {str(e)}")

    def add_image_button(self, row):
        """Fügt einen Bild-Button zu einer Zeile hinzu"""
        # Container für Bild-Buttons
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(2, 2, 2, 2)
        button_layout.setSpacing(2)
        
        # Bild-Button
        button = QPushButton("Bild wählen")
        button.clicked.connect(lambda checked, row=row: self.choose_image(row))
        button_layout.addWidget(button)
        
        # Entfernen-Button
        remove_button = QPushButton("×")
        remove_button.setFixedSize(20, 20)
        remove_button.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #d32f2f;
                border-radius: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #b71c1c;
            }
        """)
        remove_button.clicked.connect(lambda checked, row=row: self.remove_image(row))
        remove_button.hide()  # Initial versteckt
        button_layout.addWidget(remove_button)
        
        button_layout.addStretch()
        self.table.setCellWidget(row, 4, button_container)

    def add_row(self):
        """Fügt eine neue leere Zeile hinzu"""
        row_position = self.table.rowCount()
        self.table.insertRow(row_position)
        
        # Leere Zellen für die ersten 4 Spalten
        for col in range(4):
            self.table.setItem(row_position, col, QTableWidgetItem(""))
            
        # Bild-Button in der letzten Spalte
        self.add_image_button(row_position)

    def remove_row(self):
        """Entfernt die ausgewählte Zeile"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)

    def save_config(self):
        """Speichert die Konfiguration und löscht markierte Bilder"""
        try:
            # Erst Konfiguration speichern
            new_airports = []
            for row in range(self.table.rowCount()):
                # Prüfe ob alle notwendigen Felder existieren und nicht leer sind
                label_item = self.table.item(row, 0)
                lat_item = self.table.item(row, 1)
                lon_item = self.table.item(row, 2)
                stream_item = self.table.item(row, 3)
                
                # Überspringe Zeile wenn Label fehlt oder leer ist
                if not label_item or not label_item.text().strip():
                    continue
                    
                # Überspringe Zeile wenn Koordinaten fehlen oder ungültig sind
                if not lat_item or not lon_item:
                    continue
                    
                try:
                    lat = float(lat_item.text().strip())
                    lon = float(lon_item.text().strip())
                except ValueError:
                    continue
                
                # Hole den Button aus dem Container für den Image-Pfad
                button_container = self.table.cellWidget(row, 4)
                image_path = None
                if button_container:
                    button = button_container.layout().itemAt(0).widget()
                    if button.text() == "Bild gewählt":
                        image_path = button.toolTip()
                
                airport = {
                    "label": label_item.text().strip(),
                    "icao": label_item.text().split('-')[0].strip(),
                    "coordinates": {
                        "lat": lat,
                        "lon": lon
                    },
                    "livestream": stream_item.text().strip() if stream_item and stream_item.text() else None,
                    "image": image_path
                }
                new_airports.append(airport)
            
            # Speichere in JSON
            config_path = Path(__file__).parent / "airports.json"
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump({"airports": new_airports}, f, indent=4)
            
            # Jetzt die markierten Bilder löschen
            for image_path in self.images_to_delete:
                try:
                    if os.path.exists(image_path):
                        os.remove(image_path)
                        print(f"Bild gelöscht: {image_path}")
                except Exception as e:
                    print(f"Fehler beim Löschen des Bildes {image_path}: {e}")
            
            QMessageBox.information(self, "Erfolg", "Konfiguration wurde gespeichert!")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Fehler beim Speichern: {str(e)}")

def main():
    setup_logger()  # Logger initialisieren
    app = QApplication(sys.argv)
    
    # Globaler Exception Handler
    def handle_exception(exc_type, exc_value, exc_traceback):
        logging.error("Unbehandelte Exception:", exc_info=(exc_type, exc_value, exc_traceback))
        QMessageBox.critical(None, "Fehler",
                           f"Ein unerwarteter Fehler ist aufgetreten:\n{exc_value}")
    
    sys.excepthook = handle_exception
    
    window = RadarApp()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
