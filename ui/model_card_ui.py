# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'model_card.ui'
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
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget)

class Ui_ModelCard(object):
    def setupUi(self, modelCardTemplate):
        if not modelCardTemplate.objectName():
            modelCardTemplate.setObjectName(u"modelCardTemplate")
        modelCardTemplate.setMinimumSize(QSize(200, 220))
        self.verticalLayout = QVBoxLayout(modelCardTemplate)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.thumbnailLabel = QLabel(modelCardTemplate)
        self.thumbnailLabel.setObjectName(u"thumbnailLabel")
        self.thumbnailLabel.setMinimumSize(QSize(150, 150))
        self.thumbnailLabel.setAlignment(Qt.AlignCenter)

        self.verticalLayout.addWidget(self.thumbnailLabel)

        self.nameLabel = QLabel(modelCardTemplate)
        self.nameLabel.setObjectName(u"nameLabel")

        self.verticalLayout.addWidget(self.nameLabel)

        self.timeLabel = QLabel(modelCardTemplate)
        self.timeLabel.setObjectName(u"timeLabel")

        self.verticalLayout.addWidget(self.timeLabel)

        self.cardButtonLayout = QHBoxLayout()
        self.cardButtonLayout.setObjectName(u"cardButtonLayout")
        self.btn3d = QPushButton(modelCardTemplate)
        self.btn3d.setObjectName(u"btn3d")

        self.cardButtonLayout.addWidget(self.btn3d)

        self.btnEditModel = QPushButton(modelCardTemplate)
        self.btnEditModel.setObjectName(u"btnEditModel")

        self.cardButtonLayout.addWidget(self.btnEditModel)


        self.verticalLayout.addLayout(self.cardButtonLayout)


        self.retranslateUi(modelCardTemplate)

        QMetaObject.connectSlotsByName(modelCardTemplate)
    # setupUi

    def retranslateUi(self, modelCardTemplate):
        self.nameLabel.setText(QCoreApplication.translate("ModelCard", u"Model Name", None))
        self.timeLabel.setText(QCoreApplication.translate("ModelCard", u"Print time: 1h30m", None))
        self.btn3d.setText(QCoreApplication.translate("ModelCard", u"3D View", None))
        self.btnEditModel.setText(QCoreApplication.translate("ModelCard", u"Edit", None))
        pass
    # retranslateUi

