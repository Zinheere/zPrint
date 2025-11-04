# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'new_model_dialog.ui'
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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QComboBox, QDialog,
    QDialogButtonBox, QFormLayout, QFrame, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QListWidget, QPushButton, QSizePolicy, QSpacerItem,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

class Ui_NewModelDialog(object):
    def setupUi(self, NewModelDialog):
        if not NewModelDialog.objectName():
            NewModelDialog.setObjectName(u"NewModelDialog")
        NewModelDialog.setWindowModality(Qt.WindowModal)
        self.verticalLayout = QVBoxLayout(NewModelDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.groupModelInfo = QGroupBox(NewModelDialog)
        self.groupModelInfo.setObjectName(u"groupModelInfo")
        self.formLayoutModelInfo = QFormLayout(self.groupModelInfo)
        self.formLayoutModelInfo.setObjectName(u"formLayoutModelInfo")
        self.labelName = QLabel(self.groupModelInfo)
        self.labelName.setObjectName(u"labelName")

        self.formLayoutModelInfo.setWidget(0, QFormLayout.ItemRole.LabelRole, self.labelName)

        self.lineEditName = QLineEdit(self.groupModelInfo)
        self.lineEditName.setObjectName(u"lineEditName")

        self.formLayoutModelInfo.setWidget(0, QFormLayout.ItemRole.FieldRole, self.lineEditName)

        self.labelStl = QLabel(self.groupModelInfo)
        self.labelStl.setObjectName(u"labelStl")

        self.formLayoutModelInfo.setWidget(1, QFormLayout.ItemRole.LabelRole, self.labelStl)

        self.layoutStl = QVBoxLayout()
        self.layoutStl.setObjectName(u"layoutStl")
        self.listWidgetStlFiles = QListWidget(self.groupModelInfo)
        self.listWidgetStlFiles.setObjectName(u"listWidgetStlFiles")
        self.listWidgetStlFiles.setSelectionMode(QListWidget.SingleSelection)

        self.layoutStl.addWidget(self.listWidgetStlFiles)

        self.layoutStlButtons = QHBoxLayout()
        self.layoutStlButtons.setObjectName(u"layoutStlButtons")
        self.btnAddStl = QPushButton(self.groupModelInfo)
        self.btnAddStl.setObjectName(u"btnAddStl")

        self.layoutStlButtons.addWidget(self.btnAddStl)

        self.btnRemoveStl = QPushButton(self.groupModelInfo)
        self.btnRemoveStl.setObjectName(u"btnRemoveStl")

        self.layoutStlButtons.addWidget(self.btnRemoveStl)

        self.horizontalSpacerStl = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.layoutStlButtons.addItem(self.horizontalSpacerStl)


        self.layoutStl.addLayout(self.layoutStlButtons)


        self.formLayoutModelInfo.setLayout(1, QFormLayout.ItemRole.FieldRole, self.layoutStl)

        self.labelPreview = QLabel(self.groupModelInfo)
        self.labelPreview.setObjectName(u"labelPreview")

        self.formLayoutModelInfo.setWidget(2, QFormLayout.ItemRole.LabelRole, self.labelPreview)

        self.layoutPreview = QHBoxLayout()
        self.layoutPreview.setObjectName(u"layoutPreview")
        self.previewLabel = QLabel(self.groupModelInfo)
        self.previewLabel.setObjectName(u"previewLabel")
        self.previewLabel.setMinimumSize(QSize(180, 140))
        self.previewLabel.setFrameShape(QFrame.StyledPanel)
        self.previewLabel.setFrameShadow(QFrame.Raised)
        self.previewLabel.setAlignment(Qt.AlignCenter)

        self.layoutPreview.addWidget(self.previewLabel)

        self.btnChoosePreview = QPushButton(self.groupModelInfo)
        self.btnChoosePreview.setObjectName(u"btnChoosePreview")

        self.layoutPreview.addWidget(self.btnChoosePreview)


        self.formLayoutModelInfo.setLayout(2, QFormLayout.ItemRole.FieldRole, self.layoutPreview)


        self.verticalLayout.addWidget(self.groupModelInfo)

        self.groupGcodes = QGroupBox(NewModelDialog)
        self.groupGcodes.setObjectName(u"groupGcodes")
        self.verticalLayoutGcodes = QVBoxLayout(self.groupGcodes)
        self.verticalLayoutGcodes.setObjectName(u"verticalLayoutGcodes")
        self.tableGcodes = QTableWidget(self.groupGcodes)
        if (self.tableGcodes.columnCount() < 3):
            self.tableGcodes.setColumnCount(3)
        __qtablewidgetitem = QTableWidgetItem()
        self.tableGcodes.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.tableGcodes.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.tableGcodes.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        self.tableGcodes.setObjectName(u"tableGcodes")

        self.verticalLayoutGcodes.addWidget(self.tableGcodes)

        self.layoutGcodeButtons = QHBoxLayout()
        self.layoutGcodeButtons.setObjectName(u"layoutGcodeButtons")
        self.btnAddGcode = QPushButton(self.groupGcodes)
        self.btnAddGcode.setObjectName(u"btnAddGcode")

        self.layoutGcodeButtons.addWidget(self.btnAddGcode)

        self.btnRemoveGcode = QPushButton(self.groupGcodes)
        self.btnRemoveGcode.setObjectName(u"btnRemoveGcode")

        self.layoutGcodeButtons.addWidget(self.btnRemoveGcode)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.layoutGcodeButtons.addItem(self.horizontalSpacer)


        self.verticalLayoutGcodes.addLayout(self.layoutGcodeButtons)


        self.verticalLayout.addWidget(self.groupGcodes)

        self.groupStorage = QGroupBox(NewModelDialog)
        self.groupStorage.setObjectName(u"groupStorage")
        self.formLayoutStorage = QFormLayout(self.groupStorage)
        self.formLayoutStorage.setObjectName(u"formLayoutStorage")
        self.labelLocation = QLabel(self.groupStorage)
        self.labelLocation.setObjectName(u"labelLocation")

        self.formLayoutStorage.setWidget(0, QFormLayout.ItemRole.LabelRole, self.labelLocation)

        self.comboLocation = QComboBox(self.groupStorage)
        self.comboLocation.setObjectName(u"comboLocation")

        self.formLayoutStorage.setWidget(0, QFormLayout.ItemRole.FieldRole, self.comboLocation)

        self.labelDestination = QLabel(self.groupStorage)
        self.labelDestination.setObjectName(u"labelDestination")

        self.formLayoutStorage.setWidget(1, QFormLayout.ItemRole.LabelRole, self.labelDestination)

        self.layoutDestination = QHBoxLayout()
        self.layoutDestination.setObjectName(u"layoutDestination")
        self.lineEditDestination = QLineEdit(self.groupStorage)
        self.lineEditDestination.setObjectName(u"lineEditDestination")

        self.layoutDestination.addWidget(self.lineEditDestination)

        self.btnBrowseDestination = QPushButton(self.groupStorage)
        self.btnBrowseDestination.setObjectName(u"btnBrowseDestination")

        self.layoutDestination.addWidget(self.btnBrowseDestination)


        self.formLayoutStorage.setLayout(1, QFormLayout.ItemRole.FieldRole, self.layoutDestination)


        self.verticalLayout.addWidget(self.groupStorage)

        self.buttonBox = QDialogButtonBox(NewModelDialog)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Save)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(NewModelDialog)
        self.buttonBox.accepted.connect(NewModelDialog.accept)
        self.buttonBox.rejected.connect(NewModelDialog.reject)

        QMetaObject.connectSlotsByName(NewModelDialog)
    # setupUi

    def retranslateUi(self, NewModelDialog):
        NewModelDialog.setWindowTitle(QCoreApplication.translate("NewModelDialog", u"New Model", None))
        self.groupModelInfo.setTitle(QCoreApplication.translate("NewModelDialog", u"Model Info", None))
        self.labelName.setText(QCoreApplication.translate("NewModelDialog", u"Model Name", None))
        self.labelStl.setText(QCoreApplication.translate("NewModelDialog", u"STL / 3MF Files", None))
        self.btnAddStl.setText(QCoreApplication.translate("NewModelDialog", u"Add Model File...", None))
        self.btnRemoveStl.setText(QCoreApplication.translate("NewModelDialog", u"Remove Selected", None))
        self.labelPreview.setText(QCoreApplication.translate("NewModelDialog", u"Preview Image", None))
        self.previewLabel.setText(QCoreApplication.translate("NewModelDialog", u"No Preview", None))
        self.btnChoosePreview.setText(QCoreApplication.translate("NewModelDialog", u"Choose Image", None))
        self.groupGcodes.setTitle(QCoreApplication.translate("NewModelDialog", u"G-Code Variants", None))
        ___qtablewidgetitem = self.tableGcodes.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("NewModelDialog", u"File", None));
        ___qtablewidgetitem1 = self.tableGcodes.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("NewModelDialog", u"Material", None));
        ___qtablewidgetitem2 = self.tableGcodes.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("NewModelDialog", u"Print Time", None));
        self.btnAddGcode.setText(QCoreApplication.translate("NewModelDialog", u"Add G-code", None))
        self.btnRemoveGcode.setText(QCoreApplication.translate("NewModelDialog", u"Remove Selected", None))
        self.groupStorage.setTitle(QCoreApplication.translate("NewModelDialog", u"Storage", None))
        self.labelLocation.setText(QCoreApplication.translate("NewModelDialog", u"Save Location", None))
        self.labelDestination.setText(QCoreApplication.translate("NewModelDialog", u"Destination Folder", None))
        self.btnBrowseDestination.setText(QCoreApplication.translate("NewModelDialog", u"Browse...", None))
    # retranslateUi

