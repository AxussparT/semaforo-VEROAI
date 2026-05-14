from PyQt6 import QtWidgets, QtCore, QtGui
import os
import time
import cv2

# Importamos la interfaz generada
from .ui_generated import Ui_MainWindow
from ..ia.detector_yolo import DetectorYOLO
from ..control.gestor_semaforos import GestorSemaforos
from PyQt6.QtWidgets import QGraphicsDropShadowEffect


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, num_carriles):
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.num_carriles = num_carriles

        self.detector = DetectorYOLO()
        self.gestor = GestorSemaforos()

        # Frames de vistas
        self.vistas = [
            self.ui.vista1,
            self.ui.vista2,
            self.ui.vista3,
            self.ui.vista4
        ]

        self.corregir_estilo_inputs()

        # Labels donde se mostrarán las imágenes
        self.labels_camara = []

        for i, vista in enumerate(self.vistas):

            # Fondo negro para mejor visualización
            vista.setStyleSheet("""
                background-color: black;
                border: 4px solid #A8FE39;
                border-radius: 10px;
            """)

            self.aplicar_neon(vista, "#A8FE39")

            label = QtWidgets.QLabel(vista)

            # El label ocupa todo el frame
            label.setGeometry(vista.rect())

            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

            label.setScaledContents(False)

            label.setStyleSheet("""
                background-color: black;
                border: none;
            """)

            label.show()

            self.labels_camara.append(label)

            # Ocultar vistas no utilizadas
            if i >= self.num_carriles:
                vista.hide()

        # Botón manual
        self.ui.pushButton_4.clicked.connect(self.ciclo_deteccion)

        # Timer automático
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.ciclo_deteccion)
        self.timer.start(5000)

        # Primera carga
        QtCore.QTimer.singleShot(1000, self.ciclo_deteccion)

    # =========================================================

    def corregir_estilo_inputs(self):

        estilo = """
            color: black;
            background-color: white;
            font-weight: bold;
            border-radius: 5px;
        """

        for w in [
            self.ui.lineEdit,
            self.ui.lineEdit_2,
            self.ui.lineEdit_3,
            self.ui.lineEdit_4,
            self.ui.lineEdit_5,
            self.ui.lineEdit_6
        ]:
            w.setStyleSheet(estilo)

    # =========================================================

    def resizeEvent(self, event):
        """
        Hace que los QLabel siempre ocupen todo el frame.
        """

        super().resizeEvent(event)

        for vista, label in zip(self.vistas, self.labels_camara):
            label.setGeometry(vista.rect())

    # =========================================================

    def ciclo_deteccion(self):

        conteos = []

        try:

            pesos = {
                'truck': float(self.ui.lineEdit.text() or 1.5),
                'bus': float(self.ui.lineEdit_2.text() or 1.3),
                'car': float(self.ui.lineEdit_3.text() or 1.0),
                'motorbike': float(self.ui.lineEdit_4.text() or 0.8),
                'bicycle': float(self.ui.lineEdit_5.text() or 0.5),
                'person': float(self.ui.lineEdit_6.text() or 0.3)
            }

        except ValueError:
            return

        output_dir = "test/procesadas"

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # ==========================================
        # CARGAR IMÁGENES AUTOMÁTICAMENTE
        # ==========================================

        imagenes = sorted([
            f for f in os.listdir("test")
            if f.lower().endswith((".jpg", ".jpeg", ".png"))
        ])

        for i, nombre in enumerate(imagenes[:self.num_carriles]):

            path_in = os.path.join("test", nombre)

            try:

                img, c = self.detector.procesar_interseccion(path_in)

                conteos.append(c)

                if img is None:
                    continue

                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

                h, w, ch = img_rgb.shape

                bytes_per_line = ch * w

                q_img = QtGui.QImage(
                    img_rgb.data,
                    w,
                    h,
                    bytes_per_line,
                    QtGui.QImage.Format.Format_RGB888
                ).copy()

                pixmap = QtGui.QPixmap.fromImage(q_img)

                pixmap_escalado = pixmap.scaled(
                    self.labels_camara[i].size(),
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation
                )

                self.labels_camara[i].setPixmap(pixmap_escalado)

                self.labels_camara[i].raise_()

                cv2.imwrite(
                    f"{output_dir}/inf_{i+1}.jpg",
                    img
                )

            except Exception as e:
                print(f"ERROR carril {i+1}: {e}")

        # ==========================================

        idx_v = self.gestor.calcular_prioridades(
            conteos,
            pesos
        )

        self.actualizar_colores_semaforo(idx_v)

        self.limpiar_cache(output_dir)

    # =========================================================

    def limpiar_cache(self, folder):

        for f in os.listdir(folder):

            path = os.path.join(folder, f)

            if time.time() - os.path.getmtime(path) > 30:

                try:
                    os.remove(path)

                except:
                    pass

    # =========================================================

    def actualizar_colores_semaforo(self, index_verde):

        for i, vista in enumerate(self.vistas[:self.num_carriles]):

            color = "#A8FE39" if i == index_verde else "#FF0000"

            vista.setStyleSheet(f"""
                background-color: black;
                border: 4px solid {color};
                border-radius: 10px;
            """)

            # Actualizar neon
            self.aplicar_neon(vista, color)

            # Mantener imagen visible
            self.labels_camara[i].raise_()
    
    def aplicar_neon(self, widget, color):

        efecto = QGraphicsDropShadowEffect()

        efecto.setBlurRadius(25)

        efecto.setColor(QtGui.QColor(color))

        efecto.setOffset(0)

        widget.setGraphicsEffect(efecto)