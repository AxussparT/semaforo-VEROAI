class GestorSemaforos:
    def calcular_prioridades(self, lista_conteos, pesos_manuales):
        """
        Calcula el puntaje de cada carril usando la fórmula: 
        Prioridad = Σ (Cantidad * Peso)
        """
        puntajes = []
        for conteo in lista_conteos:
            total = 0
            for objeto, cantidad in conteo.items():
                peso = pesos_manuales.get(objeto, 1.0)
                total += cantidad * peso
            puntajes.append(total)
            
        # Determina el carril ganador[cite: 2]
        if max(puntajes) == 0:
            return 0 # Por defecto el primero si no hay tráfico
            
        return puntajes.index(max(puntajes))