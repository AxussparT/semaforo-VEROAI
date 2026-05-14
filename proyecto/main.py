import sys
from PyQt6 import QtWidgets, QtGui
from PyQt6.QtWidgets import QGraphicsDropShadowEffect

# Importamos la clase de tu diseño (asegúrate de que tu archivo .py se llame interfaz.py)
# Si tu archivo se llama diferente, cambia "interfaz" por el nombre de tu archivo sin el .py
from principal import Ui_MainWindow 

class SemaforoApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 1. Cargamos tu interfaz gráfica
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # 2. Aplicamos el efecto neón a los frames que necesites
        self.aplicar_neon(self.ui.semaforo_man)
        self.aplicar_neon(self.ui.pesos)
        self.aplicar_neon(self.ui.vista1)
        self.aplicar_neon(self.ui.vista2)
        self.aplicar_neon(self.ui.vista3)
        self.aplicar_neon(self.ui.vista4)

    # --- Función para crear la magia del neón ---
    def aplicar_neon(self, widget):
        # NOTA: En PyQt, cada elemento necesita su PROPIA instancia del efecto.
        # Por eso creamos uno nuevo cada vez que llamamos a esta función.
        efecto_neon = QGraphicsDropShadowEffect(self)
        
        # Ajusta el radio de difuminado (prueba con 20, 30 o 40 hasta que te guste)
        efecto_neon.setBlurRadius(30)
        
        # El color verde brillante de tu diseño (168, 254, 57)
        color_neon = QtGui.QColor(168, 254, 57, 255) 
        efecto_neon.setColor(color_neon)
        
        # Offset en 0 para que la luz rodee todo el cuadro por igual
        efecto_neon.setXOffset(0)
        efecto_neon.setYOffset(0)
        
        # Le aplicamos el efecto al widget (el frame) que pasamos a la función
        widget.setGraphicsEffect(efecto_neon)

# --- Bloque principal para ejecutar la aplicación ---
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    ventana = SemaforoApp()
    ventana.show()
    sys.exit(app.exec())