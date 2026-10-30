import os
import sys
import unicodedata
import pickle
import re
from datetime import date, datetime


class Lote:

    INCREMENTO_MINIMO_POR_DEFECTO = 50  # $/kg: subida minima entre pujas (RF-35)

    def __init__(self, id_lote, fecha_registro, cantidad_animales, precio_compra_kg=0, id_jornada=None,
                 tipo_animal=None):
        self.id_lote = id_lote
        self.fecha_registro = fecha_registro
        self.cantidad_animales = cantidad_animales
        self.precio_compra_kg = precio_compra_kg  # $/kg pagado al proveedor por todo el lote
        self.tipo_animal = tipo_animal  # homogeneidad: todos los animales del lote son de este tipo
        self.estado = "abierto"
        self.animales = []
        self.id_jornada = id_jornada  # RF-11
        self.precio_venta_kg = None   # $/kg al que se vendio el lote
        self.precio_venta = None      # total de la venta = precio_venta_kg x peso total
        self.comprador = None
        self.proveedor = None    # RF-30: vendedor/proveedor del lote
        self.pujas = []          # RF-35: historial de pujas de la subasta de este lote (valor en $/kg)
        self.precio_salida_kg = None  # RF-34: precio minimo por kg con el que arranca la subasta
        self.incremento_minimo_kg = self.INCREMENTO_MINIMO_POR_DEFECTO  # RF-35

    def establecer_precio_salida(self, valor_kg, incremento_minimo_kg=None):
        """RF-34: registra o actualiza el precio base/de salida del lote (en
        $/kg), antes de que arranque la subasta. Es el minimo por kilo al que
        se aceptaria vender el lote. Ya no se puede cambiar una vez que el
        lote tiene pujas registradas."""
        if len(self.pujas) > 0:
            return False
        self.precio_salida_kg = valor_kg
        if incremento_minimo_kg is not None:
            self.incremento_minimo_kg = incremento_minimo_kg
        return True

    def precio_salida_total(self):
        """Precio de salida del lote completo = $/kg x peso total. None si aun no se define."""
        if self.precio_salida_kg is None:
            return None
        return self.precio_salida_kg * self.peso_total_kg()

    def puja_minima_kg(self):
        """Valor minimo por kg que puede tener la proxima puja: la primera
        puja debe ser al menos el precio de salida; las siguientes, al menos
        la ultima puja mas el incremento minimo. None si no hay precio de salida."""
        if self.precio_salida_kg is None:
            return None
        if not self.pujas:
            return self.precio_salida_kg
        return self.pujas[-1].valor + self.incremento_minimo_kg

    def validar_rango_animales(self):
        # RF-01 + RF-36: el rango (minimo y maximo) lo configura el administrador
        if self.cantidad_animales < RANGO_ANIMALES["minimo"] or self.cantidad_animales > RANGO_ANIMALES["maximo"]:
            return False
        return True

    def agregar_animal(self, animal):
        # RF-02 + homogeneidad del lote
        animal.id_lote = self.id_lote
        self.animales.append(animal)

    def cantidad_animales_faltantes(self):
        """Cuantos animales faltan por registrar, uno por uno, para
        completar la cantidad declarada al crear el lote."""
        return max(0, self.cantidad_animales - len(self.animales))

    def esta_completo(self):
        """True solo si ya se registraron (uno por uno, en Animales) todos
        los animales que se declararon al crear el lote. Un lote no puede
        venderse mientras le falten animales por registrar."""
        return len(self.animales) >= self.cantidad_animales

    def jornada_esta_abierta(self):
        # Apoyo para RF-03 / RF-04
        if self.id_jornada is None:
            return True
        jornada = next((j for j in jornadas_registradas if j.id_jornada == self.id_jornada), None)
        if jornada is None:
            return True
        return jornada.estado == "abierta"

    def peso_total_kg(self):
        """Suma el peso de todos los animales del lote, en kilogramos."""
        return sum(animal.peso for animal in self.animales)

    def peso_total_toneladas(self):
        """Convierte el peso total del lote de kg a toneladas (1 ton = 1000 kg)."""
        return self.peso_total_kg() / 1000

    def costo_total_compra(self):
        """Lo que costo comprar el lote completo = $/kg de compra x peso total."""
        return self.precio_compra_kg * self.peso_total_kg()

    def ganancia_total(self):
        """(precio de venta por kg - precio de compra por kg) x peso total.
        None si el lote todavia no se ha vendido."""
        if self.precio_venta is None:
            return None
        return self.precio_venta - self.costo_total_compra()

    def ganancia_por_kilo(self):
        """Ganancia por cada kilo vendido (precio de venta/kg - precio de compra/kg).
        None si el lote no se ha vendido o no tiene animales con peso registrado."""
        if self.precio_venta_kg is None or self.peso_total_kg() <= 0:
            return None
        return self.precio_venta_kg - self.precio_compra_kg

    def precio_promedio_compra(self):
        """RF-19: precio promedio de compra por animal del lote
        (costo total del lote / cantidad de animales)."""
        if len(self.animales) == 0:
            return 0.0
        return self.costo_total_compra() / len(self.animales)

    def calcular_ganancia_lote(self):
        """Nombre del metodo tal como aparece en el diagrama de clases (Lote).
        Delega en ganancia_total(), que ya implementa el calculo (RF-20)."""
        return self.ganancia_total()


class Animal:

    def __init__(self, id_animal, registro_ica, tipo, peso=0,
                 raza="", edad=0, observaciones_sanitarias=""):
        self.id_animal = id_animal
        self.registro_ica = registro_ica
        self.tipo = tipo
        self.peso = peso
        self.id_lote = None
        self.raza = raza                                        # RF-31
        self.edad = edad                                        # RF-32
        self.observaciones_sanitarias = observaciones_sanitarias  # RF-33


class Jornada:

    def __init__(self, id_jornada, dia_semana, fecha):
        self.id_jornada = id_jornada
        self.dia_semana = dia_semana
        self.fecha = fecha
        self.estado = "abierta"

    def cerrar(self):
        # RF-04
        self.estado = "cerrada"


class Comprador:

    def __init__(self, id_comprador, nombre, documento, telefono="", id_lote=None):
        self.id_comprador = id_comprador
        self.nombre = nombre
        self.documento = documento
        self.telefono = telefono
        self.id_lote = id_lote  # RF-14


class Proveedor:
    """Clase del diagrama. 'finca' e 'id_lote' no aparecen como atributos
    en el diagrama de clases (documentos/telefono si aparecen), pero
    RF-30 exige la finca de procedencia y el proveedor debe quedar
    asociado a un lote, igual que ya se hizo con Comprador."""

    def __init__(self, id_proveedor, nombre, documento, telefono="", finca="", id_lote=None):
        self.id_proveedor = id_proveedor
        self.nombre = nombre
        self.documentos = documento
        self.telefono = telefono
        self.finca = finca      # RF-30
        self.id_lote = id_lote  # RF-30: a que lote pertenece

    def registrar_proveedor(self, datos):
        """Metodo del diagrama; la logica real vive en la funcion de
        modulo registrar_proveedor(), ya implementada."""
        pass


class Puja:
    """Clase del diagrama. 'id_lote' no aparece como atributo en el
    diagrama (ahi es solo una relacion de asociacion con Lote), pero se
    necesita aqui para saber a que lote pertenece cada puja, igual que
    ya se hizo con Venta."""

    def __init__(self, id_puja, valor, fecha_hora=None, id_lote=None):
        self.id_puja = id_puja
        self.valor = valor
        self.fecha_hora = fecha_hora or datetime.now()
        self.es_ganadora = False
        self.id_lote = id_lote

    def registrar_puja(self, valor):
        """Metodo del diagrama; la logica real vive en la funcion de
        modulo registrar_puja(), ya implementada."""
        self.valor = valor

    def determinar_puja_ganadora(self):
        """Metodo del diagrama; la logica real vive en la funcion de
        modulo determinar_puja_ganadora(), ya implementada."""
        pass


class Auditoria:
    """Clase del diagrama. 'usuario' no aparece como atributo en el
    diagrama (ahi es solo una relacion 'registra' desde Registrador),
    pero RF-29 exige saber que usuario realizo cada operacion."""

    def __init__(self, id_auditoria, operacion, fecha_hora=None, usuario=None):
        self.id_auditoria = id_auditoria
        self.operacion = operacion
        self.fecha_hora = fecha_hora or datetime.now()
        self.usuario = usuario  # RF-29

    def registrar_operacion(self, op):
        """Metodo del diagrama; la logica real vive en la funcion de
        modulo registrar_auditoria(), ya implementada."""
        self.operacion = op


class Venta:
    """Clase del diagrama. id_lote e id_comprador no aparecen como atributos
    en el diagrama (ahi son solo relaciones de asociacion), pero se
    necesitan aqui para poder ubicar la venta dentro de las listas
    globales y resolver las consultas de historial (RF-16, RF-17, RF-18)."""

    def __init__(self, id_venta, fecha, precio_final, forma_pago, id_lote, id_comprador):
        self.id_venta = id_venta
        self.fecha = fecha
        self.precio_final = precio_final
        self.forma_pago = forma_pago
        self.id_lote = id_lote
        self.id_comprador = id_comprador
        self.precio_kg = None       # $/kg al que se vendio (foto del momento de la venta)
        self.peso_total_kg = 0      # peso total vendido, en kg (foto del momento de la venta)
        self.factura = None         # RF-41: factura generada para esta venta

    def registrar_venta_lote(self):
        """RF-15: deja la venta guardada en la lista global de ventas."""
        ventas_registradas.append(self)

    def generar_factura(self):
        """RF-41: genera el comprobante/factura de venta de este lote y lo
        deja guardado en la lista global de facturas."""
        factura = Factura(len(facturas_registradas) + 1, date.today(), self.precio_final, self.id_venta)
        lote = next((l for l in lotes_registrados if l.id_lote == self.id_lote), None)
        if lote is not None:
            factura.incluir_detalle_animales_lote(lote)
        factura.incluir_forma_pago()
        facturas_registradas.append(factura)
        self.factura = factura
        return factura

    def consultar_saldo_pendiente(self):
        """Lo que falta por pagar de esta venta: total menos lo pagado (RF-42).
        En efectivo/transferencia queda en 0; en credito queda el total
        hasta que existan los abonos (RF-43)."""
        pagado = sum(p.monto for p in pagos_registrados if p.id_venta == self.id_venta)
        pagado += sum(a.monto for a in abonos_registrados if a.id_venta == self.id_venta)
        return max(0.0, self.precio_final - pagado)


