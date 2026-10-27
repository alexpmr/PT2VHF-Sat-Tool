"""Single Qt binding per release: Qt 5/PySide2 for Win7, Qt 6/PySide6 for Win11.

Do not import both bindings into one interpreter. Runtime selection is based on
what the build installed, never on a guessed Windows version string.
"""
import sys

try:
    from PySide6.QtCore import Qt, QTimer, QObject, Signal, Slot, QUrl
    from PySide6.QtGui import QDoubleValidator, QFont, QIcon, QPixmap, QColor, QBrush
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QPushButton, QLineEdit, QComboBox, QGroupBox, QTabWidget,
        QPlainTextEdit, QSplitter, QMessageBox, QCheckBox, QTableWidget,
        QTableWidgetItem, QHeaderView, QDoubleSpinBox, QAbstractItemView, QProgressDialog, QScrollArea, QProgressBar, QFileDialog, QDialog,
    )
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtPositioning import QGeoPositionInfoSource
    QT_BINDING = "PySide6"
except ImportError as qt6_error:
    # Only a missing binding triggers the Qt5 fallback. Do not swallow
    # broken Qt6 native DLL loads, which should fail visibly during QA.
    if "No module named 'PySide6'" not in str(qt6_error):
        raise
    from PySide2.QtCore import Qt, QTimer, QObject, Signal, Slot, QUrl
    from PySide2.QtGui import QDoubleValidator, QFont, QIcon, QPixmap, QColor, QBrush
    from PySide2.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QPushButton, QLineEdit, QComboBox, QGroupBox, QTabWidget,
        QPlainTextEdit, QSplitter, QMessageBox, QCheckBox, QTableWidget,
        QTableWidgetItem, QHeaderView, QDoubleSpinBox, QAbstractItemView, QProgressDialog, QScrollArea, QProgressBar, QFileDialog, QDialog,
    )
    from PySide2.QtWebEngineWidgets import QWebEngineView
    from PySide2.QtPositioning import QGeoPositionInfoSource
    QT_BINDING = "PySide2"


def qt_exec(app):
    """Qt5 exposes exec_ and Qt6 exposes exec."""
    return app.exec_() if QT_BINDING == "PySide2" else app.exec()
