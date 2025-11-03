# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main_window.ui'
##
## Created by: Qt User Interface Compiler version 6.10.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QComboBox, QGridLayout, QHBoxLayout,
    QLineEdit, QMainWindow, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(739, 700)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.verticalLayout = QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.topBar1 = QWidget(self.centralwidget)
        self.topBar1.setObjectName(u"topBar1")
        self.topBar1.setAutoFillBackground(False)
        self.topBar1Layout = QHBoxLayout(self.topBar1)
        self.topBar1Layout.setObjectName(u"topBar1Layout")
        self.topBar1Layout.setContentsMargins(0, 0, 0, 0)
        self.btnThemeToggle = QPushButton(self.topBar1)
        self.btnThemeToggle.setObjectName(u"btnThemeToggle")

        self.topBar1Layout.addWidget(self.btnThemeToggle)

        self.btnReload = QPushButton(self.topBar1)
        self.btnReload.setObjectName(u"btnReload")

        self.topBar1Layout.addWidget(self.btnReload)

        self.btnImport = QPushButton(self.topBar1)
        self.btnImport.setObjectName(u"btnImport")

        self.topBar1Layout.addWidget(self.btnImport)

        self.btnAddModel = QPushButton(self.topBar1)
        self.btnAddModel.setObjectName(u"btnAddModel")

        self.topBar1Layout.addWidget(self.btnAddModel)


        self.verticalLayout.addWidget(self.topBar1)

        self.topBar2Layout = QHBoxLayout()
        self.topBar2Layout.setObjectName(u"topBar2Layout")
        self.searchBox = QLineEdit(self.centralwidget)
        self.searchBox.setObjectName(u"searchBox")

        self.topBar2Layout.addWidget(self.searchBox)

        self.sortDropdown = QComboBox(self.centralwidget)
        self.sortDropdown.addItem("")
        self.sortDropdown.addItem("")
        self.sortDropdown.addItem("")
        self.sortDropdown.addItem("")
        self.sortDropdown.addItem("")
        self.sortDropdown.setObjectName(u"sortDropdown")

        self.topBar2Layout.addWidget(self.sortDropdown)

        self.filterDropdown = QComboBox(self.centralwidget)
        self.filterDropdown.addItem("")
        self.filterDropdown.setObjectName(u"filterDropdown")

        self.topBar2Layout.addWidget(self.filterDropdown)


        self.verticalLayout.addLayout(self.topBar2Layout)

        self.scrollArea = QScrollArea(self.centralwidget)
        self.scrollArea.setObjectName(u"scrollArea")
        self.scrollArea.setWidgetResizable(True)
        self.scrollAreaWidgetContents = QWidget()
        self.scrollAreaWidgetContents.setObjectName(u"scrollAreaWidgetContents")
        self.scrollAreaWidgetContents.setGeometry(QRect(0, 0, 719, 616))
        self.galleryLayout = QGridLayout(self.scrollAreaWidgetContents)
        self.galleryLayout.setObjectName(u"galleryLayout")
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)

        self.verticalLayout.addWidget(self.scrollArea)

        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"zPrint", None))
        self.topBar1.setObjectName(QCoreApplication.translate("MainWindow", u"topBar1", None))
        self.btnThemeToggle.setText(QCoreApplication.translate("MainWindow", u"Theme", None))
        self.btnReload.setText(QCoreApplication.translate("MainWindow", u"Reload", None))
        self.btnImport.setText(QCoreApplication.translate("MainWindow", u"Import", None))
        self.btnAddModel.setText(QCoreApplication.translate("MainWindow", u"Add Model", None))
        self.searchBox.setPlaceholderText(QCoreApplication.translate("MainWindow", u"Search...", None))
        self.sortDropdown.setItemText(0, QCoreApplication.translate("MainWindow", u"Last viewed", None))
        self.sortDropdown.setItemText(1, QCoreApplication.translate("MainWindow", u"Last created", None))
        self.sortDropdown.setItemText(2, QCoreApplication.translate("MainWindow", u"Name A-Z", None))
        self.sortDropdown.setItemText(3, QCoreApplication.translate("MainWindow", u"Name Z-A", None))
        self.sortDropdown.setItemText(4, QCoreApplication.translate("MainWindow", u"Print Time", None))

        self.filterDropdown.setItemText(0, QCoreApplication.translate("MainWindow", u"All Materials", None))

    # retranslateUi