class Pago:
    """Clase del diagrama (RF-42). 'id_venta' no aparece como atributo en el
    diagrama (ahi es la relacion 'registra' con Venta), pero se necesita para
    saber a que venta pertenece cada pago."""

    def __init__(self, id_pago, monto, fecha, forma_pago):
        self.id_pago = id_pago
        self.monto = monto
        self.fecha = fecha
        self.forma_pago = forma_pago
        self.id_venta = None

    def registrar_pago(self):
        """RF-42: deja el pago guardado en la lista global de pagos."""
        if self.validar_monto():
            pagos_registrados.append(self)

    def seleccionar_forma_pago(self, forma):
        """RF-42: solo acepta efectivo, transferencia o credito."""
        forma = (forma or "").strip().lower()
        if forma in FORMAS_PAGO:
            self.forma_pago = forma

    def validar_monto(self):
        return self.monto >= 0


class Abono:
    """Clase del diagrama. Esqueleto: su logica llegara con RF-43. 'id_venta'
    no aparece en el diagrama (es la relacion 'registra' con Venta)."""

    def __init__(self, id_abono, monto, fecha, saldo_pendiente):
        self.id_abono = id_abono
        self.monto = monto
        self.fecha = fecha
        self.saldo_pendiente = saldo_pendiente
        self.id_venta = None

    def registrar_abono(self):
        """RF-43: registra un abono parcial para una venta a credito."""
        if self.id_venta is None:
            return False, "El abono debe estar asociado a una venta."

        venta = next((v for v in ventas_registradas if v.id_venta == self.id_venta), None)
        if venta is None:
            return False, "No existe la venta asociada al abono."

        if venta.forma_pago != "credito":
            return False, "Solo se pueden registrar abonos en ventas a credito."

        if self.monto <= 0:
            return False, "El monto del abono debe ser mayor a cero."

        saldo = venta.consultar_saldo_pendiente()
        if self.monto > saldo:
            return False, f"El abono no puede superar el saldo pendiente de ${saldo:,.0f}."

        self.saldo_pendiente = saldo - self.monto
        abonos_registrados.append(self)
        registrar_auditoria(
            f"Registro de abono de ${self.monto:,.0f} para la venta {self.id_venta}")
        return True, None

    def actualizar_saldo_pendiente(self):
        """RF-43: recalcula el saldo pendiente de la venta asociada."""
        if self.id_venta is None:
            return None
        venta = next((v for v in ventas_registradas if v.id_venta == self.id_venta), None)
        if venta is None:
            return None
        self.saldo_pendiente = venta.consultar_saldo_pendiente()
        return self.saldo_pendiente


class Factura:
    """Clase del diagrama (RF-41). 'id_venta', 'id_lote', 'forma_pago' y
    'detalle' no aparecen como atributos en el diagrama (son la relacion
    'genera' con Venta y el detalle que se imprime), pero se necesitan para
    armar el comprobante."""

    def __init__(self, numero_factura, fecha_emision, total, id_venta=None):
        self.numero_factura = numero_factura
        self.fecha_emision = fecha_emision
        self.total = total
        self.id_venta = id_venta
        self.id_lote = None
        self.forma_pago = ""
        self.detalle = []

    def incluir_detalle_animales_lote(self, lote):
        """RF-41: copia a la factura el detalle del lote vendido."""
        self.id_lote = lote.id_lote
        comprador = next((c for c in compradores_registrados if c.id_lote == lote.id_lote), None)
        self.detalle = [
            f"Lote: {lote.id_lote} ({lote.tipo_animal or '-'}) - {len(lote.animales)} animal(es)",
            f"Comprador: {comprador.nombre + ' (Doc. ' + comprador.documento + ')' if comprador else 'Sin comprador registrado'}",
            f"Peso total: {lote.peso_total_kg():,.0f} kg",
        ]
        if lote.precio_venta_kg is not None:
            self.detalle.append(f"Precio de venta: ${lote.precio_venta_kg:,.0f}/kg")
        self.detalle.append("Animales:")
        for animal in lote.animales:
            self.detalle.append(f"  - ICA {animal.registro_ica} | {animal.tipo} | {animal.peso} kg | {animal.raza}")

    def incluir_forma_pago(self):
        """RF-41 + RF-42: copia la forma de pago de la venta a la factura."""
        venta = next((v for v in ventas_registradas if v.id_venta == self.id_venta), None)
        self.forma_pago = venta.forma_pago if venta else ""

    def texto_factura(self):
        lineas = [
            f"FACTURA DE VENTA N° {self.numero_factura}",
            f"Fecha de emision: {self.fecha_emision}",
            f"Venta #{self.id_venta}",
        ]
        lineas.extend(self.detalle)
        lineas.append(f"Forma de pago: {self.forma_pago or '-'}")
        lineas.append(f"TOTAL: ${self.total:,.0f}")
        return "\n".join(lineas)

    def exportar(self, formato):
        """RF-41: version simplificada igual que los reportes: 'pdf' guarda un
        .txt y 'excel' guarda un .csv, en la carpeta 'reportes'."""
        extension = "csv" if str(formato).strip().lower() == "excel" else "txt"
        nombre_archivo = os.path.join(_carpeta_reportes(), f"factura_{self.numero_factura}.{extension}")
        with open(nombre_archivo, "w", encoding="utf-8") as archivo:
            archivo.write(self.texto_factura())
        return nombre_archivo


