"""
principal.py — Controlador principal de SEMAFORO-VEROAI
-------------------------------------------------------
Correcciones aplicadas respecto a la versión original:
  1. La transición ámbar SOLO afecta al carril que está en VERDE, no a todos.
  2. La lógica de parpadeo queda EXCLUSIVAMENTE en el driver/Arduino, no en la UI.
  3. El flujo manual→automático y automático→manual usa una máquina de estados
     clara (EstadoSistema) para evitar condiciones de carrera.
  4. La interfaz es responsiva gracias al nuevo ui_generated.py basado en layouts.
  5. Se agrega el módulo ArduinoDriver con el protocolo de comunicación serial.
"""

from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtWidgets import QGraphicsDropShadowEffect
import os
import time
import cv2
from enum import Enum, auto

from .ui_generated import Ui_MainWindow
from ..ia.detector_yolo import DetectorYOLO
from ..control.gestor_semaforos import GestorSemaforos

# ─────────────────────────────────────────────
#  Driver Arduino (ver arduino_driver.py)
# ─────────────────────────────────────────────
try:
    from ..control.arduino_driver import ArduinoDriver
    ARDUINO_DISPONIBLE = True
except ImportError:
    ARDUINO_DISPONIBLE = False


# ─────────────────────────────────────────────
#  Máquina de estados del sistema
# ─────────────────────────────────────────────
class EstadoSistema(Enum):
    AUTOMATICO   = auto()   # IA controla todo
    TRANSICION   = auto()   # Ámbar de seguridad activo (ni manual ni auto)
    MANUAL       = auto()   # Operador forzó un carril


