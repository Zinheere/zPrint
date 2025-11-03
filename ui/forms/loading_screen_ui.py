# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'loading_screen.ui'
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
from PySide6.QtWidgets import (QApplication, QLabel, QProgressBar, QSizePolicy,
    QVBoxLayout, QWidget)

class Ui_LoadingScreen(object):
    def setupUi(self, LoadingScreen):
        if not LoadingScreen.objectName():
            LoadingScreen.setObjectName(u"LoadingScreen")
        LoadingScreen.resize(320, 240)
        LoadingScreen.setStyleSheet(u"background-color: transparent;")
        self.verticalLayout = QVBoxLayout(LoadingScreen)
        self.verticalLayout.setSpacing(16)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(32, 32, 32, 32)
        self.loadingLabel = QLabel(LoadingScreen)
        self.loadingLabel.setObjectName(u"loadingLabel")
        self.loadingLabel.setAlignment(Qt.AlignCenter)
        self.loadingLabel.setStyleSheet(u"color: #FFFFFF; font-size: 20px; font-weight: 600;")

        self.verticalLayout.addWidget(self.loadingLabel, 0, Qt.AlignHCenter|Qt.AlignVCenter)

        self.loadingProgress = QProgressBar(LoadingScreen)
        self.loadingProgress.setObjectName(u"loadingProgress")
        self.loadingProgress.setMinimum(0)
        self.loadingProgress.setMaximum(0)
        self.loadingProgress.setTextVisible(False)
        self.loadingProgress.setStyleSheet(u"QProgressBar {border: 1px solid rgba(255,255,255,90); border-radius: 10px; background: rgba(255,255,255,28); }\n"
"QProgressBar::chunk { background: rgba(255,255,255,190); border-radius: 10px; }")
        self.loadingProgress.setMinimumWidth(240)
        self.loadingProgress.setMaximumWidth(320)

        self.verticalLayout.addWidget(self.loadingProgress, 0, Qt.AlignHCenter)


        self.retranslateUi(LoadingScreen)

        QMetaObject.connectSlotsByName(LoadingScreen)
    # setupUi

    def retranslateUi(self, LoadingScreen):
        LoadingScreen.setWindowTitle(QCoreApplication.translate("LoadingScreen", u"Loading", None))
        self.loadingLabel.setText(QCoreApplication.translate("LoadingScreen", u"Loading\u2026", None))
    # retranslateUi

