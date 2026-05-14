import cv2
from ultralytics import YOLO

class DetectorYOLO:
    def __init__(self, model_path="data/weights/yolo26n.pt"):
        # Carga el modelo una sola vez para optimizar recursos
        self.model = YOLO(model_path)
        # Mapeo de IDs de clase a nombres de la interfaz
        self.clases = {0: 'person', 1: 'bicycle', 2: 'car', 3: 'motorbike', 5: 'bus', 7: 'truck'}

    def procesar_interseccion(self, frame_path):
        results = self.model.predict(frame_path, conf=0.5)[0]
        
        # Imagen con los cuadros delimitadores dibujados
        imagen_anotada = results.plot()
        
        # Conteo de objetos por clase
        conteo = {clase: 0 for clase in self.clases.values()}
        for box in results.boxes:
            cls_id = int(box.cls[0])
            nombre = self.clases.get(cls_id)
            if nombre:
                conteo[nombre] += 1
                
        return imagen_anotada, conteo