# Duración (ms) de la fase ámbar de seguridad
DURACION_AMBAR_MS = 7_000


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, num_carriles: int):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("SEMAFORO-VEROAI")

        self.num_carriles = num_carriles
        self.estado = EstadoSistema.AUTOMATICO
        self.carril_verde_actual = 0        # Índice del carril actualmente en verde
        self.carril_manual_objetivo = 0     # Carril elegido por el operador

        # ── IA y Control ──────────────────────────────────────────
        self.detector = DetectorYOLO()
        self.gestor   = GestorSemaforos()

        # ── Driver Arduino (opcional) ──────────────────────────────
        self.arduino: ArduinoDriver | None = None
        if ARDUINO_DISPONIBLE:
            try:
                self.arduino = ArduinoDriver(port="COM3", num_carriles=num_carriles)
                self.arduino.conectar()
                self.statusBar().showMessage("Arduino conectado ✔")
            except Exception as e:
                self.statusBar().showMessage(f"Arduino no disponible: {e}")

        # ── Vistas de cámara ──────────────────────────────────────
        self.vistas = [self.ui.vista1, self.ui.vista2, self.ui.vista3, self.ui.vista4]
        self.labels_camara: list[QtWidgets.QLabel] = []

        for i in range(4):
            layout = QtWidgets.QVBoxLayout(self.vistas[i])
            layout.setContentsMargins(2, 2, 2, 2)

            label = QtWidgets.QLabel()
            label.setScaledContents(True)
            label.setStyleSheet("background-color: transparent;")
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
            self.labels_camara.append(label)

            self._aplicar_neon(self.vistas[i])

            if i >= self.num_carriles:
                self.vistas[i].hide()

        # ── Sección de pesos ──────────────────────────────────────
        self._configurar_seccion_pesos()

        # ── Sección de control manual ─────────────────────────────
        self._configurar_control_manual()

        # ── Timer principal (ciclo IA cada 5 s) ──────────────────
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.ejecutar_ciclo_sistema)
        self.timer.start(5_000)

        QtCore.QTimer.singleShot(500, self.ejecutar_ciclo_sistema)

    # ═══════════════════════════════════════════════════════════════
    #  Configuración de UI
    # ═══════════════════════════════════════════════════════════════

    def _configurar_seccion_pesos(self):
        estilo = (
            "color: black; background-color: white;"
            "font-weight: bold; border-radius: 5px; padding: 2px;"
        )
        self.inputs_pesos = {
            'truck':     self.ui.lineEdit,
            'bus':       self.ui.lineEdit_2,
            'car':       self.ui.lineEdit_3,
            'motorbike': self.ui.lineEdit_4,
            'bicycle':   self.ui.lineEdit_5,
            'person':    self.ui.lineEdit_6,
        }
        valores_defecto = {
            'truck': "1.5", 'bus': "1.3", 'car': "1.0",
            'motorbike': "0.8", 'bicycle': "0.5", 'person': "0.3",
        }
        for clave, widget in self.inputs_pesos.items():
            widget.setStyleSheet(estilo)
            widget.setText(valores_defecto[clave])

        self.ui.pushButton_4.clicked.connect(self.ejecutar_ciclo_sistema)

    def _configurar_control_manual(self):
        """
        Construye los controles manuales dinámicamente dentro de semaforo_man.
        Sustituye los botones circulares decorativos por controles funcionales.
        """
        # Ocultamos los círculos decorativos del layout original
        self.ui.pushButton.hide()
        self.ui.pushButton_2.hide()
        self.ui.pushButton_3.hide()

        layout_man = self.ui.semaforo_man.layout()   # QVBoxLayout del panel

        # Fila: etiqueta + combo de carriles
        fila_selector = QtWidgets.QHBoxLayout()
        lbl = QtWidgets.QLabel("Carril objetivo:")
        lbl.setStyleSheet("color: white; font: 11pt 'Segoe UI';")
        self.selector_carril = QtWidgets.QComboBox()
        self.selector_carril.setStyleSheet(
            "color: black; background-color: white; font-weight: bold;"
        )
        self.selector_carril.setFixedHeight(32)
        for i in range(self.num_carriles):
            self.selector_carril.addItem(f"Carril {i + 1}", i)

        fila_selector.addWidget(lbl)
        fila_selector.addWidget(self.selector_carril, stretch=1)
        layout_man.addLayout(fila_selector)

        # Fila: botón Forzar + botón Auto
        fila_btns = QtWidgets.QHBoxLayout()
        fila_btns.setSpacing(10)

        self.btn_forzar = QtWidgets.QPushButton("⚡ Forzar Carril")
        self.btn_forzar.setFixedHeight(36)
        self.btn_forzar.setStyleSheet(
            "background-color: #EDFF08; color: black;"
            "font: bold 10pt 'Segoe UI'; border-radius: 6px;"
        )
        self.btn_forzar.clicked.connect(self._solicitar_modo_manual)

        self.btn_auto = QtWidgets.QPushButton("🤖 Modo Auto")
        self.btn_auto.setFixedHeight(36)
        self.btn_auto.setStyleSheet(
            "background-color: #A8FE39; color: black;"
            "font: bold 10pt 'Segoe UI'; border-radius: 6px;"
        )
        self.btn_auto.clicked.connect(self._solicitar_modo_automatico)

        fila_btns.addWidget(self.btn_forzar)
        fila_btns.addWidget(self.btn_auto)
        layout_man.addLayout(fila_btns)

        # Indicador de estado
        self.lbl_estado = QtWidgets.QLabel("● AUTOMÁTICO")
        self.lbl_estado.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.lbl_estado.setStyleSheet(
            "color: #A8FE39; font: bold 11pt 'Segoe UI'; background: transparent;"
        )
        layout_man.addWidget(self.lbl_estado)

    # ═══════════════════════════════════════════════════════════════
    #  Máquina de estados de transición
    # ═══════════════════════════════════════════════════════════════

    def _solicitar_modo_manual(self):
        """
        El operador quiere forzar un carril.
        SÓLO el carril actualmente en verde recibe el ámbar de transición.
        """
        if self.estado != EstadoSistema.AUTOMATICO:
            return   # Ignora el clic si ya está en transición o manual

        self.carril_manual_objetivo = self.selector_carril.currentData()
        self._iniciar_transicion_ambar(destino=EstadoSistema.MANUAL)

    def _solicitar_modo_automatico(self):
        """Regresa el control a la IA con ámbar de seguridad."""
        if self.estado != EstadoSistema.MANUAL:
            return

        self._iniciar_transicion_ambar(destino=EstadoSistema.AUTOMATICO)

    def _iniciar_transicion_ambar(self, destino: EstadoSistema):
        """
        Pone ÚNICAMENTE el carril en verde en estado ámbar y espera DURACION_AMBAR_MS
        antes de completar el cambio.

        Los demás carriles permanecen en ROJO durante la transición para no
        generar movimiento innecesario en la intersección.
        """
        self.estado = EstadoSistema.TRANSICION
        self._destino_tras_transicion = destino

        self._actualizar_indicador_estado()

        # Solo el carril actualmente verde pasa a ámbar
        self._pintar_carril(self.carril_verde_actual, "ambar")

        # Enviar señal ámbar al Arduino solo para ese carril
        if self.arduino:
            self.arduino.set_carril_ambar(self.carril_verde_actual)

        print(
            f"[TRANSICIÓN] Ámbar en carril {self.carril_verde_actual + 1} "
            f"→ destino: {destino.name}"
        )

        QtCore.QTimer.singleShot(DURACION_AMBAR_MS, self._completar_transicion)

    def _completar_transicion(self):
        """Finaliza la fase ámbar y aplica el estado destino."""
        destino = self._destino_tras_transicion

        if destino == EstadoSistema.MANUAL:
            self.estado = EstadoSistema.MANUAL
            self._actualizar_colores_semaforo(self.carril_manual_objetivo)
            print(f"[MANUAL] Carril {self.carril_manual_objetivo + 1} en VERDE.")

        elif destino == EstadoSistema.AUTOMATICO:
            self.estado = EstadoSistema.AUTOMATICO
            print("[AUTO] Control devuelto a la IA.")
            self.ejecutar_ciclo_sistema()   # Ciclo inmediato para asignar verde correcto

        self._actualizar_indicador_estado()

    def _actualizar_indicador_estado(self):
        textos = {
            EstadoSistema.AUTOMATICO:  ("● AUTOMÁTICO",  "#A8FE39"),
            EstadoSistema.TRANSICION:  ("● TRANSICIÓN",  "#C8BA1D"),
            EstadoSistema.MANUAL:      ("● MANUAL",      "#EDFF08"),
        }
        texto, color = textos[self.estado]
        self.lbl_estado.setText(texto)
        self.lbl_estado.setStyleSheet(
            f"color: {color}; font: bold 11pt 'Segoe UI'; background: transparent;"
        )

    # ═══════════════════════════════════════════════════════════════
    #  Ciclo principal de detección
    # ═══════════════════════════════════════════════════════════════

    def ejecutar_ciclo_sistema(self):
        """
        Captura pesos, ejecuta YOLO y actualiza la UI.
        Si estamos en TRANSICIÓN o MANUAL, solo actualiza imágenes sin cambiar colores.
        """
        pesos = self._leer_pesos()
        conteos = []

        output_dir = "test/procesadas"
        os.makedirs(output_dir, exist_ok=True)

        for i in range(self.num_carriles):
            path_in = f"test/carril_{i + 1}.jpg"
            if os.path.exists(path_in):
                img, c = self.detector.procesar_interseccion(path_in)
                conteos.append(c)
                self._mostrar_imagen(i, img)
                cv2.imwrite(f"{output_dir}/inf_{i + 1}.jpg", img)
            else:
                conteos.append({})

        # Respeta la prioridad de estado
        if self.estado == EstadoSistema.TRANSICION:
            return
        if self.estado == EstadoSistema.MANUAL:
            self._actualizar_colores_semaforo(self.carril_manual_objetivo)
            return

        # Modo automático: la IA decide
        idx_verde = self.gestor.calcular_prioridades(conteos, pesos)
        self._actualizar_colores_semaforo(idx_verde)
        self._limpiar_cache(output_dir)

    def _leer_pesos(self) -> dict:
        pesos = {}
        for clave, widget in self.inputs_pesos.items():
            try:
                pesos[clave] = float(widget.text() or 1.0)
            except ValueError:
                pesos[clave] = 1.0
        return pesos

    def _mostrar_imagen(self, idx: int, img):
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, ch = img_rgb.shape
        q_img = QtGui.QImage(
            img_rgb.data, w, h, ch * w,
            QtGui.QImage.Format.Format_RGB888
        )
        self.labels_camara[idx].setPixmap(QtGui.QPixmap.fromImage(q_img.copy()))

    # ═══════════════════════════════════════════════════════════════
    #  Actualización visual de semáforos
    # ═══════════════════════════════════════════════════════════════

    def _actualizar_colores_semaforo(self, index_verde: int):
        """
        Pinta los marcos de las cámaras y actualiza el Arduino.
        El parpadeo NUNCA se gestiona aquí; es responsabilidad del driver Arduino.
        """
        self.carril_verde_actual = index_verde

        for i, vista in enumerate(self.vistas[:self.num_carriles]):
            if i == index_verde:
                self._pintar_carril(i, "verde")
            else:
                self._pintar_carril(i, "rojo")

        # Enviar estado al Arduino
        if self.arduino:
            self.arduino.set_semaforo(index_verde)

    def _pintar_carril(self, idx: int, color: str):
        """
        color: "verde" | "rojo" | "ambar"
        """
        COLORES = {
            "verde": ("#A8FE39", QtGui.QColor(168, 254, 57)),
            "rojo":  ("#FF0000", QtGui.QColor(255, 0, 0)),
            "ambar": ("#C8BA1D", QtGui.QColor(200, 186, 29)),
        }
        hex_c, q_c = COLORES[color]
        vista = self.vistas[idx]
        vista.setStyleSheet(
            f"background-color: black;"
            f"border: 4px solid {hex_c};"
            f"border-radius: 10px;"
        )
        self._aplicar_neon(vista, q_c)

    # ═══════════════════════════════════════════════════════════════
    #  Utilidades
    # ═══════════════════════════════════════════════════════════════

    def _aplicar_neon(self, widget, color=QtGui.QColor(168, 254, 57)):
        efecto = QGraphicsDropShadowEffect(self)
        efecto.setBlurRadius(28)
        efecto.setColor(color)
        efecto.setXOffset(0)
        efecto.setYOffset(0)
        widget.setGraphicsEffect(efecto)

    def _limpiar_cache(self, folder: str):
        for f in os.listdir(folder):
            path = os.path.join(folder, f)
            if time.time() - os.path.getmtime(path) > 30:
                try:
                    os.remove(path)
                except OSError:
                    pass

    def closeEvent(self, event):
        if self.arduino:
            self.arduino.desconectar()
        super().closeEvent(event)