def _carpeta_reportes():
    """Carpeta fija 'reportes', creada junto al programa (funciona igual
    corriendo el .py o un .exe empaquetado), para que los reportes
    exportados siempre queden en un lugar predecible."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    carpeta = os.path.join(base, "reportes")
    os.makedirs(carpeta, exist_ok=True)
    return carpeta


class Reporte:
    """Clase base del diagrama para todos los reportes del sistema."""

    def __init__(self, id_reporte, fecha_generacion=None):
        self.id_reporte = id_reporte
        self.fecha_generacion = fecha_generacion or date.today()

    def generar(self):
        """Metodo generico de la clase base; cada subclase (ReportePorLote,
        ReporteConsolidadoPorJornada, etc.) lo sobreescribe con su propia
        logica de construccion del reporte."""
        pass

    def _texto_reporte(self):
        return getattr(self, "texto_generado", "(el reporte aun no ha sido generado)")

    def exportar_pdf(self):
        """RF-25: version simplificada de la exportacion a PDF para esta
        entrega: guarda el contenido del reporte en un archivo de texto,
        dentro de una carpeta 'reportes' fija y facil de encontrar."""
        nombre_archivo = os.path.join(_carpeta_reportes(), f"reporte_{self.id_reporte}.txt")
        with open(nombre_archivo, "w", encoding="utf-8") as archivo:
            archivo.write(self._texto_reporte())
        return nombre_archivo

    def exportar_excel(self):
        """RF-25: version simplificada de la exportacion a Excel para esta
        entrega: guarda el contenido del reporte en un archivo CSV,
        dentro de una carpeta 'reportes' fija y facil de encontrar."""
        nombre_archivo = os.path.join(_carpeta_reportes(), f"reporte_{self.id_reporte}.csv")
        with open(nombre_archivo, "w", encoding="utf-8") as archivo:
            archivo.write(self._texto_reporte())
        return nombre_archivo


class ReportePorLote(Reporte):

    def __init__(self, id_reporte, id_lote):
        super().__init__(id_reporte)
        self.id_lote = id_lote

    def generar_reporte_por_lote(self, id_lote):
        """RF-23: reporte por lote con comprador, ICA, peso, precio de
        compra e historial de ventas."""
        self.id_lote = id_lote
        lote = next((l for l in lotes_registrados if l.id_lote == id_lote), None)
        if lote is None:
            self.texto_generado = f"No existe un lote con numero {id_lote}."
            return self.texto_generado

        comprador = next((c for c in compradores_registrados if c.id_lote == id_lote), None)
        ventas_del_lote = [v for v in ventas_registradas if v.id_lote == id_lote]

        lineas = [
            f"REPORTE POR LOTE #{lote.id_lote}",
            f"Fecha de registro: {lote.fecha_registro}",
            f"Comprador: {comprador.nombre + ' (' + comprador.documento + ')' if comprador else 'Sin comprador registrado'}",
            f"Proveedor: {lote.proveedor.nombre + ' - finca ' + lote.proveedor.finca if lote.proveedor else 'Sin proveedor registrado'}",
            f"Peso total del lote: {lote.peso_total_kg():,.0f} kg",
            f"Precio de compra: ${lote.precio_compra_kg:,.0f}/kg  (costo total: ${lote.costo_total_compra():,.0f})",
            "Animales del lote:",
        ]
        for animal in lote.animales:
            lineas.append(f"  - ICA {animal.registro_ica} | {animal.tipo} | {animal.peso} kg | "
                           f"{animal.raza} | {animal.edad} años")

        lineas.append("Historial de ventas:")
        if len(ventas_del_lote) == 0:
            lineas.append("  (este lote todavia no registra ventas)")
        for venta in ventas_del_lote:
            precio_kg_texto = f"${venta.precio_kg:,.0f}/kg | " if venta.precio_kg is not None else ""
            lineas.append(f"  - Venta #{venta.id_venta} | {venta.fecha} | {precio_kg_texto}"
                           f"total ${venta.precio_final:,.0f} | {venta.forma_pago}")

        self.texto_generado = "\n".join(lineas)
        return self.texto_generado

    def consultar_ganancia_lote(self, id_lote):
        lote = next((l for l in lotes_registrados if l.id_lote == id_lote), None)
        if lote is None:
            return None
        return lote.calcular_ganancia_lote()


class ReporteConsolidadoPorJornada(Reporte):

    def __init__(self, id_reporte, id_jornada):
        super().__init__(id_reporte)
        self.id_jornada = id_jornada
        self.total_ventas = 0
        self.ganancia_total = 0.0

    def generar_reporte_jornada(self, id_jornada):
        """RF-24: reporte consolidado de ganancia general por jornada."""
        self.id_jornada = id_jornada
        jornada = next((j for j in jornadas_registradas if j.id_jornada == id_jornada), None)
        if jornada is None:
            self.texto_generado = f"No existe una jornada con id {id_jornada}."
            return self.texto_generado

        lotes_de_la_jornada = [l for l in lotes_registrados if l.id_jornada == id_jornada]
        lotes_vendidos = [l for l in lotes_de_la_jornada if l.estado == "vendido"]
        self.total_ventas = len(lotes_vendidos)
        self.ganancia_total = self.calcular_ganancia_jornada()

        lineas = [
            f"REPORTE CONSOLIDADO - JORNADA #{jornada.id_jornada} ({jornada.dia_semana}, {jornada.fecha})",
            f"Estado de la jornada: {jornada.estado}",
            f"Lotes en la jornada: {len(lotes_de_la_jornada)}",
            f"Lotes vendidos: {self.total_ventas}",
            f"Ganancia total de la jornada: ${self.ganancia_total:,.0f}",
        ]
        self.texto_generado = "\n".join(lineas)
        return self.texto_generado

    def calcular_ganancia_jornada(self):
        lotes_de_la_jornada = [l for l in lotes_registrados if l.id_jornada == self.id_jornada]
        total = 0.0
        for lote in lotes_de_la_jornada:
            ganancia = lote.calcular_ganancia_lote()
            if ganancia is not None:
                total += ganancia
        return total


class ReporteEstadisticas(Reporte):
    """Clase del diagrama para estadisticas generales (RF-45 a RF-47)."""

    def __init__(self, id_reporte, total_lotes=0, total_animales=0, total_ventas=0):
        super().__init__(id_reporte)
        self.total_lotes = total_lotes
        self.total_animales = total_animales
        self.total_ventas = total_ventas

    def generar_estadisticas(self):
        """RF-45 a RF-47: genera un resumen general de ventas y ganancias."""
        self.total_lotes = len(lotes_registrados)
        self.total_animales = sum(len(lote.animales) for lote in lotes_registrados)
        self.total_ventas = len(ventas_registradas)

        lineas = [
            "ESTADISTICAS GENERALES",
            f"Total de lotes: {self.total_lotes}",
            f"Total de animales: {self.total_animales}",
            f"Total de ventas: {self.total_ventas}",
            f"Ganancia general acumulada: ${calcular_ganancia_general():,.0f}",
            "",
            "VENTAS POR TIPO DE ANIMAL"
        ]
        for tipo in ["ternero", "novilla", "vaca"]:
            reporte = ReporteVentasPorTipoAnimal(self.id_reporte, tipo)
            lineas.append(reporte.generar_reporte())

        self.texto_generado = "\n".join(lineas)
        return self.texto_generado

    def calcular_promedios(self):
        """Calcula el promedio de venta por operación registrada."""
        if self.total_ventas == 0:
            return 0.0
        return sum(v.precio_final for v in ventas_registradas) / self.total_ventas


class ReporteVentasPorTipoAnimal(ReporteConsolidadoPorJornada):
    """RF-45: estadisticas de ventas separadas por ternero, novilla y vaca."""

    def __init__(self, id_reporte, tipo_animal="", cantidad_ventas=0, total_ventas=0.0):
        super().__init__(id_reporte, None)
        self.tipo_animal = tipo_animal
        self.cantidad_ventas = cantidad_ventas
        self.total_ventas = total_ventas

    def generar_reporte(self):
        tipos = [self.tipo_animal] if self.tipo_animal else ["ternero", "novilla", "vaca"]
        bloques = []
        for tipo in tipos:
            ventas_tipo = []
            for venta in ventas_registradas:
                lote = next((l for l in lotes_registrados if l.id_lote == venta.id_lote), None)
                if lote is not None and lote.tipo_animal == tipo:
                    ventas_tipo.append(venta)

            cantidad = len(ventas_tipo)
            total = sum(v.precio_final for v in ventas_tipo)
            if tipo == self.tipo_animal:
                self.cantidad_ventas = cantidad
                self.total_ventas = total
            bloques.append(f"{tipo.capitalize()}: {cantidad} venta(s) | total ${total:,.0f}")

        self.texto_generado = "\n".join(bloques)
        return self.texto_generado

    def calcular_ventas_por_tipo(self):
        """RF-45: devuelve el valor total vendido del tipo seleccionado."""
        if not self.tipo_animal:
            return 0.0
        total = 0.0
        for venta in ventas_registradas:
            lote = next((l for l in lotes_registrados if l.id_lote == venta.id_lote), None)
            if lote is not None and lote.tipo_animal == self.tipo_animal:
                total += venta.precio_final
        self.total_ventas = total
        self.cantidad_ventas = sum(
            1 for venta in ventas_registradas
            if (next((l for l in lotes_registrados if l.id_lote == venta.id_lote), None) is not None
                and next((l for l in lotes_registrados if l.id_lote == venta.id_lote), None).tipo_animal == self.tipo_animal)
        )
        return total


class ReporteGananciaComparativaPorJornada(ReporteConsolidadoPorJornada):
    """RF-46: compara las ganancias de las jornadas lunes, miercoles y sabado."""

    def __init__(self, id_reporte, jornada_actual=0, jornada_anterior=0, diferencia_ganancia=0.0):
        super().__init__(id_reporte, None)
        self.jornada_actual = jornada_actual
        self.jornada_anterior = jornada_anterior
        self.diferencia_ganancia = diferencia_ganancia

    def generar_reporte(self):
        resultados = []
        for dia in DIAS_VALIDOS_JORNADA:
            ganancia = 0.0
            ventas = 0
            for jornada in jornadas_registradas:
                if jornada.dia_semana != dia:
                    continue
                for lote in lotes_registrados:
                    if lote.id_jornada == jornada.id_jornada:
                        valor = lote.calcular_ganancia_lote()
                        if valor is not None:
                            ganancia += valor
                        if lote.estado == "vendido":
                            ventas += 1
            resultados.append(f"{dia.capitalize()}: ${ganancia:,.0f} de ganancia | {ventas} venta(s)")

        self.texto_generado = "ESTADISTICAS COMPARATIVAS POR JORNADA\n" + "\n".join(resultados)
        return self.texto_generado

    def comparar_ganancias(self):
        """RF-46: devuelve las ganancias agrupadas por tipo de jornada."""
        resultado = {}
        for dia in DIAS_VALIDOS_JORNADA:
            total = 0.0
            for jornada in jornadas_registradas:
                if jornada.dia_semana == dia:
                    for lote in lotes_registrados:
                        if lote.id_jornada == jornada.id_jornada:
                            ganancia = lote.calcular_ganancia_lote()
                            if ganancia is not None:
                                total += ganancia
            resultado[dia] = total
        return resultado


class ReporteMensualGanancias(ReporteConsolidadoPorJornada):
    """RF-47: reporte consolidado de ganancias para un mes."""

    def __init__(self, id_reporte, mes=0, anio=0, ganancia_total=0.0):
        super().__init__(id_reporte, None)
        self.mes = mes
        self.anio = anio
        self.ganancia_total = ganancia_total

    def generar_reporte(self):
        self.ganancia_total = self.calcular_ganancia_mensual()
        self.texto_generado = (
            f"REPORTE MENSUAL DE GANANCIAS\n"
            f"Mes: {self.mes:02d}/{self.anio}\n"
            f"Ganancia total: ${self.ganancia_total:,.0f}")
        return self.texto_generado

    def calcular_ganancia_mensual(self):
        total = 0.0
        for venta in ventas_registradas:
            if venta.fecha.year == self.anio and venta.fecha.month == self.mes:
                lote = next((l for l in lotes_registrados if l.id_lote == venta.id_lote), None)
                if lote is not None and lote.ganancia_total() is not None:
                    total += lote.ganancia_total()
        return total


class ReporteAnualGanancias(ReporteConsolidadoPorJornada):
    """RF-47: reporte consolidado de ganancias para un año."""

    def __init__(self, id_reporte, anio=0, ganancia_total=0.0):
        super().__init__(id_reporte, None)
        self.anio = anio
        self.ganancia_total = ganancia_total

    def generar_reporte(self):
        self.ganancia_total = self.calcular_ganancia_anual()
        self.texto_generado = (
            f"REPORTE ANUAL DE GANANCIAS\n"
            f"Año: {self.anio}\n"
            f"Ganancia total: ${self.ganancia_total:,.0f}")
        return self.texto_generado

    def calcular_ganancia_anual(self):
        total = 0.0
        for venta in ventas_registradas:
            if venta.fecha.year == self.anio:
                lote = next((l for l in lotes_registrados if l.id_lote == venta.id_lote), None)
                if lote is not None and lote.ganancia_total() is not None:
                    total += lote.ganancia_total()
        return total


class Usuario:

    def __init__(self, id_usuario, nombre, usuario, contrasena, estado=True):
        self.id_usuario = id_usuario
        self.nombre = nombre
        self.usuario = usuario
        self.contrasena = contrasena
        self.estado = estado  # True = activo, False = inactivo
        self.rol = "usuario"

    def iniciar_sesion(self, usuario, contrasena):
        """RF-27"""
        return self.usuario == usuario and self.contrasena == contrasena and self.estado

    def validar_credenciales(self):
        return bool(self.usuario) and bool(self.contrasena)

    def crear_usuario(self, datos):
        """La creacion real de la cuenta la resuelve la funcion de modulo
        registrar_usuario() (RF-26); este metodo queda como esqueleto."""
        pass

    def editar_usuario(self, id_usuario):
        pass

    def eliminar_usuario(self, id_usuario):
        pass

    def reasignar_rol(self, rol):
        self.rol = rol


class Administrador(Usuario):

    def __init__(self, id_usuario, nombre, usuario, contrasena, estado=True):
        super().__init__(id_usuario, nombre, usuario, contrasena, estado)
        self.rol = "administrador"

    def registrar_lote(self, datos):
        pass  # delega en la funcion de modulo registrar_lote(), ya implementada

    def editar_usuario(self, id_usuario):
        pass

    def asignar_rol(self, id_usuario, rol):
        usuario_objetivo = next((u for u in usuarios_registrados if u.id_usuario == id_usuario), None)
        if usuario_objetivo:
            usuario_objetivo.reasignar_rol(rol)

    def realizar_respaldo(self):
        """La clase Respaldo todavia no se ha construido (llegara con RF-48)."""
        pass

    def restaurar_respaldo(self, id_respaldo):
        """Llegara con RF-49."""
        pass


class Registrador(Usuario):

    def __init__(self, id_usuario, nombre, usuario, contrasena, estado=True):
        super().__init__(id_usuario, nombre, usuario, contrasena, estado)
        self.rol = "registrador"

    def registrar_lote(self, datos):
        pass  # delega en la funcion de modulo registrar_lote(), ya implementada

    def registrar_animal(self, datos):
        pass  # delega en la funcion de modulo registrar_animal(), ya implementada

    def registrar_proveedor(self, datos):
        pass  # delega en la funcion de modulo registrar_proveedor(), ya implementada

    def registrar_comprador(self, datos):
        pass  # delega en la funcion de modulo registrar_comprador(), ya implementada

    def registrar_puja(self, valor):
        pass  # delega en la funcion de modulo registrar_puja(), ya implementada

    def registrar_venta_lote(self):
        pass  # delega en la funcion de modulo registrar_venta(), ya implementada

    def registrar_auditoria(self, operacion):
        pass  # delega en la funcion de modulo registrar_auditoria(), ya implementada


class Consulta(Usuario):

    def __init__(self, id_usuario, nombre, usuario, contrasena, estado=True):
        super().__init__(id_usuario, nombre, usuario, contrasena, estado)
        self.rol = "consulta"

    def consultar_saldo_pendiente(self):
        return sum(item["saldo_pendiente"] for item in consultar_saldos_pendientes())

    def consultar_ganancias(self):
        return ganancia_general_acumulada

    def consultar_reportes(self):
        return [v for v in ventas_registradas]

    def consultar_estado_jornada(self):
        return [(j.id_jornada, j.dia_semana, j.fecha, j.estado) for j in jornadas_registradas]

    def consultar_informacion_lote(self, id_lote):
        return next((l for l in lotes_registrados if l.id_lote == id_lote), None)

    def consultar_informacion_animal(self, id_animal):
        for lote in lotes_registrados:
            animal = next((a for a in lote.animales if a.id_animal == id_animal), None)
            if animal:
                return animal
        return None


class Respaldo:
    """RF-48 y RF-49: copia y restauracion de la informacion registrada."""

    def __init__(self, id_respaldo, fecha, ruta_archivo=""):
        self.id_respaldo = id_respaldo
        self.fecha = fecha
        self.ruta_archivo = ruta_archivo

    def realizar_respaldo(self):
        return realizar_respaldo(self.id_respaldo, self.fecha, self.ruta_archivo)

    def restaurar_respaldo(self, id_respaldo):
        return restaurar_respaldo(id_respaldo)


# LISTAS GLOBALES


lotes_registrados = []
icas_registrados = []
jornadas_registradas = []
compradores_registrados = []
ventas_registradas = []          # RF-15 a RF-18
usuarios_registrados = []        # RF-26
proveedores_registrados = []     # RF-30
pujas_registradas = []           # RF-34, RF-35
auditorias_registradas = []      # RF-29
facturas_registradas = []        # RF-41
pagos_registrados = []           # RF-42
abonos_registrados = []         # RF-43
respaldos_registrados = []      # RF-48, RF-49
ganancia_general_acumulada = 0.0  # RF-21, RF-22
sesion_actual = {"usuario": None}  # RF-27, RF-28

DIAS_VALIDOS_JORNADA = ["lunes", "miercoles", "sabado"]

# RF-36: rango permitido de animales por lote (lo configura el administrador)
RANGO_ANIMALES = {"minimo": 10, "maximo": 30}

# RF-31: razas que el usuario puede elegir (menu desplegable, no se escribe)
RAZAS_DISPONIBLES = ["Brahman", "Cebú", "Gyr", "Holstein", "Pardo Suizo",
                     "Romosinuano", "Criollo", "Mestizo", "Otra"]

# RF-42: formas de pago permitidas
FORMAS_PAGO = ["efectivo", "transferencia", "credito"]


def texto_rango_animales():
    """Ej. 'entre 10 y 30' (usa el rango configurado en RF-36)."""
    return f"entre {RANGO_ANIMALES['minimo']} y {RANGO_ANIMALES['maximo']}"

# Indice de Python: date.weekday() -> 0=lunes, 1=martes, 2=miercoles,
# 3=jueves, 4=viernes, 5=sabado, 6=domingo
NOMBRES_DIA_SEMANA = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]


def dia_semana_de_fecha(fecha):
    """Devuelve el nombre del dia de la semana (en minusculas) que
    corresponde a una fecha real, sin importar el año."""
    return NOMBRES_DIA_SEMANA[fecha.weekday()]



# FUNCIONES DE VALIDACION DE CADA RF 

def registrar_lote(id_lote, cantidad_animales, precio_compra_kg=0, id_jornada=None, tipo_animal=None):
    """RF-01, RF-11, homogeneidad de tipo por lote.

    La fecha del lote YA NO se pide por separado: cada lote pertenece a
    una jornada (lunes/miercoles/sabado), asi que su fecha es la misma
    fecha de esa jornada. Pedirla aparte permitia que quedaran
    desincronizadas (ej. jornada del sabado con lote fechado hoy)."""
    if not tipo_animal:
        return None, "Debes seleccionar el tipo de animal del lote."

    if precio_compra_kg <= 0:
        return None, "El precio de compra por kilo debe ser mayor a cero."

    if id_jornada is None:
        return None, "Debes seleccionar la jornada a la que pertenece el lote."

    jornada = next((j for j in jornadas_registradas if j.id_jornada == id_jornada), None)
    if jornada is None:
        return None, "No existe una jornada con ese ID."

    if jornada.estado == "cerrada":
        return None, "La jornada seleccionada ya fue cerrada; no se pueden registrar lotes nuevos en ella."

    if any(l.id_lote == id_lote for l in lotes_registrados):
        return None, f"Ya existe un lote con el numero {id_lote}."

    fecha_registro = jornada.fecha
    nuevo_lote = Lote(id_lote, fecha_registro, cantidad_animales, precio_compra_kg, id_jornada, tipo_animal)

    if not nuevo_lote.validar_rango_animales():
        return None, f"La cantidad de animales debe estar {texto_rango_animales()}."

    lotes_registrados.append(nuevo_lote)
    registrar_auditoria(f"Registro del lote {id_lote}")
    return nuevo_lote, None


def editar_lote(id_lote, cantidad_animales=None, precio_compra_kg=None):
    """RF-03"""
    lote = next((l for l in lotes_registrados if l.id_lote == id_lote), None)

    if lote is None:
        return None, "No existe un lote con ese numero."

    if not lote.jornada_esta_abierta():
        return None, "No se puede editar el lote: su jornada ya fue cerrada."

    if lote.estado == "vendido":
        return None, "No se puede editar el lote: ya fue vendido."

    # Se valida TODO antes de aplicar cualquier cambio (no quedan ediciones a medias)
    if cantidad_animales is not None:
        cantidad_anterior = lote.cantidad_animales
        lote.cantidad_animales = cantidad_animales
        rango_ok = lote.validar_rango_animales()
        lote.cantidad_animales = cantidad_anterior
        if not rango_ok:
            return None, f"La cantidad de animales debe estar {texto_rango_animales()}."
        if cantidad_animales < len(lote.animales):
            return None, (f"El lote ya tiene {len(lote.animales)} animales registrados; "
                          f"la cantidad no puede ser menor.")

    if precio_compra_kg is not None and precio_compra_kg <= 0:
        return None, "El precio de compra por kilo debe ser mayor a cero."

    if cantidad_animales is not None:
        lote.cantidad_animales = cantidad_animales
    if precio_compra_kg is not None:
        lote.precio_compra_kg = precio_compra_kg

    registrar_auditoria(f"Edicion del lote {id_lote}")
    return lote, None


def registrar_jornada(id_jornada, fecha):
    """RF-11, RF-12: el dia de la jornada NO se elige a mano; se calcula
    a partir de la fecha real seleccionada en el calendario. Asi, sin
    importar el año, solo se acepta si esa fecha cae en lunes, miercoles
    o sabado."""
    dia_normalizado = dia_semana_de_fecha(fecha)

    if dia_normalizado not in DIAS_VALIDOS_JORNADA:
        return None, (f"El {fecha.strftime('%Y-%m-%d')} es {dia_normalizado}. "
                       f"La jornada solo puede registrarse los dias lunes, miercoles o sabado.")

    if any(j.id_jornada == id_jornada for j in jornadas_registradas):
        return None, f"Ya existe una jornada con el ID {id_jornada}."

    if any(j.fecha == fecha for j in jornadas_registradas):
        return None, f"Ya existe una jornada registrada para el {fecha.strftime('%Y-%m-%d')}."

    nueva_jornada = Jornada(id_jornada, dia_normalizado, fecha)
    jornadas_registradas.append(nueva_jornada)
    registrar_auditoria(f"Registro de la jornada {id_jornada} ({dia_normalizado} {fecha:%Y-%m-%d})")
    return nueva_jornada, None


def cerrar_jornada(id_jornada):
    """RF-04"""
    jornada = next((j for j in jornadas_registradas if j.id_jornada == id_jornada), None)

    if jornada is None:
        return None, "No existe una jornada con ese ID."

    if jornada.estado == "cerrada":
        return None, "Esa jornada ya estaba cerrada."

    jornada.cerrar()
    registrar_auditoria(f"Cierre de la jornada {id_jornada}")
    return jornada, None


def consultar_jornadas_por_rango(fecha_inicio, fecha_fin):
    """RF-13"""
    resultado = []
    for jornada in jornadas_registradas:
        if fecha_inicio <= jornada.fecha <= fecha_fin:
            resultado.append(jornada)
    return resultado


def registrar_animal(id_animal, registro_ica, tipo, peso, tipo_esperado=None,
                      raza="", edad=0, observaciones_sanitarias=""):
    """RF-06, RF-07, RF-08, RF-09, RF-31, RF-32, RF-33, homogeneidad de
    tipo por lote. El precio ya no se registra por animal: los animales se
    compran por lote y a un precio por kilo (ver Lote.precio_compra_kg)."""
    tipos_validos = ["ternero", "novilla", "vaca"]

    if tipo not in tipos_validos:
        return None, "El tipo de animal no es valido. Debe ser ternero, novilla o vaca."

    if tipo_esperado is not None and tipo != tipo_esperado:
        return None, f"Este lote es de tipo '{tipo_esperado}'. Todos sus animales deben ser de ese mismo tipo."

    registro_ica = (registro_ica or "").strip()
    if not registro_ica:
        return None, "Debes escribir el numero de registro ICA."

    # RF-09: el ICA es unico sin importar mayusculas/minusculas ni espacios sobrantes
    ica_normalizado = registro_ica.upper()
    if any(str(i).strip().upper() == ica_normalizado for i in icas_registrados):
        return None, f"El registro ICA '{registro_ica}' ya fue usado antes."

    if any(a.id_animal == id_animal for l in lotes_registrados for a in l.animales):
        return None, f"Ya existe un animal con el ID {id_animal}."

    if peso <= 0:
        return None, "El peso debe ser mayor a cero."

    if raza not in RAZAS_DISPONIBLES:
        return None, "Debes seleccionar la raza del animal de la lista."

    if edad <= 0:
        return None, "La edad aproximada del animal debe ser mayor a cero."

    icas_registrados.append(registro_ica)
    nuevo_animal = Animal(id_animal, registro_ica, tipo, peso,
                           raza, edad, observaciones_sanitarias or "Sin observaciones.")
    registrar_auditoria(f"Registro del animal con ICA '{registro_ica}'")
    return nuevo_animal, None


def registrar_comprador(id_comprador, nombre, documento, telefono, id_lote):
    """RF-14"""
    if not nombre:
        return None, "Debes escribir el nombre del comprador."

    if not documento:
        return None, "Debes escribir el documento del comprador."

    lote = next((l for l in lotes_registrados if l.id_lote == id_lote), None)
    if lote is None:
        return None, "No existe un lote con ese numero."

    if lote.estado == "vendido":
        return None, "Este lote ya fue vendido; no se puede registrar otro comprador."

    # El ID identifica a una sola persona: no puede repetirse con otro documento
    if any(c.id_comprador == id_comprador and c.documento != documento for c in compradores_registrados):
        return None, f"El ID de comprador {id_comprador} ya pertenece a otra persona. Usa un ID distinto."

    nuevo_comprador = Comprador(id_comprador, nombre, documento, telefono, id_lote)
    compradores_registrados.append(nuevo_comprador)
    registrar_auditoria(f"Registro del comprador '{nombre}' para el lote {id_lote}")
    return nuevo_comprador, None


def validar_precio_venta_kg(lote, precio_venta_kg):
    """Devuelve un mensaje de error si el precio de venta por kilo no es
    valido para ese lote, o None si esta bien. Se usa antes de registrar
    al comprador para no dejar datos a medias."""
    if precio_venta_kg <= 0:
        return "El precio de venta por kilo debe ser mayor a cero."

    if lote.precio_salida_kg is not None and precio_venta_kg < lote.precio_salida_kg:
        return (f"El precio de venta (${precio_venta_kg:,.0f}/kg) no puede ser menor al "
                f"precio de salida del lote (${lote.precio_salida_kg:,.0f}/kg).")
    return None


def marcar_lote_vendido(id_lote, precio_venta_kg):
    """Cierre/venta del lote y calculo de ganancia (seccion Calculos y ganancias).
    El precio de venta se da POR KILO; el total es precio/kg x peso total."""
    lote = next((l for l in lotes_registrados if l.id_lote == id_lote), None)

    if lote is None:
        return None, "No existe un lote con ese numero."

    if lote.estado == "vendido":
        return None, "Este lote ya fue vendido."

    if not lote.jornada_esta_abierta():
        return None, "La jornada de este lote ya fue cerrada; ya no se pueden registrar ventas en ella."

    if not lote.esta_completo():
        faltan = lote.cantidad_animales_faltantes()
        return None, (
            f"Este lote debe tener {lote.cantidad_animales} animales registrados (uno por uno, "
            f"en la seccion Animales) antes de poder venderse. Llevas {len(lote.animales)} "
            f"registrados; faltan {faltan}.")

    error_precio = validar_precio_venta_kg(lote, precio_venta_kg)
    if error_precio:
        return None, error_precio

    lote.precio_venta_kg = precio_venta_kg
    lote.precio_venta = precio_venta_kg * lote.peso_total_kg()
    lote.estado = "vendido"

    return lote, None


def filtrar_lotes_por_tipo(lista_de_lotes, tipo_buscado):
    """RF-05"""
    lotes_encontrados = []
    for lote in lista_de_lotes:
        for animal in lote.animales:
            if animal.tipo == tipo_buscado:
                lotes_encontrados.append(lote)
                break
    return lotes_encontrados


def registrar_venta(id_venta, id_lote, precio_final, forma_pago, fecha=None):
    """RF-15 (registrar el precio de venta del lote), RF-21 y RF-22
    (actualiza la ganancia general acumulada apenas se registra la venta)."""
    global ganancia_general_acumulada

    lote = next((l for l in lotes_registrados if l.id_lote == id_lote), None)
    if lote is None:
        return None, "No existe un lote con ese numero."

    if any(v.id_venta == id_venta for v in ventas_registradas):
        return None, f"Ya existe una venta con el ID {id_venta}."

    if precio_final <= 0:
        return None, "El precio de venta debe ser mayor a cero."

    forma_pago = (forma_pago or "").strip().lower()
    if forma_pago not in FORMAS_PAGO:
        return None, "La forma de pago debe ser efectivo, transferencia o credito."

    comprador = next((c for c in compradores_registrados if c.id_lote == id_lote), None)
    id_comprador = comprador.id_comprador if comprador else None

    nueva_venta = Venta(id_venta, fecha or date.today(), precio_final, forma_pago, id_lote, id_comprador)
    nueva_venta.precio_kg = lote.precio_venta_kg          # foto del momento de la venta
    nueva_venta.peso_total_kg = lote.peso_total_kg()
    nueva_venta.registrar_venta_lote()

    # RF-42: se registra el pago con su forma de pago (en credito todavia no se ha pagado nada)
    nuevo_pago = Pago(len(pagos_registrados) + 1,
                      0.0 if forma_pago == "credito" else precio_final,
                      nueva_venta.fecha, forma_pago)
    nuevo_pago.id_venta = id_venta
    nuevo_pago.seleccionar_forma_pago(forma_pago)
    nuevo_pago.registrar_pago()

    # RF-41: se genera la factura del lote vendido
    nueva_venta.generar_factura()

    ganancia_del_lote = lote.calcular_ganancia_lote()
    if ganancia_del_lote is not None:
        ganancia_general_acumulada += ganancia_del_lote  # RF-22

    registrar_auditoria(f"Registro de venta del lote {id_lote} por ${precio_final:,.0f}")
    return nueva_venta, None


def consultar_ventas_por_comprador(documento):
    """RF-16"""
    comprador = next((c for c in compradores_registrados if c.documento == documento), None)
    if comprador is None:
        return []
    return [v for v in ventas_registradas if v.id_comprador == comprador.id_comprador]


def consultar_ventas_por_animal(registro_ica):
    """RF-17: una venta es por lote, asi que se devuelven las ventas del
    lote al que pertenece el animal con ese registro ICA."""
    for lote in lotes_registrados:
        for animal in lote.animales:
            if animal.registro_ica == registro_ica:
                return [v for v in ventas_registradas if v.id_lote == lote.id_lote]
    return []


def consultar_ventas_por_lote(id_lote):
    """RF-18"""
    return [v for v in ventas_registradas if v.id_lote == id_lote]


def calcular_ganancia_general():
    """RF-21: ganancia general acumulada de todas las jornadas."""
    return ganancia_general_acumulada


def registrar_abono(id_abono, id_venta, monto, fecha=None):
    """RF-43: registra un pago parcial en una venta a credito."""
    venta = next((v for v in ventas_registradas if v.id_venta == id_venta), None)
    if venta is None:
        return None, "No existe una venta con ese ID."

    if venta.forma_pago != "credito":
        return None, "Solo se pueden registrar abonos en ventas a credito."

    if monto <= 0:
        return None, "El monto del abono debe ser mayor a cero."

    saldo = venta.consultar_saldo_pendiente()
    if saldo <= 0:
        return None, "Esta venta ya no tiene saldo pendiente."

    if monto > saldo:
        return None, f"El abono no puede superar el saldo pendiente de ${saldo:,.0f}."

    nuevo_abono = Abono(id_abono, monto, fecha or date.today(), saldo)
    nuevo_abono.id_venta = id_venta
    correcto, error = nuevo_abono.registrar_abono()
    if not correcto:
        return None, error

    nuevo_abono.actualizar_saldo_pendiente()
    return nuevo_abono, None


def consultar_saldos_pendientes():
    """RF-44: devuelve las ventas a credito que aun tienen saldo pendiente."""
    alertas = []
    for venta in ventas_registradas:
        if venta.forma_pago != "credito":
            continue
        saldo = venta.consultar_saldo_pendiente()
        if saldo <= 0:
            continue
        comprador = next((c for c in compradores_registrados
                          if c.id_comprador == venta.id_comprador), None)
        nombre = comprador.nombre if comprador else "Comprador no registrado"
        alertas.append({
            "id_venta": venta.id_venta,
            "id_comprador": venta.id_comprador,
            "comprador": nombre,
            "saldo_pendiente": saldo
        })
    return alertas


def alertar_saldos_pendientes():
    """RF-44: prepara el mensaje de alerta que puede mostrar la interfaz."""
    alertas = consultar_saldos_pendientes()
    if not alertas:
        return "No hay compradores con saldo pendiente."
    lineas = ["COMPRADORES CON SALDO PENDIENTE"]
    for alerta in alertas:
        lineas.append(
            f"{alerta['comprador']} - Venta #{alerta['id_venta']}: "
            f"${alerta['saldo_pendiente']:,.0f}")
    return "\n".join(lineas)


def generar_estadisticas_ventas_por_tipo():
    """RF-45: devuelve cantidad y valor vendido por ternero, novilla y vaca."""
    resultado = {}
    for tipo in ["ternero", "novilla", "vaca"]:
        reporte = ReporteVentasPorTipoAnimal(
            len(lotes_registrados) + len(ventas_registradas) + 1, tipo)
        reporte.generar_reporte()
        resultado[tipo] = {
            "cantidad_ventas": reporte.cantidad_ventas,
            "total_ventas": reporte.total_ventas
        }
    return resultado


def generar_estadisticas_ganancia_por_jornada():
    """RF-46: compara la ganancia acumulada de lunes, miercoles y sabado."""
    reporte = ReporteGananciaComparativaPorJornada(
        len(lotes_registrados) + len(jornadas_registradas) + 1)
    return reporte.comparar_ganancias()


def generar_reporte_mensual(mes, anio):
    """RF-47: genera el reporte consolidado mensual."""
    reporte = ReporteMensualGanancias(
        len(lotes_registrados) + len(jornadas_registradas) + 1, mes, anio)
    return reporte.generar_reporte(), reporte


def generar_reporte_anual(anio):
    """RF-47: genera el reporte consolidado anual."""
    reporte = ReporteAnualGanancias(
        len(lotes_registrados) + len(jornadas_registradas) + 1, anio)
    return reporte.generar_reporte(), reporte


# RESPALDO Y RESTAURACION (RF-48 y RF-49)
#
# Formato del archivo: .pkl con un diccionario (version 1). Se guarda de
# forma segura (archivo temporal + verificacion + reemplazo) y se restaura
# de forma atomica: primero se lee y se valida TODO, y solo si esta correcto
# se reemplazan los datos; si algo falla, el sistema queda como estaba.

# Clases que pueden aparecer dentro de una copia de seguridad. Al restaurar
# solo se reconstruyen estas (nada mas), asi un archivo ajeno o manipulado no
# puede ejecutar codigo. No se crea ninguna clase nueva: el diagrama tiene 24.
CLASES_EN_RESPALDO = ("Lote", "Animal", "Jornada", "Comprador", "Proveedor", "Puja",
                      "Auditoria", "Venta", "Pago", "Abono", "Factura",
                      "Usuario", "Administrador", "Registrador", "Consulta")


def _lista_global(nombre):
    return globals()[nombre]


def _listas_de_respaldo():
    """(nombre de la lista global, clase de sus elementos) de cada lista que se respalda."""
    return (("lotes_registrados", Lote), ("jornadas_registradas", Jornada),
            ("compradores_registrados", Comprador), ("ventas_registradas", Venta),
            ("usuarios_registrados", Usuario), ("proveedores_registrados", Proveedor),
            ("pujas_registradas", Puja), ("auditorias_registradas", Auditoria),
            ("facturas_registradas", Factura), ("pagos_registrados", Pago))


def _datos_para_respaldo():
    """Construye un snapshot sin incluir la propia lista de respaldos."""
    return {
        "version": 1,
        "lotes_registrados": lotes_registrados,
        "icas_registrados": icas_registrados,
        "jornadas_registradas": jornadas_registradas,
        "compradores_registrados": compradores_registrados,
        "ventas_registradas": ventas_registradas,
        "usuarios_registrados": usuarios_registrados,
        "proveedores_registrados": proveedores_registrados,
        "pujas_registradas": pujas_registradas,
        "auditorias_registradas": auditorias_registradas,
        "facturas_registradas": facturas_registradas,
        "pagos_registrados": pagos_registrados,
        "abonos_registrados": abonos_registrados,
        "ganancia_general_acumulada": ganancia_general_acumulada,
        "rango_animales": dict(RANGO_ANIMALES),
    }


def _cargar_respaldo_seguro(ruta_archivo):
    """Lee un .pkl reconstruyendo SOLO las clases del sistema (funciona sin
    importar con que nombre se ejecuto el programa: __main__, un modulo, un .exe)."""
    def buscar_clase(modulo, nombre):
        if modulo == "datetime" and nombre == "date":
            return date
        if modulo == "datetime" and nombre == "datetime":
            return datetime
        if modulo == "builtins" and nombre in ("set", "frozenset"):
            return {"set": set, "frozenset": frozenset}[nombre]
        if nombre in CLASES_EN_RESPALDO:
            return globals()[nombre]
        raise pickle.UnpicklingError(f"Contenido no permitido en la copia: {modulo}.{nombre}")

    cargador = type("CargadorSeguro", (pickle.Unpickler,),
                    {"find_class": lambda self, modulo, nombre: buscar_clase(modulo, nombre)})
    with open(ruta_archivo, "rb") as archivo:
        return cargador(archivo).load()


def _validar_datos_respaldo(datos):
    """Devuelve un mensaje de error si la copia esta incompleta o danada, o None si esta bien."""
    if not isinstance(datos, dict):
        return "El archivo no es una copia de seguridad valida."

    if datos.get("version") != 1:
        return "La version del respaldo no es compatible con este sistema."

    for nombre, clase in _listas_de_respaldo():
        lista = datos.get(nombre)
        if not isinstance(lista, list):
            return f"La copia esta incompleta o danada (falta '{nombre}')."
        if not all(isinstance(elemento, clase) for elemento in lista):
            return f"La copia esta danada: '{nombre}' contiene datos invalidos."

    icas = datos.get("icas_registrados")
    if not isinstance(icas, list) or not all(isinstance(i, str) for i in icas):
        return "La copia esta incompleta o danada (registros ICA)."

    abonos = datos.get("abonos_registrados", [])
    if not isinstance(abonos, list) or not all(isinstance(a, Abono) for a in abonos):
        return "La copia esta danada: 'abonos_registrados' contiene datos invalidos."

    ganancia = datos.get("ganancia_general_acumulada")
    if isinstance(ganancia, bool) or not isinstance(ganancia, (int, float)):
        return "La copia esta incompleta o danada (ganancia general)."

    rango = datos.get("rango_animales")
    if (not isinstance(rango, dict)
            or isinstance(rango.get("minimo"), bool) or not isinstance(rango.get("minimo"), int)
            or isinstance(rango.get("maximo"), bool) or not isinstance(rango.get("maximo"), int)
            or rango["minimo"] < 1 or rango["maximo"] < rango["minimo"]):
        return "La copia esta incompleta o danada (rango de animales)."

    return None


def _tomar_foto_del_estado():
    """Copia del estado actual, para poder deshacer si la restauracion falla a medias."""
    foto = {nombre: list(_lista_global(nombre)) for nombre, _ in _listas_de_respaldo()}
    foto["icas_registrados"] = list(icas_registrados)
    foto["abonos_registrados"] = list(abonos_registrados)
    foto["ganancia_general_acumulada"] = ganancia_general_acumulada
    foto["rango_animales"] = dict(RANGO_ANIMALES)
    return foto


def _aplicar_datos(datos):
    """Reemplaza el estado actual por 'datos' (modifica las listas en su sitio)."""
    global ganancia_general_acumulada
    for nombre, _ in _listas_de_respaldo():
        _lista_global(nombre)[:] = datos[nombre]
    icas_registrados[:] = datos["icas_registrados"]
    abonos_registrados[:] = datos.get("abonos_registrados", [])
    ganancia_general_acumulada = datos["ganancia_general_acumulada"]
    RANGO_ANIMALES["minimo"] = datos["rango_animales"]["minimo"]
    RANGO_ANIMALES["maximo"] = datos["rango_animales"]["maximo"]


def _siguiente_id_respaldo():
    ids = [r.id_respaldo for r in respaldos_registrados]
    return (max(ids) + 1) if ids else 1


def descubrir_respaldos_en_disco():
    """Agrega a la lista las copias .pkl que ya estan guardadas en la carpeta
    'reportes' (por ejemplo, hechas en una sesion anterior), para poder
    restaurarlas desde la lista sin buscar el archivo a mano."""
    carpeta = _carpeta_reportes()
    try:
        nombres = sorted(os.listdir(carpeta))
    except OSError:
        return []

    conocidas = {os.path.abspath(r.ruta_archivo) for r in respaldos_registrados if r.ruta_archivo}
    nuevos = []
    for nombre in nombres:
        if not (nombre.startswith("respaldo_") and nombre.endswith(".pkl")):
            continue
        ruta = os.path.abspath(os.path.join(carpeta, nombre))
        if ruta in conocidas:
            continue
        coincide = re.match(r"respaldo_(\d+)_", nombre)
        id_respaldo = int(coincide.group(1)) if coincide else None
        if id_respaldo is None or any(r.id_respaldo == id_respaldo for r in respaldos_registrados):
            id_respaldo = _siguiente_id_respaldo()
        try:
            fecha = date.fromtimestamp(os.path.getmtime(ruta))
        except OSError:
            fecha = date.today()
        respaldo = Respaldo(id_respaldo, fecha, ruta)
        respaldos_registrados.append(respaldo)
        conocidas.add(ruta)
        nuevos.append(respaldo)

    respaldos_registrados.sort(key=lambda r: r.id_respaldo)
    return nuevos


def realizar_respaldo(id_respaldo=None, fecha=None, ruta_archivo=""):
    """RF-48: crea una copia de seguridad completa en formato PKL.
    Se escribe primero en un archivo temporal, se verifica leyendola de
    nuevo y solo entonces se guarda con su nombre definitivo; asi nunca
    queda una copia a medias ni se sobreescribe otra copia anterior."""
    if fecha is None:
        fecha = date.today()
    ahora = datetime.now()

    if id_respaldo is None:
        descubrir_respaldos_en_disco()
        id_respaldo = _siguiente_id_respaldo()

    try:
        if not ruta_archivo:
            base = os.path.join(_carpeta_reportes(),
                                f"respaldo_{id_respaldo}_{fecha:%Y%m%d}_{ahora:%H%M%S}")
            ruta_archivo = base + ".pkl"
            repeticion = 2
            while os.path.exists(ruta_archivo):   # nunca pisa una copia que ya existe
                ruta_archivo = f"{base}_{repeticion}.pkl"
                repeticion += 1

        ruta_archivo = os.path.abspath(ruta_archivo)
        os.makedirs(os.path.dirname(ruta_archivo), exist_ok=True)
    except OSError as error:
        return None, f"No fue posible preparar la carpeta de la copia de seguridad: {error}"

    temporal = ruta_archivo + ".tmp"
    try:
        datos = _datos_para_respaldo()
        with open(temporal, "wb") as archivo:
            pickle.dump(datos, archivo, protocol=4)
            archivo.flush()
            os.fsync(archivo.fileno())

        # Verificacion: se lee de nuevo y se comprueba que quedo completa
        leido = _cargar_respaldo_seguro(temporal)
        error_validacion = _validar_datos_respaldo(leido)
        if error_validacion:
            raise ValueError(error_validacion)
        for nombre, _ in _listas_de_respaldo():
            if len(leido[nombre]) != len(datos[nombre]):
                raise ValueError(f"la copia no quedo completa ('{nombre}')")
        if leido["ganancia_general_acumulada"] != datos["ganancia_general_acumulada"]:
            raise ValueError("la copia no quedo completa (ganancia general)")

        os.replace(temporal, ruta_archivo)
    except Exception as error:
        try:
            if os.path.exists(temporal):
                os.remove(temporal)
        except OSError:
            pass
        return None, f"No fue posible crear la copia de seguridad: {error}"

    respaldo = next((r for r in respaldos_registrados if r.id_respaldo == id_respaldo), None)
    if respaldo is None:
        respaldo = Respaldo(id_respaldo, fecha, ruta_archivo)
        respaldos_registrados.append(respaldo)
    else:
        respaldo.fecha = fecha
        respaldo.ruta_archivo = ruta_archivo

    registrar_auditoria(f"Copia de seguridad realizada: {ruta_archivo}")
    return respaldo, None


def restaurar_respaldo(id_respaldo):
    """RF-49: restaura la informacion desde una copia previamente creada."""
    respaldo = next((r for r in respaldos_registrados if r.id_respaldo == id_respaldo), None)
    if respaldo is None:
        return None, "No existe un respaldo con ese ID."
    return restaurar_informacion_desde_archivo(respaldo.ruta_archivo)


def restaurar_informacion_desde_archivo(ruta_archivo):
    """RF-49: carga la copia y reemplaza la informacion actual. Es atomica:
    si el archivo no existe, esta vacio, danado o incompleto, NO se cambia
    nada y se devuelve el motivo."""
    if not ruta_archivo or not os.path.isfile(ruta_archivo):
        return None, "No se encontro el archivo de respaldo."

    try:
        if os.path.getsize(ruta_archivo) == 0:
            return None, "El archivo de respaldo esta vacio."
        datos = _cargar_respaldo_seguro(ruta_archivo)
    except Exception as error:
        return None, f"No fue posible restaurar el respaldo (archivo danado o no valido): {error}"

    error_validacion = _validar_datos_respaldo(datos)
    if error_validacion:
        return None, error_validacion

    foto = _tomar_foto_del_estado()
    try:
        _aplicar_datos(datos)
    except Exception as error:
        _aplicar_datos(foto)   # deshacer: el sistema queda como estaba
        return None, f"No fue posible restaurar el respaldo: {error}"

    # La sesion actual apunta al usuario restaurado con el mismo nombre de usuario (si existe)
    usuario_en_sesion = sesion_actual["usuario"]
    if usuario_en_sesion is not None:
        equivalente = next((u for u in usuarios_registrados
                            if u.usuario == usuario_en_sesion.usuario), None)
        if equivalente is not None:
            sesion_actual["usuario"] = equivalente

    registrar_auditoria(f"Restauracion de copia de seguridad: {ruta_archivo}")
    return True, None


def notificar_cierre_jornada(jornada):
    """RF-50: en la version web el aviso se muestra con un mensaje en pantalla."""
    return True


def registrar_usuario(id_usuario, nombre, usuario, contrasena, rol):
    """RF-26: crea una cuenta de usuario con un rol diferenciado
    (administrador, registrador o consulta)."""
    # RF-28: una vez que existe algun usuario, solo un administrador con la
    # sesion iniciada puede crear cuentas (evita que alguien se de permisos).
    if usuarios_registrados:
        autorizado, error_acceso = verificar_autorizacion(["administrador"])
        if not autorizado:
            return None, error_acceso

    if not usuario or not contrasena:
        return None, "Debes escribir el usuario y la contraseña."

    if any(u.usuario == usuario for u in usuarios_registrados):
        return None, "Ese nombre de usuario ya existe."

    if any(u.id_usuario == id_usuario for u in usuarios_registrados):
        return None, f"Ya existe un usuario con el ID {id_usuario}."

    rol_normalizado = (rol or "").strip().lower()

    # Arranque del sistema: la primera cuenta tiene que ser de administrador.
    if not usuarios_registrados and rol_normalizado != "administrador":
        return None, "La primera cuenta del sistema debe ser de administrador."

    if rol_normalizado == "administrador":
        nuevo_usuario = Administrador(id_usuario, nombre, usuario, contrasena)
    elif rol_normalizado == "registrador":
        nuevo_usuario = Registrador(id_usuario, nombre, usuario, contrasena)
    elif rol_normalizado == "consulta":
        nuevo_usuario = Consulta(id_usuario, nombre, usuario, contrasena)
    else:
        return None, "El rol debe ser administrador, registrador o consulta."

    usuarios_registrados.append(nuevo_usuario)
    registrar_auditoria(f"Creacion del usuario '{usuario}' con rol '{rol_normalizado}'")
    return nuevo_usuario, None


def iniciar_sesion(usuario, contrasena):
    """RF-27"""
    encontrado = next((u for u in usuarios_registrados if u.usuario == usuario), None)
    if encontrado is None:
        return None, "No existe un usuario con ese nombre."

    if not encontrado.iniciar_sesion(usuario, contrasena):
        return None, "Usuario o contraseña incorrectos."

    sesion_actual["usuario"] = encontrado
    return encontrado, None


def cerrar_sesion():
    sesion_actual["usuario"] = None


def verificar_autorizacion(roles_permitidos, permitir_sin_usuarios=False):
    """RF-28: restringe el acceso a las funciones de registro y edicion
    solo a usuarios autorizados con uno de los roles indicados."""
    usuario = sesion_actual["usuario"]
    if usuario is None:
        # Arranque: si todavia no existe ningun usuario, se permite (solo
        # para restaurar una copia de seguridad en un sistema vacio).
        if permitir_sin_usuarios and not usuarios_registrados:
            return True, None
        return False, "Debes iniciar sesión para realizar esta acción."
    if usuario.rol not in roles_permitidos:
        return False, f"Tu rol ('{usuario.rol}') no tiene permiso para realizar esta acción."
    return True, None


def registrar_auditoria(operacion):
    """RF-29: registra que usuario realizo cada operacion de registro o
    edicion, para dejar trazabilidad (auditoria) de la actividad del
    sistema. Se llama automaticamente desde las demas funciones de
    registro/edicion; no requiere que el usuario haga nada aparte."""
    usuario_activo = sesion_actual["usuario"]
    nombre_usuario = (usuario_activo.nombre or usuario_activo.usuario) if usuario_activo else "Sistema"

    id_auditoria = len(auditorias_registradas) + 1
    nuevo_registro = Auditoria(id_auditoria, operacion, datetime.now(), nombre_usuario)
    auditorias_registradas.append(nuevo_registro)
    return nuevo_registro


def registrar_proveedor(id_proveedor, nombre, documento, telefono, finca, id_lote):
    """RF-30: registra los datos del vendedor/proveedor de un lote (nombre,
    identificacion y finca de procedencia) y lo asocia a ese lote."""
    if not nombre:
        return None, "Debes escribir el nombre del proveedor."

    if not documento:
        return None, "Debes escribir el documento del proveedor."

    if not finca:
        return None, "Debes escribir la finca de procedencia."

    lote = next((l for l in lotes_registrados if l.id_lote == id_lote), None)
    if lote is None:
        return None, "No existe un lote con ese numero."

    nuevo_proveedor = Proveedor(id_proveedor, nombre, documento, telefono, finca, id_lote)
    proveedores_registrados.append(nuevo_proveedor)
    lote.proveedor = nuevo_proveedor

    registrar_auditoria(f"Registro del proveedor '{nombre}' para el lote {id_lote}")
    return nuevo_proveedor, None


def _validar_lote_para_subasta(lote):
    """Reglas comunes para poder subastar un lote (RF-34 y RF-35): no
    vendido, jornada abierta y con TODOS sus animales registrados (sin el
    peso total no se puede calcular el precio total del lote)."""
    if lote.estado == "vendido":
        return "Este lote ya fue vendido; no se puede subastar de nuevo."

    if not lote.jornada_esta_abierta():
        return "La jornada de este lote ya fue cerrada."

    if not lote.esta_completo():
        return (f"Este lote debe tener sus {lote.cantidad_animales} animales registrados antes de "
                f"subastarse (llevas {len(lote.animales)}; faltan {lote.cantidad_animales_faltantes()}). "
                f"Sin el peso total no se puede calcular el precio del lote.")
    return None


def establecer_precio_salida(id_lote, precio_salida_kg, incremento_minimo_kg=None):
    """RF-34: registra el precio de salida (minimo por kilo) de un lote
    antes de la subasta, y opcionalmente el incremento minimo por kilo
    entre pujas (RF-35)."""
    lote = next((l for l in lotes_registrados if l.id_lote == id_lote), None)
    if lote is None:
        return None, "No existe un lote con ese numero."

    error = _validar_lote_para_subasta(lote)
    if error:
        return None, error

    if precio_salida_kg <= 0:
        return None, "El precio de salida por kilo debe ser mayor a cero."

    if incremento_minimo_kg is not None and incremento_minimo_kg <= 0:
        return None, "El incremento minimo por kilo debe ser mayor a cero."

    if not lote.establecer_precio_salida(precio_salida_kg, incremento_minimo_kg):
        return None, "Este lote ya tiene pujas registradas; no se puede cambiar su precio de salida."

    registrar_auditoria(
        f"Precio de salida del lote {id_lote}: ${precio_salida_kg:,.0f}/kg "
        f"(total ${lote.precio_salida_total():,.0f})")
    return lote, None


def registrar_puja(id_puja, id_lote, valor_kg):
    """RF-35: registra una puja (en $/kg) durante la subasta de un lote.
    La primera puja debe ser al menos el precio de salida (RF-34); cada
    puja siguiente debe superar a la anterior por al menos el incremento
    minimo por kilo del lote."""
    lote = next((l for l in lotes_registrados if l.id_lote == id_lote), None)
    if lote is None:
        return None, "No existe un lote con ese numero."

    error = _validar_lote_para_subasta(lote)
    if error:
        return None, error

    if lote.precio_salida_kg is None:
        return None, "Primero debes establecer el precio de salida del lote."

    if valor_kg <= 0:
        return None, "El valor de la puja por kilo debe ser mayor a cero."

    minima = lote.puja_minima_kg()
    if valor_kg < minima:
        if lote.pujas:
            detalle = (f"la ultima puja (${lote.pujas[-1].valor:,.0f}/kg) mas el incremento "
                       f"minimo (${lote.incremento_minimo_kg:,.0f}/kg)")
        else:
            detalle = "el precio de salida del lote"
        return None, f"La puja debe ser de al menos ${minima:,.0f}/kg ({detalle})."

    nueva_puja = Puja(id_puja, valor_kg, datetime.now(), id_lote)
    lote.pujas.append(nueva_puja)
    pujas_registradas.append(nueva_puja)

    registrar_auditoria(
        f"Puja de ${valor_kg:,.0f}/kg (total ${valor_kg * lote.peso_total_kg():,.0f}) "
        f"registrada para el lote {id_lote}")
    return nueva_puja, None


def determinar_puja_ganadora(id_lote):
    """Apoyo a RF-35: la puja ganadora de un lote es la ultima (la mas
    alta, ya que cada puja debe superar a la anterior) registrada para
    ese lote."""
    lote = next((l for l in lotes_registrados if l.id_lote == id_lote), None)
    if lote is None:
        return None, "No existe un lote con ese numero."

    if not lote.pujas:
        return None, "Este lote todavia no tiene pujas registradas."

    for puja in lote.pujas:
        puja.es_ganadora = False

    puja_ganadora = lote.pujas[-1]
    puja_ganadora.es_ganadora = True
    registrar_auditoria(f"Puja ganadora del lote {id_lote}: ${puja_ganadora.valor:,.0f}/kg")
    return puja_ganadora, None


def configurar_rango_animales(minimo, maximo):
    """RF-36: el administrador define el minimo y maximo de animales por lote."""
    if minimo < 1:
        return None, "El minimo de animales por lote debe ser al menos 1."
    if maximo < minimo:
        return None, "El maximo no puede ser menor que el minimo."

    RANGO_ANIMALES["minimo"] = minimo
    RANGO_ANIMALES["maximo"] = maximo
    registrar_auditoria(f"Rango de animales por lote configurado: {minimo} a {maximo}")
    return dict(RANGO_ANIMALES), None


def _normalizar_texto(texto):
    """Minusculas, sin espacios sobrantes y sin tildes, para que 'Perez'
    encuentre 'Pérez' al buscar."""
    descompuesto = unicodedata.normalize("NFD", texto or "")
    sin_tildes = "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")
    return sin_tildes.strip().lower()


def lotes_comprados_por_documento(documento):
    """Lotes VENDIDOS a la persona con ese documento (una persona puede
    comprar varios lotes, y cada compra deja un registro Comprador)."""
    lotes = []
    for comprador in compradores_registrados:
        if comprador.documento != documento:
            continue
        lote = next((l for l in lotes_registrados if l.id_lote == comprador.id_lote), None)
        if lote is not None and lote.estado == "vendido" and lote not in lotes:
            lotes.append(lote)
    return lotes


def consultar_compradores():
    """RF-37: lista completa de compradores registrados. Cada persona
    aparece UNA sola vez (identificada por su documento), aunque haya
    comprado varios lotes."""
    unicos = {}
    for comprador in compradores_registrados:
        if comprador.documento not in unicos:
            unicos[comprador.documento] = comprador
    return list(unicos.values())


def buscar_animal_por_ica(registro_ica):
    """RF-38: devuelve (animal, lote) del animal con ese ICA, o (None, None)."""
    buscado = registro_ica.strip().lower()
    for lote in lotes_registrados:
        for animal in lote.animales:
            if animal.registro_ica.strip().lower() == buscado:
                return animal, lote
    return None, None


def buscar_lotes_por_rango_fechas(fecha_inicio, fecha_fin):
    """RF-39: lotes cuya fecha de registro cae dentro del rango (inclusive)."""
    return [l for l in lotes_registrados if fecha_inicio <= l.fecha_registro <= fecha_fin]


def buscar_lotes_por_comprador(texto):
    """RF-40: lotes VENDIDOS a los compradores que coincidan con el texto:
    el documento (completo o parte de el) o el nombre (sin distinguir
    mayusculas ni tildes)."""
    buscado = _normalizar_texto(texto)
    if not buscado:
        return []

    resultado = []
    for comprador in compradores_registrados:
        coincide = (buscado in _normalizar_texto(comprador.documento)
                    or buscado in _normalizar_texto(comprador.nombre))
        if not coincide:
            continue
        lote = next((l for l in lotes_registrados if l.id_lote == comprador.id_lote), None)
        if lote is not None and lote.estado == "vendido" and lote not in resultado:
            resultado.append(lote)
    return resultado
