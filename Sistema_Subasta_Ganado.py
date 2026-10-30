
import os
import sys
import unicodedata
import pickle
import re
from datetime import date, datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    from tkcalendar import DateEntry
except ImportError:
    import sys
    print("Este programa requiere la libreria 'tkcalendar'. Instalala con: pip install tkcalendar")
    sys.exit(1)





COLOR_FONDO = "#f3f4f7"          # fondo general del área de contenido
COLOR_PANEL = "#ffffff"          # tarjetas, tabla, listas
COLOR_BORDE = "#e4e6ec"          # bordes sutiles en reposo
COLOR_BORDE_FOCO = "#059669"     # borde al enfocar un campo (= acento)
COLOR_TEXTO = "#13151a"          # texto principal
COLOR_TEXTO_SUAVE = "#5b6170"    # texto secundario / etiquetas
COLOR_TEXTO_TENUE = "#98a0ac"    # texto terciario / ayudas
COLOR_HOVER = "#eef1f0"          # hover neutro sobre superficies claras

COLOR_ACENTO = "#059669"         # esmeralda — color de marca
COLOR_ACENTO_HOVER = "#047857"   # acento en hover / presionado
COLOR_ACENTO_TEXTO = "#ffffff"   # texto sobre el color de acento
COLOR_ACENTO_SUAVE = "#e6f6ef"   # fondo tenue con tinte de acento (selección)
COLOR_ALERTA = "#dc2626"         # estados cerrados / negativos
COLOR_ALERTA_SUAVE = "#fdeded"   # fondo tenue de alerta


COLOR_SIDEBAR = "#13151c"
COLOR_SIDEBAR_BORDE = "#22252f"
COLOR_SIDEBAR_TEXTO = "#8d93a3"
COLOR_SIDEBAR_TEXTO_ACTIVO = "#ffffff"
COLOR_SIDEBAR_HOVER = "#1d2028"
COLOR_SIDEBAR_ACTIVO = "#182620"

FUENTE_FAMILIA = "Segoe UI"
FUENTE_BASE = (FUENTE_FAMILIA, 10)
FUENTE_BASE_BOLD = (FUENTE_FAMILIA, 10, "bold")
FUENTE_ETIQUETA = (FUENTE_FAMILIA, 8, "bold")
FUENTE_AYUDA = (FUENTE_FAMILIA, 8)
FUENTE_NAV = (FUENTE_FAMILIA, 10)
FUENTE_NAV_BOLD = (FUENTE_FAMILIA, 10, "bold")
FUENTE_NAV_ICONO = (FUENTE_FAMILIA, 12)
FUENTE_TITULO = (FUENTE_FAMILIA, 23, "bold")
FUENTE_SUBTITULO = (FUENTE_FAMILIA, 10)
FUENTE_MARCA = (FUENTE_FAMILIA, 13, "bold")
FUENTE_MARCA_SUB = (FUENTE_FAMILIA, 8)

ESPACIO_SECCION = 28


ICONOS_MENU = {
    "INICIAR SESIÓN": "⏻",
    "USUARIOS": "◍",
    "JORNADAS": "▤",
    "LOTES": "▣",
    "EDITAR LOTE": "✎",
    "ANIMALES": "◈",
    "LISTA DE LOTES": "☰",
    "FILTRAR": "▾",
    "CONSULTAR JORNADAS": "⌕",
    "VENDER LOTE": "⇄",
    "HISTORIAL VENTAS": "◷",
    "GENERAR REPORTES": "▦",
    "GANANCIAS": "▲",
    "PROVEEDORES": "⚑",
    "SUBASTA EN VIVO": "⚡",
    "AUDITORÍA": "▥",
    "CONFIGURAR RANGO": "⚙",
    "COMPRADORES": "◉",
    "BUSCAR ANIMAL": "⌕",
    "LOTES POR FECHAS": "◷",
    "LOTES POR COMPRADOR": "⇄",
    "FACTURAS": "▦",
    "ABONOS": "◐",
    "RESPALDO": "⟳",
}





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
    """RF-50: muestra en pantalla el cierre de la jornada."""
    messagebox.showinfo(
        "Jornada cerrada",
        f"La jornada {jornada.id_jornada} ({jornada.dia_semana}) ha sido cerrada correctamente.\n"
        "Sus lotes ya no se pueden editar.")
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


def crear_campo(parent, etiqueta_texto, fila, columna, placeholder=""):
    """Crea una etiqueta en mayusculas + una caja de texto minimalista, con
    resalte sutil del borde al enfocar (estado 'foco' profesional)."""

    tk.Label(
        parent, text=etiqueta_texto.upper(), font=FUENTE_ETIQUETA,
        bg=COLOR_FONDO, fg=COLOR_TEXTO_SUAVE
    ).grid(row=fila, column=columna, sticky="w", padx=10, pady=(0, 7))

    entry = tk.Entry(
        parent, font=FUENTE_BASE, bg=COLOR_PANEL, fg=COLOR_TEXTO,
        insertbackground=COLOR_ACENTO, relief="flat",
        highlightthickness=2, highlightbackground=COLOR_BORDE,
        highlightcolor=COLOR_BORDE_FOCO, bd=0
    )
    entry.grid(row=fila + 1, column=columna, sticky="ew", padx=10, ipady=9)

    entry.placeholder = placeholder  # lo usa valor_campo() para distinguirlo de lo escrito por el usuario

    if placeholder:
        entry.insert(0, placeholder)
        entry.config(fg=COLOR_TEXTO_SUAVE)

        def al_enfocar(evento, e=entry, ph=placeholder):
            if e.get() == ph:
                e.delete(0, tk.END)
                e.config(fg=COLOR_TEXTO)

        def al_perder_foco(evento, e=entry, ph=placeholder):
            if e.get().strip() == "":
                e.insert(0, ph)
                e.config(fg=COLOR_TEXTO_SUAVE)

        entry.bind("<FocusIn>", al_enfocar)
        entry.bind("<FocusOut>", al_perder_foco)

    return entry


def valor_campo(entry):
    """Texto que el usuario realmente escribio en un campo creado con
    crear_campo(). Si el campo todavia muestra solo el texto de ejemplo
    (placeholder), devuelve '' para que no se guarde como si fuera un dato."""
    texto = entry.get().strip()
    if texto and texto == getattr(entry, "placeholder", None):
        return ""
    return texto


def crear_campo_solo_digitos(parent, etiqueta_texto, fila, columna, longitud_maxima, placeholder=""):
    """Igual que crear_campo, pero bloquea cualquier tecla que no sea un
    digito y no deja escribir mas de 'longitud_maxima' caracteres (para
    documento de identidad y telefono: 10 digitos exactos como maximo).
    El bloqueo ocurre en el momento en que se escribe (validate='key'),
    no despues de guardar."""
    entry = crear_campo(parent, etiqueta_texto, fila, columna, placeholder=placeholder)

    def solo_digitos(texto_propuesto):
        # se permite vaciar el campo o dejar el placeholder tal cual
        # (asi el placeholder con letras no rompe la validacion)
        if texto_propuesto == "" or texto_propuesto == placeholder:
            return True
        return texto_propuesto.isdigit() and len(texto_propuesto) <= longitud_maxima

    vcmd = (entry.register(solo_digitos), "%P")
    entry.config(validate="key", validatecommand=vcmd)
    return entry


def crear_selector_fecha(parent, etiqueta_texto, fila, columna):
    """Etiqueta en mayusculas + selector de fecha con calendario emergente.
    El usuario elige la fecha del lote; ya no se asume la fecha del dia actual."""

    tk.Label(
        parent, text=etiqueta_texto.upper(), font=FUENTE_ETIQUETA,
        bg=COLOR_FONDO, fg=COLOR_TEXTO_SUAVE
    ).grid(row=fila, column=columna, sticky="w", padx=10, pady=(0, 7))

    selector = DateEntry(
        parent, font=FUENTE_BASE, date_pattern="yyyy-mm-dd",
        background=COLOR_ACENTO, foreground=COLOR_ACENTO_TEXTO,
        headersbackground=COLOR_ACENTO, headersforeground=COLOR_ACENTO_TEXTO,
        selectbackground=COLOR_ACENTO, normalbackground=COLOR_PANEL,
        weekendbackground=COLOR_PANEL, bordercolor=COLOR_BORDE,
        borderwidth=1, locale="es"
    )
    selector.grid(row=fila + 1, column=columna, sticky="ew", padx=10, ipady=5)
    return selector


def crear_combo(parent, etiqueta_texto, fila, columna, valores):
    """Etiqueta en mayusculas + combobox de solo lectura, con el mismo
    lenguaje visual que crear_campo para mantener coherencia."""

    tk.Label(
        parent, text=etiqueta_texto.upper(), font=FUENTE_ETIQUETA,
        bg=COLOR_FONDO, fg=COLOR_TEXTO_SUAVE
    ).grid(row=fila, column=columna, sticky="w", padx=10, pady=(0, 7))

    combo = ttk.Combobox(
        parent, values=valores, state="readonly",
        font=FUENTE_BASE, style="Claro.TCombobox"
    )
    combo.grid(row=fila + 1, column=columna, sticky="ew", padx=10, ipady=7)
    return combo


def _agregar_hover(widget, color_normal, color_hover):
    """Aplica un cambio de fondo sutil al pasar el mouse, sin depender de
    estilos ttk. Da una sensación 'viva' y profesional a los botones."""
    widget.bind("<Enter>", lambda e: widget.config(bg=color_hover))
    widget.bind("<Leave>", lambda e: widget.config(bg=color_normal))


def boton_principal(parent, texto, comando):
    """Boton de acento (verde sólido, texto blanco) para la acción principal
    de cada pantalla. Incluye estado hover."""
    boton = tk.Button(
        parent, text=texto.upper(), command=comando,
        bg=COLOR_ACENTO, fg=COLOR_ACENTO_TEXTO, font=FUENTE_BASE_BOLD,
        relief="flat", bd=0, padx=24, pady=12, cursor="hand2",
        activebackground=COLOR_ACENTO_HOVER, activeforeground=COLOR_ACENTO_TEXTO
    )
    _agregar_hover(boton, COLOR_ACENTO, COLOR_ACENTO_HOVER)
    return boton


def boton_secundario(parent, texto, comando):
    """Boton de acción secundaria (solo borde), para acciones de apoyo como
    'agregar' o 'cerrar'. Incluye estado hover."""
    boton = tk.Button(
        parent, text=texto.upper(), command=comando,
        bg=COLOR_PANEL, fg=COLOR_TEXTO, font=(FUENTE_FAMILIA, 9, "bold"),
        relief="flat", bd=0, padx=18, pady=10, cursor="hand2",
        highlightthickness=1, highlightbackground=COLOR_BORDE,
        activebackground=COLOR_HOVER, activeforeground=COLOR_TEXTO
    )
    _agregar_hover(boton, COLOR_PANEL, COLOR_HOVER)
    return boton


def boton_peligro(parent, texto, comando):
    """Boton de acción destructiva/negativa (borde y texto en color de
    alerta), para acciones como 'cerrar jornada'. Incluye estado hover."""
    boton = tk.Button(
        parent, text=texto.upper(), command=comando,
        bg=COLOR_PANEL, fg=COLOR_ALERTA, font=(FUENTE_FAMILIA, 9, "bold"),
        relief="flat", bd=0, padx=18, pady=10, cursor="hand2",
        highlightthickness=1, highlightbackground=COLOR_BORDE,
        activebackground=COLOR_ALERTA_SUAVE, activeforeground=COLOR_ALERTA
    )
    _agregar_hover(boton, COLOR_PANEL, COLOR_ALERTA_SUAVE)
    return boton


def chip_estado(parent, texto, tono="acento"):
    """Insignia de estado tipo 'pill' (fondo suave + texto en mayúsculas)
    para reemplazar las etiquetas de color planas y dar un lenguaje visual
    consistente y más moderno a los estados (abierto/cerrado/vendido...)."""
    colores = {
        "acento": (COLOR_ACENTO_SUAVE, COLOR_ACENTO),
        "alerta": (COLOR_ALERTA_SUAVE, COLOR_ALERTA),
        "neutro": (COLOR_HOVER, COLOR_TEXTO_SUAVE),
    }
    fondo, tinta = colores.get(tono, colores["neutro"])
    contenedor = tk.Frame(parent, bg=fondo)
    tk.Label(contenedor, text=texto.upper(), font=FUENTE_ETIQUETA,
             bg=fondo, fg=tinta, padx=10, pady=4).pack()
    return contenedor


def separador(parent, **pack_kwargs):
    """Línea horizontal delgada para dividir secciones sin recargar la
    interfaz con cuadros o sombras."""
    opciones = {"fill": "x", "pady": (0, ESPACIO_SECCION)}
    opciones.update(pack_kwargs)
    linea = tk.Frame(parent, bg=COLOR_BORDE, height=1)
    linea.pack(**opciones)
    return linea



# VENTANA PRINCIPAL


def crear_ventana_principal():

    def _inicializar(self):
        # La ventana `app` ya fue creada con tk.Tk() en la fábrica.
        # No se debe volver a ejecutar tk.Tk.__init__(self), porque eso
        # puede crear/reinicializar otra ventana raíz de Tk.
        self.title("Sistema de Control de Subastas de Ganado")
        self.geometry("1180x700")
        self.minsize(980, 600)
        self.configure(bg=COLOR_FONDO)

        self._configurar_estilos_ttk()

        # ---------------------------------------------------------------
        # BARRA SUPERIOR: marca del sistema a la izquierda, estado de la
        # sesión activa a la derecha (siempre visible, sin recargar la
        # pantalla). Blanca y limpia, para contrastar con la barra
        # lateral oscura y dar una jerarquía de panel de control moderno.
        # ---------------------------------------------------------------
        barra_superior = tk.Frame(self, bg=COLOR_PANEL, height=64,
                                   highlightthickness=0)
        barra_superior.pack(fill="x", side="top")
        barra_superior.pack_propagate(False)

        marca = tk.Frame(barra_superior, bg=COLOR_PANEL)
        marca.pack(side="left", padx=(28, 0), pady=14)
        insignia = tk.Frame(marca, bg=COLOR_ACENTO, width=34, height=34)
        insignia.pack(side="left", pady=1)
        insignia.pack_propagate(False)
        tk.Label(insignia, text="SG", bg=COLOR_ACENTO, fg=COLOR_ACENTO_TEXTO,
                 font=(FUENTE_FAMILIA, 11, "bold")).pack(expand=True)

        texto_marca = tk.Frame(marca, bg=COLOR_PANEL)
        texto_marca.pack(side="left", padx=(12, 0))
        tk.Label(texto_marca, text="SUBASTAS DE GANADO", bg=COLOR_PANEL, fg=COLOR_TEXTO,
                 font=FUENTE_MARCA, anchor="w").pack(anchor="w")
        tk.Label(texto_marca, text="Panel de control", bg=COLOR_PANEL, fg=COLOR_TEXTO_TENUE,
                 font=FUENTE_MARCA_SUB, anchor="w").pack(anchor="w")

        # --- indicador de sesión activa, a la derecha de la barra superior ---
        self.panel_sesion = tk.Frame(barra_superior, bg=COLOR_PANEL)
        self.panel_sesion.pack(side="right", padx=28)
        self.avatar_sesion = tk.Frame(self.panel_sesion, bg=COLOR_HOVER, width=32, height=32)
        self.avatar_sesion.pack(side="left")
        self.avatar_sesion.pack_propagate(False)
        self.label_avatar_sesion = tk.Label(self.avatar_sesion, text="?", bg=COLOR_HOVER,
                                             fg=COLOR_TEXTO_SUAVE, font=(FUENTE_FAMILIA, 10, "bold"))
        self.label_avatar_sesion.pack(expand=True)

        texto_sesion = tk.Frame(self.panel_sesion, bg=COLOR_PANEL)
        texto_sesion.pack(side="left", padx=(10, 0))
        self.label_sesion_nombre = tk.Label(texto_sesion, text="Sin sesión iniciada",
                                             bg=COLOR_PANEL, fg=COLOR_TEXTO, font=FUENTE_BASE_BOLD,
                                             anchor="w")
        self.label_sesion_nombre.pack(anchor="w")
        self.label_sesion_rol = tk.Label(texto_sesion, text="Inicia sesión para operar el sistema",
                                          bg=COLOR_PANEL, fg=COLOR_TEXTO_TENUE, font=FUENTE_AYUDA,
                                          anchor="w")
        self.label_sesion_rol.pack(anchor="w")

        separador(self, fill="x", pady=0)

        # --- contenedor principal: sidebar (izquierda) + contenido (derecha) ---
        contenedor = tk.Frame(self, bg=COLOR_FONDO)
        contenedor.pack(fill="both", expand=True)

        self.sidebar = tk.Frame(contenedor, bg=COLOR_SIDEBAR, width=232,
                                 highlightthickness=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        area_scroll_exterior = tk.Frame(contenedor, bg=COLOR_FONDO)
        area_scroll_exterior.pack(side="left", fill="both", expand=True)

        self.area_contenido = tk.Frame(area_scroll_exterior, bg=COLOR_FONDO)
        self.area_contenido.pack(side="left", fill="both", expand=True, padx=40, pady=30)

        # --- opciones de la barra lateral, agrupadas por flujo de trabajo:
        #     esto convierte una lista plana de 13 enlaces en una
        #     navegación con jerarquía clara, propia de un panel moderno ---
        self.grupos_menu = [
            ("CUENTA", [
                ("INICIAR SESIÓN", self.mostrar_pantalla_login),
                ("USUARIOS", self.mostrar_pantalla_usuarios),
                ("AUDITORÍA", self.mostrar_pantalla_auditoria),
                ("CONFIGURAR RANGO", self.mostrar_pantalla_configuracion),
                ("RESPALDO", self.mostrar_pantalla_respaldo),
            ]),
            ("SUBASTA", [
                ("JORNADAS", self.mostrar_pantalla_jornada),
                ("CONSULTAR JORNADAS", self.mostrar_pantalla_consultar_jornadas),
                ("LOTES", self.mostrar_pantalla_lote),
                ("EDITAR LOTE", self.mostrar_pantalla_editar_lote),
                ("ANIMALES", self.mostrar_pantalla_animal),
                ("PROVEEDORES", self.mostrar_pantalla_proveedor),
                ("SUBASTA EN VIVO", self.mostrar_pantalla_subasta_vivo),
            ]),
            ("CONSULTAS", [
                ("LISTA DE LOTES", self.mostrar_pantalla_reportes),
                ("FILTRAR", self.mostrar_pantalla_filtrar),
                ("COMPRADORES", self.mostrar_pantalla_lista_compradores),
                ("BUSCAR ANIMAL", self.mostrar_pantalla_buscar_animal),
                ("LOTES POR FECHAS", self.mostrar_pantalla_lotes_por_fechas),
                ("LOTES POR COMPRADOR", self.mostrar_pantalla_lotes_por_comprador),
            ]),
            ("VENTAS", [
                ("VENDER LOTE", self.mostrar_pantalla_comprador),
                ("HISTORIAL VENTAS", self.mostrar_pantalla_historial_ventas),
                ("FACTURAS", self.mostrar_pantalla_facturas),
                ("ABONOS", self.mostrar_pantalla_abonos),
            ]),
            ("REPORTES", [
                ("GENERAR REPORTES", self.mostrar_pantalla_generar_reportes),
                ("GANANCIAS", self.mostrar_pantalla_ganancias),
            ]),
        ]
        self.opciones_menu = [item for _, items in self.grupos_menu for item in items]

        # --- pie de la barra lateral: se ancla primero, abajo del todo,
        #     para que el área de navegación (con scroll propio) ocupe
        #     exactamente el espacio que sobra por encima de él ---
        tk.Frame(self.sidebar, bg=COLOR_SIDEBAR_BORDE, height=1).pack(fill="x", side="bottom")
        pie_sidebar = tk.Frame(self.sidebar, bg=COLOR_SIDEBAR)
        pie_sidebar.pack(fill="x", side="bottom", pady=14, padx=22)
        tk.Label(pie_sidebar, text="Sistema de Control · v1.0", bg=COLOR_SIDEBAR,
                 fg=COLOR_SIDEBAR_TEXTO, font=FUENTE_AYUDA, anchor="w").pack(anchor="w")

        # --- área de navegación CON SCROLL PROPIO: con 13 opciones agrupadas
        #     en 5 secciones, el menú puede llegar a ser más alto que la
        #     ventana (sobre todo si el usuario la achica). Envolverlo en un
        #     Canvas con scrollbar garantiza que SIEMPRE se pueda llegar a
        #     todas las opciones (incluidas GENERAR REPORTES y GANANCIAS al
        #     final), sin que ningún ítem quede oculto fuera de la vista. ---
        contenedor_nav = tk.Frame(self.sidebar, bg=COLOR_SIDEBAR)
        contenedor_nav.pack(fill="both", expand=True)

        canvas_nav = tk.Canvas(contenedor_nav, bg=COLOR_SIDEBAR, highlightthickness=0, bd=0)
        scrollbar_nav = tk.Scrollbar(
            contenedor_nav, orient="vertical", command=canvas_nav.yview,
            bg=COLOR_SIDEBAR, troughcolor=COLOR_SIDEBAR, bd=0, relief="flat",
            activebackground=COLOR_SIDEBAR_HOVER, width=8, elementborderwidth=0
        )
        canvas_nav.configure(yscrollcommand=scrollbar_nav.set)
        canvas_nav.pack(side="left", fill="both", expand=True)
        scrollbar_nav.pack(side="right", fill="y")

        panel_menu = tk.Frame(canvas_nav, bg=COLOR_SIDEBAR)
        ventana_menu = canvas_nav.create_window((0, 0), window=panel_menu, anchor="nw")

        def _region_scroll_menu(evento=None):
            canvas_nav.configure(scrollregion=canvas_nav.bbox("all"))
        panel_menu.bind("<Configure>", _region_scroll_menu)

        def _ajustar_ancho_menu(evento):
            canvas_nav.itemconfig(ventana_menu, width=evento.width)
        canvas_nav.bind("<Configure>", _ajustar_ancho_menu)

        def _rueda_mouse_menu(evento):
            if getattr(evento, "delta", 0):
                canvas_nav.yview_scroll(int(-1 * (evento.delta / 120)), "units")
            elif evento.num == 4:
                canvas_nav.yview_scroll(-1, "units")
            elif evento.num == 5:
                canvas_nav.yview_scroll(1, "units")

        def _activar_scroll_menu(evento):
            canvas_nav.bind_all("<MouseWheel>", _rueda_mouse_menu)
            canvas_nav.bind_all("<Button-4>", _rueda_mouse_menu)
            canvas_nav.bind_all("<Button-5>", _rueda_mouse_menu)

        def _desactivar_scroll_menu(evento):
            canvas_nav.unbind_all("<MouseWheel>")
            canvas_nav.unbind_all("<Button-4>")
            canvas_nav.unbind_all("<Button-5>")

        canvas_nav.bind("<Enter>", _activar_scroll_menu)
        canvas_nav.bind("<Leave>", _desactivar_scroll_menu)

        self.filas_sidebar = {}
        for titulo_grupo, items in self.grupos_menu:
            tk.Label(
                panel_menu, text=titulo_grupo, bg=COLOR_SIDEBAR, fg=COLOR_SIDEBAR_TEXTO,
                font=FUENTE_ETIQUETA, anchor="w"
            ).pack(fill="x", padx=22, pady=(16, 6))

            for nombre, accion in items:
                fila = tk.Frame(panel_menu, bg=COLOR_SIDEBAR)
                fila.pack(fill="x", padx=10, pady=1)

                indicador = tk.Frame(fila, bg=COLOR_SIDEBAR, width=3)
                indicador.pack(side="left", fill="y")

                icono = tk.Label(
                    fila, text=ICONOS_MENU.get(nombre, "•"), bg=COLOR_SIDEBAR,
                    fg=COLOR_SIDEBAR_TEXTO, font=FUENTE_NAV_ICONO, cursor="hand2", width=2
                )
                icono.pack(side="left", padx=(10, 2), pady=10)

                etiqueta = tk.Label(
                    fila, text=nombre.title(), bg=COLOR_SIDEBAR, fg=COLOR_SIDEBAR_TEXTO,
                    font=FUENTE_NAV, cursor="hand2", anchor="w"
                )
                etiqueta.pack(side="left", fill="x", expand=True, padx=(0, 10), pady=10)

                for widget in (fila, indicador, icono, etiqueta):
                    widget.bind("<Button-1>", lambda e, a=accion, n=nombre: self._seleccionar_menu(n, a))
                    widget.bind("<Enter>", lambda e, n=nombre: self._hover_menu(n, True))
                    widget.bind("<Leave>", lambda e, n=nombre: self._hover_menu(n, False))

                self.filas_sidebar[nombre] = (fila, indicador, icono, etiqueta)

        # Diccionario para no reconstruir cada pantalla desde cero cada vez
        self.pantallas = {}
        self.menu_actual = "JORNADAS"

        self._seleccionar_menu("JORNADAS", self.mostrar_pantalla_jornada)

    def _configurar_estilos_ttk(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("Claro.TCombobox",
                         fieldbackground=COLOR_PANEL, background=COLOR_PANEL,
                         foreground=COLOR_TEXTO, arrowcolor=COLOR_TEXTO_SUAVE,
                         bordercolor=COLOR_BORDE, lightcolor=COLOR_PANEL, darkcolor=COLOR_PANEL,
                         padding=6)
        style.map("Claro.TCombobox",
                  fieldbackground=[("readonly", COLOR_PANEL)],
                  bordercolor=[("focus", COLOR_BORDE_FOCO), ("!focus", COLOR_BORDE)])
        self.option_add("*TCombobox*Listbox.background", COLOR_PANEL)
        self.option_add("*TCombobox*Listbox.foreground", COLOR_TEXTO)
        self.option_add("*TCombobox*Listbox.selectBackground", COLOR_ACENTO_SUAVE)
        self.option_add("*TCombobox*Listbox.selectForeground", COLOR_ACENTO)
        self.option_add("*TCombobox*Listbox.font", FUENTE_BASE)

        style.configure("Treeview",
                         background=COLOR_PANEL, fieldbackground=COLOR_PANEL, foreground=COLOR_TEXTO,
                         bordercolor=COLOR_BORDE, borderwidth=0, rowheight=30,
                         font=FUENTE_BASE)
        style.configure("Treeview.Heading",
                         background=COLOR_FONDO, foreground=COLOR_TEXTO_SUAVE,
                         font=FUENTE_ETIQUETA, relief="flat", padding=(4, 10))
        style.map("Treeview.Heading", background=[("active", COLOR_FONDO)])
        style.map("Treeview", background=[("selected", COLOR_ACENTO_SUAVE)],
                  foreground=[("selected", COLOR_ACENTO)])
        style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

        style.configure("Vertical.TScrollbar",
                         background=COLOR_BORDE, troughcolor=COLOR_FONDO,
                         bordercolor=COLOR_FONDO, arrowcolor=COLOR_TEXTO_SUAVE, relief="flat")
        style.map("Vertical.TScrollbar", background=[("active", COLOR_TEXTO_TENUE)])

    def _seleccionar_menu(self, nombre, accion):
        self.menu_actual = nombre
        for n, (fila, indicador, icono, etiqueta) in self.filas_sidebar.items():
            activo = (n == nombre)
            fondo = COLOR_SIDEBAR_ACTIVO if activo else COLOR_SIDEBAR
            fila.config(bg=fondo)
            indicador.config(bg=COLOR_ACENTO if activo else COLOR_SIDEBAR)
            icono.config(bg=fondo, fg=COLOR_ACENTO if activo else COLOR_SIDEBAR_TEXTO)
            etiqueta.config(bg=fondo, fg=COLOR_SIDEBAR_TEXTO_ACTIVO if activo else COLOR_SIDEBAR_TEXTO,
                             font=FUENTE_NAV_BOLD if activo else FUENTE_NAV)
        accion()

    def _hover_menu(self, nombre, entrando):
        if nombre == self.menu_actual:
            return
        fila, indicador, icono, etiqueta = self.filas_sidebar[nombre]
        fondo = COLOR_SIDEBAR_HOVER if entrando else COLOR_SIDEBAR
        fila.config(bg=fondo)
        indicador.config(bg=fondo)
        icono.config(bg=fondo)
        etiqueta.config(bg=fondo)

    def _actualizar_indicador_sesion(self):
        """Refleja en la barra superior quién tiene la sesión iniciada
        (o su ausencia), sin necesidad de ir a la pantalla de Usuarios.
        Se llama cada vez que se limpia el contenido, así que siempre
        está al día sin importar por qué pantalla se navegue."""
        usuario_activo = sesion_actual["usuario"]
        if usuario_activo is None:
            self.label_avatar_sesion.config(text="?", bg=COLOR_HOVER, fg=COLOR_TEXTO_SUAVE)
            self.avatar_sesion.config(bg=COLOR_HOVER)
            self.label_sesion_nombre.config(text="Sin sesión iniciada", fg=COLOR_TEXTO)
            self.label_sesion_rol.config(text="Inicia sesión para operar el sistema")
            return

        inicial = (usuario_activo.nombre or usuario_activo.usuario or "?")[0].upper()
        self.label_avatar_sesion.config(text=inicial, bg=COLOR_ACENTO_SUAVE, fg=COLOR_ACENTO)
        self.avatar_sesion.config(bg=COLOR_ACENTO_SUAVE)
        self.label_sesion_nombre.config(text=usuario_activo.nombre or usuario_activo.usuario, fg=COLOR_TEXTO)
        self.label_sesion_rol.config(text=usuario_activo.rol.capitalize())

    def _limpiar_contenido(self):
        for widget in self.area_contenido.winfo_children():
            widget.destroy()
        self._actualizar_indicador_sesion()

    def _accion_autorizada(self, roles_permitidos, permitir_sin_usuarios=False):
        """RF-28: helper usado por las pantallas de registro/edición para
        verificar que haya una sesión activa con un rol autorizado."""
        autorizado, error = verificar_autorizacion(roles_permitidos, permitir_sin_usuarios)
        if not autorizado:
            messagebox.showerror("Acceso restringido", error)
        return autorizado

    def _titulo(self, texto, subtitulo=None):
        encabezado = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
        encabezado.pack(anchor="w", fill="x")

        tk.Frame(encabezado, bg=COLOR_ACENTO, width=4, height=28).pack(side="left", padx=(0, 12))

        bloque_texto = tk.Frame(encabezado, bg=COLOR_FONDO)
        bloque_texto.pack(side="left", anchor="w")
        tk.Label(bloque_texto, text=self.menu_actual.title(), font=FUENTE_ETIQUETA,
                 bg=COLOR_FONDO, fg=COLOR_ACENTO).pack(anchor="w")
        tk.Label(bloque_texto, text=texto, font=FUENTE_TITULO,
                 bg=COLOR_FONDO, fg=COLOR_TEXTO).pack(anchor="w")
        if subtitulo:
            tk.Label(bloque_texto, text=subtitulo, font=FUENTE_SUBTITULO,
                     bg=COLOR_FONDO, fg=COLOR_TEXTO_SUAVE).pack(anchor="w", pady=(4, 0))

        separador(self.area_contenido, anchor="w", pady=(18, ESPACIO_SECCION))

    
    # PANTALLA: Jornadas de Subasta (RF-11, RF-12, RF-04)
    
    def mostrar_pantalla_jornada(self):
        self._limpiar_contenido()
        self._titulo("Registrar Jornada de Subasta")

        form = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
        form.pack(anchor="w")
        form.columnconfigure(0, minsize=260)
        form.columnconfigure(1, minsize=260)

        self.entry_id_jornada = crear_campo(form, "ID de jornada", 0, 0, placeholder="Ej. 1")
        self.selector_fecha_jornada = crear_selector_fecha(form, "Fecha de la jornada", 0, 1)

        tk.Label(form, text="DIA CALCULADO", font=FUENTE_ETIQUETA,
                 bg=COLOR_FONDO, fg=COLOR_TEXTO_SUAVE
                 ).grid(row=2, column=0, sticky="w", padx=10, pady=(0, 6))
        self.label_dia_jornada = tk.Label(
            form, text="", font=FUENTE_BASE_BOLD, bg=COLOR_FONDO, fg=COLOR_ACENTO)
        self.label_dia_jornada.grid(row=3, column=0, sticky="w", padx=10)

        tk.Label(form, text="El dia de la jornada se calcula solo a partir de la fecha. "
                             "Solo se permiten jornadas los lunes, miércoles o sábado",
                 font=FUENTE_AYUDA, bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE
                 ).grid(row=4, column=0, columnspan=2, sticky="w", padx=10, pady=(6, 0))

        self.selector_fecha_jornada.bind(
            "<<DateEntrySelected>>", lambda evento: self._actualizar_dia_calculado())
        self.selector_fecha_jornada.bind(
            "<FocusOut>", lambda evento: self._actualizar_dia_calculado())
        # No se calcula ni se muestra nada apenas se abre la pantalla: el
        # DateEntry siempre arranca en la fecha de hoy, y mostrar de una
        # vez el aviso en rojo daria la impresion de un error aunque el
        # usuario todavia no haya elegido nada. Se espera a que el
        # usuario interactue con el calendario.
        self.label_dia_jornada.config(
            text="Elige una fecha en el calendario", fg=COLOR_TEXTO_TENUE)

        boton_principal(self.area_contenido, "Registrar Jornada",
                         self.accion_registrar_jornada).pack(anchor="w", pady=(24, ESPACIO_SECCION))

        tk.Label(self.area_contenido, text="JORNADAS REGISTRADAS", font=FUENTE_ETIQUETA,
                 bg=COLOR_FONDO, fg=COLOR_TEXTO_SUAVE).pack(anchor="w", pady=(0, 10))

        if len(jornadas_registradas) == 0:
            tk.Label(self.area_contenido, text="Todavía no hay jornadas registradas.",
                     bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE, font=FUENTE_BASE).pack(anchor="w")

        for jornada in jornadas_registradas:
            fila = tk.Frame(self.area_contenido, bg=COLOR_PANEL,
                             highlightthickness=1, highlightbackground=COLOR_BORDE)
            fila.pack(anchor="w", fill="x", pady=4)

            tk.Label(fila, text=f"Jornada {jornada.id_jornada}  ·  {jornada.dia_semana.capitalize()}  ·  "
                                 f"{jornada.fecha}",
                     bg=COLOR_PANEL, fg=COLOR_TEXTO, font=FUENTE_BASE).pack(side="left", padx=14, pady=12)

            tono_estado = "acento" if jornada.estado == "abierta" else "neutro"
            chip_estado(fila, jornada.estado, tono_estado).pack(side="left", padx=6)

            if jornada.estado == "abierta":
                boton_peligro(fila, "Cerrar",
                               lambda j=jornada.id_jornada: self.accion_cerrar_jornada(j)
                               ).pack(side="right", padx=10, pady=8)

    def _actualizar_dia_calculado(self):
        """Recalcula y muestra el dia de la semana de la fecha elegida en
        el calendario, coloreando en rojo cuando ese dia no es valido."""
        fecha = self.selector_fecha_jornada.get_date()
        dia = dia_semana_de_fecha(fecha)
        if dia in DIAS_VALIDOS_JORNADA:
            self.label_dia_jornada.config(text=dia.capitalize(), fg=COLOR_ACENTO)
        else:
            self.label_dia_jornada.config(
                text=f"{dia.capitalize()} (no permitido)", fg=COLOR_ALERTA)

    def accion_registrar_jornada(self):
        if not self._accion_autorizada(["administrador", "registrador"]):
            return
        texto_id = self.entry_id_jornada.get().strip()

        try:
            id_jornada = int(texto_id)
        except ValueError:
            messagebox.showerror("Datos invalidos", "El ID de jornada debe ser un numero.")
            return

        fecha_jornada = self.selector_fecha_jornada.get_date()
        nueva_jornada, error = registrar_jornada(id_jornada, fecha_jornada)

        if error:
            messagebox.showerror("Error al registrar jornada", error)
            return

        messagebox.showinfo(
            "Exito",
            f"Jornada {id_jornada} ({nueva_jornada.dia_semana}) registrada correctamente.")
        self.mostrar_pantalla_jornada()

    def accion_cerrar_jornada(self, id_jornada):
        if not self._accion_autorizada(["administrador"]):
            return
        jornada, error = cerrar_jornada(id_jornada)

        if error:
            messagebox.showerror("Error al cerrar jornada", error)
            return

        notificar_cierre_jornada(jornada)
        self.mostrar_pantalla_jornada()

   
    # PANTALLA: Consultar Jornadas por Rango de Fechas (RF-13)
   
    def mostrar_pantalla_consultar_jornadas(self):
        self._limpiar_contenido()
        self._titulo("Consultar Jornadas por Rango de Fechas")

        form = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
        form.pack(anchor="w")
        form.columnconfigure(0, minsize=260)
        form.columnconfigure(1, minsize=260)

        self.entry_fecha_inicio = crear_campo(form, "Fecha inicio (AAAA-MM-DD)", 0, 0,
                                               placeholder="2026-01-01")
        self.entry_fecha_fin = crear_campo(form, "Fecha fin (AAAA-MM-DD)", 0, 1,
                                            placeholder="2026-12-31")

        boton_principal(self.area_contenido, "Consultar",
                         self.accion_consultar_jornadas).pack(anchor="w", pady=(24, ESPACIO_SECCION))

        self.lista_jornadas_resultado = tk.Listbox(
            self.area_contenido, width=76, height=14,
            bg=COLOR_PANEL, fg=COLOR_TEXTO, font=FUENTE_BASE, relief="flat", bd=0,
            highlightthickness=1, highlightbackground=COLOR_BORDE,
            selectbackground=COLOR_HOVER, selectforeground=COLOR_TEXTO,
            activestyle="none"
        )
        self.lista_jornadas_resultado.pack(anchor="w", fill="x", ipady=6)

    def accion_consultar_jornadas(self):
        try:
            fecha_inicio = date.fromisoformat(self.entry_fecha_inicio.get().strip())
            fecha_fin = date.fromisoformat(self.entry_fecha_fin.get().strip())
        except ValueError:
            messagebox.showerror("Datos invalidos", "Las fechas deben tener el formato AAAA-MM-DD.")
            return

        resultado = consultar_jornadas_por_rango(fecha_inicio, fecha_fin)
        self.lista_jornadas_resultado.delete(0, tk.END)

        if len(resultado) == 0:
            self.lista_jornadas_resultado.insert(tk.END, "No se encontraron jornadas en ese rango de fechas.")
        else:
            for jornada in resultado:
                self.lista_jornadas_resultado.insert(
                    tk.END, f"Jornada {jornada.id_jornada} - {jornada.dia_semana} "
                            f"({jornada.fecha}) - {jornada.estado.upper()}")

    
    # PANTALLA: Registrar Lote (RF-01, RF-11)"
   
    def mostrar_pantalla_lote(self):
        self._limpiar_contenido()
        self._titulo("Registrar Nuevo Lote")

        form = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
        form.pack(anchor="w")
        form.columnconfigure(0, minsize=260)
        form.columnconfigure(1, minsize=260)

        self.entry_id_lote = crear_campo(form, "Numero de lote", 0, 0, placeholder="Ej. LT-001")
        self.entry_cantidad = crear_campo(form, "Cantidad de animales", 0, 1, placeholder=texto_rango_animales().capitalize())
        self.entry_precio_base = crear_campo(form, "Precio de compra por kg", 2, 0, placeholder="$ 0 por kilo")
        self.combo_jornada_lote = crear_combo(form, "Jornada", 2, 1,
                                               [str(j.id_jornada) for j in jornadas_registradas])
        self.combo_tipo_lote = crear_combo(form, "Tipo de animal del lote", 4, 0,
                                            ["ternero", "novilla", "vaca"])

        tk.Label(form, text="FECHA DE LA JORNADA (automatica)", font=FUENTE_ETIQUETA,
                 bg=COLOR_FONDO, fg=COLOR_TEXTO_SUAVE
                 ).grid(row=4, column=1, sticky="w", padx=10, pady=(0, 6))
        self.label_fecha_lote = tk.Label(
            form, text="Selecciona una jornada", font=FUENTE_BASE_BOLD,
            bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE)
        self.label_fecha_lote.grid(row=5, column=1, sticky="w", padx=10)

        tk.Label(form, text=f"El lote debe tener {texto_rango_animales()} animales, todos del mismo tipo. "
                             "La fecha del lote es la misma fecha de la jornada elegida. "
                             "El precio de compra es por kilo: el costo total se calcula con el peso de los animales.",
                 font=FUENTE_AYUDA, bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE
                 ).grid(row=6, column=0, columnspan=2, sticky="w", padx=10, pady=(8, 0))

        self.combo_jornada_lote.bind(
            "<<ComboboxSelected>>", lambda evento: self._actualizar_fecha_lote())

        boton_principal(self.area_contenido, "Guardar Lote y continuar",
                         self.accion_registrar_lote).pack(anchor="w", pady=(24, 0))

    def _actualizar_fecha_lote(self):
        """Muestra la fecha real de la jornada elegida, para que quede
        claro con que fecha se va a guardar el lote antes de registrarlo."""
        texto_jornada = self.combo_jornada_lote.get().strip()
        try:
            id_jornada = int(texto_jornada)
        except ValueError:
            self.label_fecha_lote.config(text="Selecciona una jornada", fg=COLOR_TEXTO_TENUE)
            return

        jornada = next((j for j in jornadas_registradas if j.id_jornada == id_jornada), None)
        if jornada is None:
            self.label_fecha_lote.config(text="Jornada no encontrada", fg=COLOR_ALERTA)
            return

        self.label_fecha_lote.config(
            text=f"{jornada.dia_semana.capitalize()} · {jornada.fecha}", fg=COLOR_ACENTO)

    def accion_registrar_lote(self):
        if not self._accion_autorizada(["administrador", "registrador"]):
            return
        texto_id = self.entry_id_lote.get().strip()
        texto_cantidad = self.entry_cantidad.get().strip()
        texto_precio = valor_campo(self.entry_precio_base).lstrip("$").strip().replace(",", "")
        texto_jornada = self.combo_jornada_lote.get().strip()
        tipo_animal = self.combo_tipo_lote.get().strip()

        try:
            id_lote = int(texto_id)
            cantidad_animales = int(texto_cantidad)
            precio_compra_kg = float(texto_precio) if texto_precio else 0
        except ValueError:
            messagebox.showerror("Datos invalidos", "El numero de lote, la cantidad y el precio por kilo deben ser numeros.")
            return

        if not texto_jornada:
            messagebox.showerror("Datos invalidos", "Debes seleccionar la jornada del lote.")
            return

        try:
            id_jornada = int(texto_jornada)
        except ValueError:
            messagebox.showerror("Datos invalidos", "La jornada seleccionada no es valida.")
            return

        if not tipo_animal:
            messagebox.showerror("Datos invalidos", "Debes seleccionar el tipo de animal del lote.")
            return

        nuevo_lote, error = registrar_lote(id_lote, cantidad_animales, precio_compra_kg,
                                            id_jornada, tipo_animal)

        if error:
            messagebox.showerror("Error al registrar lote", error)
            return

        messagebox.showinfo(
            "Exito", f"Lote {id_lote} registrado correctamente (fecha: {nuevo_lote.fecha_registro}).")
        self.mostrar_pantalla_lote()  # limpia el formulario

  
    # PANTALLA: Editar Lote (RF-03)
    
    def mostrar_pantalla_editar_lote(self):
        self._limpiar_contenido()

        if len(lotes_registrados) == 0:
            self._titulo("Editar Lote")
            tk.Label(self.area_contenido, text="Primero debes registrar un lote en la sección LOTES.",
                     bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE, font=FUENTE_BASE).pack(anchor="w")
            return

        self._titulo("Editar Lote")

        form = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
        form.pack(anchor="w")
        form.columnconfigure(0, minsize=260)
        form.columnconfigure(1, minsize=260)

        self.combo_lote_editar = crear_combo(form, "Lote a editar", 0, 0,
                                              [str(l.id_lote) for l in lotes_registrados])
        self.entry_nueva_cantidad = crear_campo(form, "Nueva cantidad de animales", 0, 1,
                                                 placeholder=texto_rango_animales().capitalize())
        self.entry_nuevo_precio_base = crear_campo(form, "Nuevo precio de compra por kg", 2, 0, placeholder="$ 0 por kilo")

        tk.Label(form, text="Solo se puede editar si la jornada del lote sigue abierta",
                 font=FUENTE_AYUDA, bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE
                 ).grid(row=4, column=0, columnspan=2, sticky="w", padx=10, pady=(8, 0))

        boton_principal(self.area_contenido, "Guardar Cambios",
                         self.accion_editar_lote).pack(anchor="w", pady=(24, 0))

    def accion_editar_lote(self):
        if not self._accion_autorizada(["administrador", "registrador"]):
            return
        texto_id = self.combo_lote_editar.get().strip()
        texto_cantidad = valor_campo(self.entry_nueva_cantidad)
        texto_precio = valor_campo(self.entry_nuevo_precio_base).lstrip("$").strip().replace(",", "")

        if not texto_id:
            messagebox.showerror("Error", "Selecciona un lote.")
            return

        try:
            id_lote = int(texto_id)
            cantidad_animales = int(texto_cantidad) if texto_cantidad else None
            precio_compra_kg = float(texto_precio) if texto_precio else None
        except ValueError:
            messagebox.showerror("Datos invalidos", "La cantidad y el precio por kilo deben ser numeros.")
            return

        lote_editado, error = editar_lote(id_lote, cantidad_animales, precio_compra_kg)

        if error:
            messagebox.showerror("Error al editar lote", error)
            return

        messagebox.showinfo("Exito", f"Lote {id_lote} actualizado correctamente.")
        self.mostrar_pantalla_editar_lote()

    
    # PANTALLA: Registrar Animal (RF-02, 06, 07, 08, 09) "
    
    def mostrar_pantalla_animal(self):
        self._limpiar_contenido()

        if len(lotes_registrados) == 0:
            self._titulo("Registro de Animales")
            tk.Label(self.area_contenido, text="Primero debes registrar un lote en la sección LOTES.",
                     bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE, font=FUENTE_BASE).pack(anchor="w")
            return

        self._titulo("Registro de Animales")

        form = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
        form.pack(anchor="w")
        form.columnconfigure(0, minsize=220)
        form.columnconfigure(1, minsize=220)
        form.columnconfigure(2, minsize=220)

        self.combo_lotes = crear_combo(form, "Lote", 0, 0,
                                        [str(l.id_lote) for l in lotes_registrados])
        self.entry_id_animal = crear_campo(form, "ID del animal", 0, 1, placeholder="Ej. 1")
        self.entry_ica = crear_campo(form, "N° ICA", 0, 2, placeholder="Ej. ICA-2026-0012")
        self.entry_peso = crear_campo(form, "Peso (kg)", 2, 0, placeholder="0.0")

        tk.Label(form, text="TIPO DE ANIMAL (segun el lote)", font=FUENTE_ETIQUETA,
                 bg=COLOR_FONDO, fg=COLOR_TEXTO_SUAVE).grid(row=2, column=1, sticky="w", padx=10, pady=(0, 6))
        self.label_tipo_lote_animal = tk.Label(
            form, text="Selecciona un lote", font=FUENTE_BASE, bg=COLOR_PANEL, fg=COLOR_TEXTO_TENUE,
            anchor="w", highlightthickness=1, highlightbackground=COLOR_BORDE
        )
        self.label_tipo_lote_animal.grid(row=3, column=1, sticky="ew", padx=10, ipady=8)

        # RF-31, RF-32, RF-33: raza, edad aproximada y observaciones sanitarias
        self.entry_raza = crear_combo(form, "Raza", 2, 2, RAZAS_DISPONIBLES)  # el usuario elige, no escribe
        self.entry_edad = crear_campo(form, "Edad aproximada (años)", 4, 0, placeholder="Ej. 2")
        self.entry_observaciones = crear_campo(
            form, "Observaciones sanitarias", 4, 1, placeholder="Ej. Vacunado, sin novedad")

        def actualizar_tipo_lote(evento=None):
            texto_id = self.combo_lotes.get().strip()
            if not texto_id:
                return
            lote = next((l for l in lotes_registrados if l.id_lote == int(texto_id)), None)
            if lote is not None:
                self.label_tipo_lote_animal.config(text=lote.tipo_animal.capitalize(), fg=COLOR_TEXTO)

        self.combo_lotes.bind("<<ComboboxSelected>>", actualizar_tipo_lote)

        boton_secundario(self.area_contenido, "+ Agregar Animal",
                          self.accion_registrar_animal).pack(anchor="w", pady=(24, 0))

    def accion_registrar_animal(self):
        if not self._accion_autorizada(["administrador", "registrador"]):
            return
        id_lote_texto = self.combo_lotes.get()
        if not id_lote_texto:
            messagebox.showerror("Error", "Selecciona un lote.")
            return

        id_lote = int(id_lote_texto)
        lote_encontrado = next(l for l in lotes_registrados if l.id_lote == id_lote)

        if lote_encontrado.esta_completo():
            messagebox.showerror(
                "Lote completo",
                f"El lote {id_lote} ya tiene registrados sus {lote_encontrado.cantidad_animales} "
                f"animales. Si necesitas cambiar el tamaño del lote, usa la sección "
                f"'Editar Lote'.")
            return

        if not lote_encontrado.jornada_esta_abierta():
            messagebox.showerror(
                "Jornada cerrada",
                f"La jornada del lote {id_lote} ya fue cerrada; no se pueden registrar más animales en él.")
            return

        try:
            id_animal = int(valor_campo(self.entry_id_animal))
            peso = float(valor_campo(self.entry_peso))
        except ValueError:
            messagebox.showerror("Datos invalidos", "El ID del animal y el peso deben ser numeros.")
            return

        registro_ica = valor_campo(self.entry_ica)

        if not registro_ica:
            messagebox.showerror("Datos invalidos", "Debes escribir el numero de registro ICA.")
            return

        raza = self.entry_raza.get().strip()
        if not raza:
            messagebox.showerror("Datos invalidos", "Selecciona la raza del animal.")
            return
        observaciones = valor_campo(self.entry_observaciones)

        try:
            edad = int(valor_campo(self.entry_edad))
        except ValueError:
            messagebox.showerror("Datos invalidos", "La edad aproximada debe ser un numero.")
            return

        tipo = lote_encontrado.tipo_animal  # homogeneidad: el tipo lo define el lote, no el usuario

        nuevo_animal, error = registrar_animal(id_animal, registro_ica, tipo, peso,
                                                tipo_esperado=lote_encontrado.tipo_animal,
                                                raza=raza, edad=edad,
                                                observaciones_sanitarias=observaciones)
        if error:
            messagebox.showerror("Error al registrar animal", error)
            return

        lote_encontrado.agregar_animal(nuevo_animal)

        messagebox.showinfo("Exito", f"Animal con ICA '{registro_ica}' agregado al lote {id_lote}.")
        self.mostrar_pantalla_animal()

    # PANTALLA: Proveedores (RF-30)

    def mostrar_pantalla_proveedor(self):
        self._limpiar_contenido()

        if len(lotes_registrados) == 0:
            self._titulo("Proveedores")
            tk.Label(self.area_contenido, text="Primero debes registrar un lote en la sección LOTES.",
                     bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE, font=FUENTE_BASE).pack(anchor="w")
            return

        self._titulo("Proveedores del Lote")

        form = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
        form.pack(anchor="w")
        form.columnconfigure(0, minsize=220)
        form.columnconfigure(1, minsize=220)
        form.columnconfigure(2, minsize=220)

        self.combo_lote_proveedor = crear_combo(form, "Lote", 0, 0,
                                                  [str(l.id_lote) for l in lotes_registrados])
        self.entry_id_proveedor = crear_campo(form, "ID del proveedor", 0, 1, placeholder="Ej. 1")
        self.entry_nombre_proveedor = crear_campo(form, "Nombre completo", 0, 2, placeholder="Ej. Carlos Ruiz")
        self.entry_documento_proveedor = crear_campo_solo_digitos(
            form, "N° de identificacion", 2, 0, longitud_maxima=10, placeholder="Ej. 1067123456")
        self.entry_telefono_proveedor = crear_campo_solo_digitos(
            form, "Telefono", 2, 1, longitud_maxima=10, placeholder="Ej. 3001234567")
        self.entry_finca_proveedor = crear_campo(form, "Finca de procedencia", 2, 2, placeholder="Ej. Finca La Esperanza")

        boton_principal(self.area_contenido, "Registrar Proveedor",
                         self.accion_registrar_proveedor).pack(anchor="w", pady=(24, ESPACIO_SECCION))

        tk.Label(self.area_contenido, text="PROVEEDORES REGISTRADOS", font=FUENTE_ETIQUETA,
                 bg=COLOR_FONDO, fg=COLOR_TEXTO_SUAVE).pack(anchor="w", pady=(0, 10))

        if len(proveedores_registrados) == 0:
            tk.Label(self.area_contenido, text="Todavía no hay proveedores registrados.",
                     bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE, font=FUENTE_BASE).pack(anchor="w")

        for proveedor in proveedores_registrados:
            fila = tk.Frame(self.area_contenido, bg=COLOR_PANEL,
                             highlightthickness=1, highlightbackground=COLOR_BORDE)
            fila.pack(anchor="w", fill="x", pady=4)
            tk.Label(fila, text=f"{proveedor.nombre}  ·  Doc. {proveedor.documentos}  ·  "
                                 f"Finca: {proveedor.finca}  ·  Lote {proveedor.id_lote}",
                     bg=COLOR_PANEL, fg=COLOR_TEXTO, font=FUENTE_BASE).pack(side="left", padx=14, pady=10)

    def accion_registrar_proveedor(self):
        if not self._accion_autorizada(["administrador", "registrador"]):
            return

        texto_id_lote = self.combo_lote_proveedor.get().strip()
        if not texto_id_lote:
            messagebox.showerror("Error", "Selecciona un lote.")
            return

        try:
            id_proveedor = int(valor_campo(self.entry_id_proveedor))
            id_lote = int(texto_id_lote)
        except ValueError:
            messagebox.showerror("Datos invalidos", "El ID del proveedor y el lote deben ser numeros.")
            return

        nombre = valor_campo(self.entry_nombre_proveedor)
        documento = valor_campo(self.entry_documento_proveedor)
        telefono = valor_campo(self.entry_telefono_proveedor)
        finca = valor_campo(self.entry_finca_proveedor)

        nuevo_proveedor, error = registrar_proveedor(id_proveedor, nombre, documento, telefono, finca, id_lote)
        if error:
            messagebox.showerror("Error al registrar proveedor", error)
            return

        messagebox.showinfo("Exito", f"Proveedor '{nombre}' registrado para el lote {id_lote}.")
        self.mostrar_pantalla_proveedor()

    # PANTALLA: Subasta en Vivo / Pujas (RF-34, RF-35)

    def mostrar_pantalla_subasta_vivo(self, id_lote_seleccionado=None):
        """Dos modos: si el lote todavia NO tiene pujas se piden lote, precio de
        salida, incremento y valor de la primera puja; si YA tiene pujas, esos
        datos no se vuelven a pedir y las pujas siguientes son automaticas."""
        self._limpiar_contenido()
        self.combo_lote_subasta = None
        self._id_lote_subasta = None

        lotes_en_subasta = [l for l in lotes_registrados if l.estado != "vendido"]

        if len(lotes_en_subasta) == 0:
            self._titulo("Subasta en Vivo")
            tk.Label(self.area_contenido, text="No hay lotes disponibles para subastar todavía.",
                     bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE, font=FUENTE_BASE).pack(anchor="w")
            return

        self._titulo("Subasta en Vivo", subtitulo="Precios y pujas por kilo: el total es el precio por kg × el peso del lote")

        lote_activo = next((l for l in lotes_en_subasta if l.id_lote == id_lote_seleccionado), None)
        if lote_activo is not None and lote_activo.pujas:
            self._construir_subasta_en_curso(lote_activo)
        else:
            self._construir_subasta_primera_puja(lotes_en_subasta, lote_activo)

    def _construir_subasta_primera_puja(self, lotes_en_subasta, lote_activo):
        """Formulario completo: solo se usa para la PRIMERA puja de un lote."""
        form = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
        form.pack(anchor="w")
        form.columnconfigure(0, minsize=220)
        form.columnconfigure(1, minsize=220)
        form.columnconfigure(2, minsize=220)

        self.combo_lote_subasta = crear_combo(form, "Lote a subastar", 0, 0,
                                               [str(l.id_lote) for l in lotes_en_subasta])
        self.entry_precio_salida = crear_campo(form, "Precio de salida por kg", 0, 1, placeholder="$ 0 por kilo")
        self.entry_incremento = crear_campo(form, "Incremento mínimo por kg", 0, 2,
                                             placeholder=f"Por defecto ${Lote.INCREMENTO_MINIMO_POR_DEFECTO}")
        self.entry_valor_puja = crear_campo(form, "Valor de la puja por kg", 2, 0, placeholder="$ 0 por kilo")

        self.combo_lote_subasta.bind("<<ComboboxSelected>>", lambda evento: self._al_elegir_lote_subasta())

        botones = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
        botones.pack(anchor="w", pady=(24, 12))
        boton_secundario(botones, "Establecer Precio de Salida",
                          self.accion_establecer_precio_salida).pack(side="left", padx=(0, 10))
        boton_principal(botones, "Registrar Puja",
                         self.accion_registrar_puja).pack(side="left", padx=(0, 10))
        boton_secundario(botones, "Determinar Puja Ganadora",
                          self.accion_determinar_puja_ganadora).pack(side="left")

        self._construir_estado_e_historial_subasta()

        if lote_activo is not None:
            self.combo_lote_subasta.set(str(lote_activo.id_lote))

        self._actualizar_estado_subasta()

    def _construir_subasta_en_curso(self, lote):
        """Lote con pujas: sin formulario. Un boton registra la siguiente puja
        sola (ultima puja + incremento) y otro permite un incremento mayor."""
        self._id_lote_subasta = lote.id_lote
        cerrada = lote.pujas[-1].es_ganadora

        self.label_estado_subasta = tk.Label(
            self.area_contenido, text="", font=FUENTE_BASE_BOLD, bg=COLOR_FONDO,
            fg=COLOR_TEXTO_TENUE, justify="left")
        self.label_estado_subasta.pack(anchor="w", pady=(0, 14))

        botones = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
        botones.pack(anchor="w", pady=(0, 12))

        if cerrada:
            tk.Label(self.area_contenido,
                     text="La puja ganadora ya fue determinada. Para registrar la venta ve a VENDER LOTE.",
                     font=FUENTE_BASE, bg=COLOR_FONDO, fg=COLOR_ACENTO).pack(anchor="w", pady=(0, 12))
        else:
            boton_principal(
                botones, f"Siguiente puja (+${lote.incremento_minimo_kg:,.0f}/kg)",
                self.accion_siguiente_puja).pack(side="left", padx=(0, 10))
            boton_secundario(botones, "Determinar Puja Ganadora",
                              self.accion_determinar_puja_ganadora).pack(side="left", padx=(0, 10))
        boton_secundario(botones, "Cambiar de Lote",
                          self.mostrar_pantalla_subasta_vivo).pack(side="left")

        if not cerrada:
            form = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
            form.pack(anchor="w", pady=(6, 12))
            form.columnconfigure(0, minsize=260)
            self.entry_incremento_mayor = crear_campo(
                form, "Incremento mayor por kg (opcional)", 0, 0, placeholder="$ 0 por kilo")
            boton_secundario(form, "Puja con incremento mayor",
                              self.accion_puja_incremento_mayor).grid(row=1, column=1, sticky="w", padx=10)

        self._construir_estado_e_historial_subasta()
        self._actualizar_estado_subasta()

    def _construir_estado_e_historial_subasta(self):
        if getattr(self, "combo_lote_subasta", None) is not None:
            self.label_estado_subasta = tk.Label(
                self.area_contenido, text="Selecciona un lote para ver su estado.",
                font=FUENTE_BASE_BOLD, bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE, justify="left")
            self.label_estado_subasta.pack(anchor="w", pady=(0, 10))

        tk.Label(self.area_contenido, text="HISTORIAL DE PUJAS", font=FUENTE_ETIQUETA,
                 bg=COLOR_FONDO, fg=COLOR_TEXTO_SUAVE).pack(anchor="w", pady=(0, 10))

        self.lista_pujas = tk.Listbox(
            self.area_contenido, width=90, height=10,
            bg=COLOR_PANEL, fg=COLOR_TEXTO, font=FUENTE_BASE, relief="flat", bd=0,
            highlightthickness=1, highlightbackground=COLOR_BORDE,
            selectbackground=COLOR_HOVER, selectforeground=COLOR_TEXTO,
            activestyle="none"
        )
        self.lista_pujas.pack(anchor="w", fill="x", ipady=6)

    def _al_elegir_lote_subasta(self):
        lote = self._lote_seleccionado_subasta()
        if lote is not None and lote.pujas:
            self.mostrar_pantalla_subasta_vivo(lote.id_lote)  # ya tiene pujas: pasa al modo automatico
        else:
            self._actualizar_estado_subasta()

    def _lote_seleccionado_subasta(self):
        if getattr(self, "combo_lote_subasta", None) is not None:
            texto_id = self.combo_lote_subasta.get().strip()
            if not texto_id:
                return None
            return next((l for l in lotes_registrados if l.id_lote == int(texto_id)), None)
        return next((l for l in lotes_registrados if l.id_lote == self._id_lote_subasta), None)

    def _actualizar_estado_subasta(self):
        lote = self._lote_seleccionado_subasta()
        self.lista_pujas.delete(0, tk.END)

        if lote is None:
            self.label_estado_subasta.config(text="Selecciona un lote para ver su estado.")
            return

        peso = lote.peso_total_kg()
        linea_1 = (f"Lote {lote.id_lote}  ·  {lote.tipo_animal}  ·  {len(lote.animales)}/{lote.cantidad_animales} "
                   f"animales  ·  Peso total: {peso:,.0f} kg  ·  Compra: ${lote.precio_compra_kg:,.0f}/kg")

        if not lote.esta_completo():
            linea_2 = (f"Faltan {lote.cantidad_animales_faltantes()} animales por registrar: "
                       f"todavía no se puede subastar este lote.")
        elif lote.precio_salida_kg is None:
            linea_2 = "Precio de salida: sin establecer."
        else:
            linea_2 = (f"Salida: ${lote.precio_salida_kg:,.0f}/kg (total ${lote.precio_salida_total():,.0f})  ·  "
                       f"Incremento mínimo: ${lote.incremento_minimo_kg:,.0f}/kg  ·  "
                       f"Puja mínima ahora: ${lote.puja_minima_kg():,.0f}/kg  ·  {len(lote.pujas)} puja(s)")

        self.label_estado_subasta.config(text=linea_1 + "\n" + linea_2)

        if not lote.pujas:
            self.lista_pujas.insert(tk.END, "Todavía no hay pujas registradas para este lote.")
        else:
            for puja in lote.pujas:
                marca = "  ★ GANADORA" if puja.es_ganadora else ""
                self.lista_pujas.insert(
                    tk.END,
                    f"Puja #{puja.id_puja}   ${puja.valor:,.0f}/kg   →   total ${puja.valor * peso:,.0f}   "
                    f"{puja.fecha_hora:%Y-%m-%d %H:%M}{marca}")

    @staticmethod
    def _numero_de_campo(entry):
        """Devuelve el numero escrito en el campo (sin '$'), None si esta vacio, o lanza ValueError."""
        texto = valor_campo(entry).lstrip("$").strip().replace(",", "")
        if texto == "":
            return None
        return float(texto)

    def accion_establecer_precio_salida(self):
        if not self._accion_autorizada(["administrador", "registrador"]):
            return
        lote = self._lote_seleccionado_subasta()
        if lote is None:
            messagebox.showerror("Error", "Selecciona un lote.")
            return

        try:
            precio_salida = self._numero_de_campo(self.entry_precio_salida)
            incremento = self._numero_de_campo(self.entry_incremento)
        except ValueError:
            messagebox.showerror("Datos invalidos", "El precio de salida y el incremento deben ser numeros.")
            return

        if precio_salida is None:
            messagebox.showerror("Datos invalidos", "Escribe el precio de salida por kilo.")
            return

        _, error = establecer_precio_salida(lote.id_lote, precio_salida, incremento)
        if error:
            messagebox.showerror("No se pudo establecer el precio de salida", error)
            return

        ganancia_minima = (precio_salida - lote.precio_compra_kg) * lote.peso_total_kg()
        etiqueta = "Ganancia" if ganancia_minima >= 0 else "Pérdida"
        messagebox.showinfo(
            "Precio de salida establecido",
            f"Lote {lote.id_lote}: ${precio_salida:,.0f} por kg × {lote.peso_total_kg():,.0f} kg = "
            f"${lote.precio_salida_total():,.0f} como mínimo.\n"
            f"{etiqueta} mínima estimada: ${abs(ganancia_minima):,.0f}.")
        self.mostrar_pantalla_subasta_vivo(lote.id_lote)

    def accion_registrar_puja(self):
        """Primera puja del lote: toma el precio de salida y el incremento del
        formulario (si aun no estaban establecidos) y registra la puja."""
        if not self._accion_autorizada(["administrador", "registrador"]):
            return
        lote = self._lote_seleccionado_subasta()
        if lote is None:
            messagebox.showerror("Error", "Selecciona un lote.")
            return

        try:
            precio_salida = self._numero_de_campo(self.entry_precio_salida)
            incremento = self._numero_de_campo(self.entry_incremento)
            valor = self._numero_de_campo(self.entry_valor_puja)
        except ValueError:
            messagebox.showerror("Datos invalidos", "El precio de salida, el incremento y la puja deben ser numeros.")
            return

        if valor is None:
            messagebox.showerror("Datos invalidos", "Escribe el valor de la puja por kilo.")
            return

        if precio_salida is None and lote.precio_salida_kg is None:
            messagebox.showerror("Datos invalidos", "Escribe el precio de salida por kilo.")
            return

        if precio_salida is not None or incremento is not None:
            salida_a_usar = precio_salida if precio_salida is not None else lote.precio_salida_kg
            _, error = establecer_precio_salida(lote.id_lote, salida_a_usar, incremento)
            if error:
                messagebox.showerror("No se pudo establecer el precio de salida", error)
                return

        id_puja = len(pujas_registradas) + 1
        _, error = registrar_puja(id_puja, lote.id_lote, valor)
        if error:
            messagebox.showerror("Error al registrar puja", error)
            return

        self.mostrar_pantalla_subasta_vivo(lote.id_lote)

    def accion_siguiente_puja(self):
        """Pujas siguientes: un solo boton, automatica (ultima puja + incremento minimo)."""
        if not self._accion_autorizada(["administrador", "registrador"]):
            return
        lote = self._lote_seleccionado_subasta()
        if lote is None:
            messagebox.showerror("Error", "No hay un lote seleccionado.")
            return

        _, error = registrar_puja(len(pujas_registradas) + 1, lote.id_lote, lote.puja_minima_kg())
        if error:
            messagebox.showerror("Error al registrar puja", error)
            return
        self.mostrar_pantalla_subasta_vivo(lote.id_lote)

    def accion_puja_incremento_mayor(self):
        """Opcional: la siguiente puja sube mas que el incremento minimo."""
        if not self._accion_autorizada(["administrador", "registrador"]):
            return
        lote = self._lote_seleccionado_subasta()
        if lote is None:
            messagebox.showerror("Error", "No hay un lote seleccionado.")
            return

        try:
            incremento = self._numero_de_campo(self.entry_incremento_mayor)
        except ValueError:
            messagebox.showerror("Datos invalidos", "El incremento debe ser un numero.")
            return

        if incremento is None:
            messagebox.showerror("Datos invalidos", "Escribe el incremento mayor por kilo.")
            return

        if incremento <= lote.incremento_minimo_kg:
            messagebox.showerror(
                "Incremento invalido",
                f"El incremento mayor debe ser más que el mínimo (${lote.incremento_minimo_kg:,.0f}/kg). "
                f"Para subir el mínimo usa el botón 'Siguiente puja'.")
            return

        valor = lote.pujas[-1].valor + incremento
        _, error = registrar_puja(len(pujas_registradas) + 1, lote.id_lote, valor)
        if error:
            messagebox.showerror("Error al registrar puja", error)
            return
        self.mostrar_pantalla_subasta_vivo(lote.id_lote)

    def accion_determinar_puja_ganadora(self):
        if not self._accion_autorizada(["administrador", "registrador"]):
            return
        lote = self._lote_seleccionado_subasta()
        if lote is None:
            messagebox.showerror("Error", "Selecciona un lote.")
            return

        puja_ganadora, error = determinar_puja_ganadora(lote.id_lote)
        if error:
            messagebox.showerror("Error", error)
            return

        messagebox.showinfo(
            "Puja ganadora",
            f"Puja ganadora del lote {lote.id_lote}: ${puja_ganadora.valor:,.0f} por kg × "
            f"{lote.peso_total_kg():,.0f} kg = ${puja_ganadora.valor * lote.peso_total_kg():,.0f}.")
        self.mostrar_pantalla_subasta_vivo(lote.id_lote)

    def mostrar_pantalla_reportes(self):
        """Lista de lotes: un boton por cada lote registrado. Al elegir uno
        se abre su detalle (mostrar_detalle_lote), en vez de una sola tabla
        gigante mezclando lotes y animales."""
        self._limpiar_contenido()
        self._titulo("Lotes Registrados")

        if len(lotes_registrados) == 0:
            tk.Label(self.area_contenido, text="Todavía no hay lotes registrados.",
                     bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE, font=FUENTE_BASE).pack(anchor="w", pady=(12, 0))
            return

        for lote in lotes_registrados:
            jornada_texto = f"Jornada {lote.id_jornada}" if lote.id_jornada is not None else "Sin jornada"
            tono_estado = "acento" if lote.estado == "abierto" else "neutro"

            fila = tk.Frame(self.area_contenido, bg=COLOR_PANEL,
                             highlightthickness=1, highlightbackground=COLOR_BORDE)
            fila.pack(anchor="w", fill="x", pady=4)

            tk.Label(fila, text=f"Lote {lote.id_lote}", font=FUENTE_BASE_BOLD,
                     bg=COLOR_PANEL, fg=COLOR_TEXTO).pack(side="left", padx=(14, 20), pady=12)
            tk.Label(fila, text=f"{jornada_texto}  ·  {lote.fecha_registro}  ·  "
                                 f"{lote.tipo_animal or '-'}  ·  {len(lote.animales)} animal(es)",
                     bg=COLOR_PANEL, fg=COLOR_TEXTO_SUAVE, font=FUENTE_BASE).pack(side="left")
            chip_estado(fila, lote.estado, tono_estado).pack(side="right", padx=14)
            boton_secundario(
                fila, "Ver Lote", lambda l=lote.id_lote: self.mostrar_detalle_lote(l)
            ).pack(side="right", padx=10, pady=8)

    def mostrar_detalle_lote(self, id_lote):
        """Detalle limpio de un solo lote: sus datos generales y, debajo,
        cada animal en su propia fila (ICA, tipo, peso, precio de compra)."""
        self._limpiar_contenido()

        lote = next((l for l in lotes_registrados if l.id_lote == id_lote), None)
        if lote is None:
            self._titulo("Lote no encontrado")
            boton_secundario(self.area_contenido, "Volver a Lotes",
                              self.mostrar_pantalla_reportes).pack(anchor="w", pady=(12, 0))
            return

        self._titulo(f"Lote {lote.id_lote}")

        boton_secundario(self.area_contenido, "← Volver a Lotes",
                          self.mostrar_pantalla_reportes).pack(anchor="w", pady=(0, 18))

        jornada_texto = f"Jornada {lote.id_jornada}" if lote.id_jornada is not None else "Sin jornada"
        comprador = next((c for c in compradores_registrados if c.id_lote == id_lote), None)

        panel_info = tk.Frame(self.area_contenido, bg=COLOR_PANEL,
                               highlightthickness=1, highlightbackground=COLOR_BORDE)
        panel_info.pack(anchor="w", fill="x", pady=(0, ESPACIO_SECCION))

        datos_generales = [
            ("Jornada", jornada_texto),
            ("Fecha", str(lote.fecha_registro)),
            ("Tipo de animal", lote.tipo_animal or "-"),
            ("Cantidad de animales", str(lote.cantidad_animales)),
            ("Peso total", f"{lote.peso_total_kg():,.0f} kg"),
            ("Precio de compra", f"${lote.precio_compra_kg:,.0f} por kg"),
            ("Costo total de compra", f"${lote.costo_total_compra():,.0f}"),
            ("Proveedor", (lote.proveedor.nombre + " - finca " + lote.proveedor.finca)
                          if lote.proveedor else "Sin proveedor registrado"),
            ("Estado", lote.estado.capitalize()),
            ("Comprador", comprador.nombre if comprador else "Sin comprador registrado"),
        ]
        for etiqueta, valor in datos_generales:
            fila = tk.Frame(panel_info, bg=COLOR_PANEL)
            fila.pack(anchor="w", fill="x", padx=16, pady=6)
            tk.Label(fila, text=etiqueta.upper(), font=FUENTE_ETIQUETA,
                     bg=COLOR_PANEL, fg=COLOR_TEXTO_SUAVE, width=22, anchor="w").pack(side="left")
            tk.Label(fila, text=valor, font=FUENTE_BASE,
                     bg=COLOR_PANEL, fg=COLOR_TEXTO, anchor="w").pack(side="left")

        tk.Label(self.area_contenido, text="ANIMALES DEL LOTE", font=FUENTE_ETIQUETA,
                 bg=COLOR_FONDO, fg=COLOR_TEXTO_SUAVE).pack(anchor="w", pady=(0, 10))

        if len(lote.animales) == 0:
            tk.Label(self.area_contenido, text="Este lote todavía no tiene animales registrados.",
                     bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE, font=FUENTE_BASE).pack(anchor="w")
            return

        columnas = ("ica", "tipo", "peso", "raza", "edad")
        contenedor_tabla = tk.Frame(self.area_contenido, bg=COLOR_FONDO,
                                     highlightthickness=1, highlightbackground=COLOR_BORDE)
        contenedor_tabla.pack(fill="x")

        tabla = ttk.Treeview(contenedor_tabla, columns=columnas, show="headings",
                              height=min(10, len(lote.animales)))
        encabezados = {"ica": "N° ICA", "tipo": "Tipo", "peso": "Peso (kg)",
                        "raza": "Raza", "edad": "Edad (años)"}
        for col in columnas:
            tabla.heading(col, text=encabezados[col])
            tabla.column(col, width=160, anchor="center")

        tabla.tag_configure("par", background=COLOR_PANEL)
        tabla.tag_configure("impar", background=COLOR_FONDO)
        tabla.pack(fill="x")

        for i, animal in enumerate(lote.animales):
            etiqueta = "par" if i % 2 == 0 else "impar"
            tabla.insert("", tk.END, values=(
                animal.registro_ica, animal.tipo, f"{animal.peso:,.1f}",
                animal.raza, animal.edad
            ), tags=(etiqueta,))


    # PANTALLA: Filtrar por tipo (RF-05)
   
    def mostrar_pantalla_filtrar(self):
        self._limpiar_contenido()
        self._titulo("Filtrar Lotes por Tipo de Animal")

        form = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
        form.pack(anchor="w")
        form.columnconfigure(0, minsize=260)

        self.combo_filtro_tipo = crear_combo(form, "Tipo de animal", 0, 0,
                                              ["ternero", "novilla", "vaca"])

        boton_principal(self.area_contenido, "Filtrar",
                         self.accion_filtrar).pack(anchor="w", pady=(24, ESPACIO_SECCION))

        self.lista_resultado = tk.Listbox(
            self.area_contenido, width=76, height=14,
            bg=COLOR_PANEL, fg=COLOR_TEXTO, font=FUENTE_BASE, relief="flat", bd=0,
            highlightthickness=1, highlightbackground=COLOR_BORDE,
            selectbackground=COLOR_HOVER, selectforeground=COLOR_TEXTO,
            activestyle="none"
        )
        self.lista_resultado.pack(anchor="w", fill="x", ipady=6)

    def accion_filtrar(self):
        tipo_buscado = self.combo_filtro_tipo.get()
        if not tipo_buscado:
            messagebox.showerror("Error", "Selecciona un tipo de animal.")
            return

        resultado = filtrar_lotes_por_tipo(lotes_registrados, tipo_buscado)
        self.lista_resultado.delete(0, tk.END)

        if len(resultado) == 0:
            self.lista_resultado.insert(tk.END, "No se encontraron lotes con ese tipo de animal.")
        else:
            for lote in resultado:
                self.lista_resultado.insert(tk.END, f"Lote {lote.id_lote}   (fecha: {lote.fecha_registro})")


    # PANTALLA: Vender Lote / Registrar Comprador (RF-14 + cierre y ganancia del lote)

    def mostrar_pantalla_comprador(self):
        self._limpiar_contenido()

        if len(lotes_registrados) == 0:
            self._titulo("Vender Lote")
            tk.Label(self.area_contenido, text="Primero debes registrar un lote en la sección LOTES.",
                     bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE, font=FUENTE_BASE).pack(anchor="w")
            return

        lotes_disponibles = [l for l in lotes_registrados if l.estado != "vendido"]

        self._titulo("Vender Lote y Registrar Comprador")

        form = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
        form.pack(anchor="w")
        form.columnconfigure(0, minsize=220)
        form.columnconfigure(1, minsize=220)
        form.columnconfigure(2, minsize=220)

        self.combo_lote_comprador = crear_combo(form, "Lote a vender", 0, 0,
                                                 [str(l.id_lote) for l in lotes_disponibles])
        self.entry_id_comprador = crear_campo(form, "ID del comprador", 0, 1, placeholder="Ej. 1")
        self.entry_nombre_comprador = crear_campo(form, "Nombre completo", 0, 2, placeholder="Ej. Juan Perez")
        self.entry_documento_comprador = crear_campo_solo_digitos(
            form, "N° de identificacion", 2, 0, longitud_maxima=10, placeholder="Ej. 1067123456")
        self.entry_telefono_comprador = crear_campo_solo_digitos(
            form, "Telefono", 2, 1, longitud_maxima=10, placeholder="Ej. 3001234567")
        self.entry_precio_venta = crear_campo(form, "Precio de venta por kg", 2, 2, placeholder="$ 0 por kilo")
        self.entry_id_venta = crear_campo(form, "ID de la venta", 4, 0, placeholder="Ej. 1")
        self.combo_forma_pago = crear_combo(form, "Forma de pago", 4, 1,
                                             ["efectivo", "transferencia", "credito"])

        if len(lotes_disponibles) == 0:
            tk.Label(self.area_contenido, text="Todos los lotes registrados ya fueron vendidos.",
                     font=FUENTE_AYUDA, bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE
                     ).pack(anchor="w", pady=(8, 0))

        # Resumen del lote elegido: peso, precios por kilo y total de la venta
        self.label_pista_venta = tk.Label(
            self.area_contenido, text="Selecciona un lote para ver su peso y precios.",
            font=FUENTE_AYUDA, bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE, justify="left")
        self.label_pista_venta.pack(anchor="w", pady=(10, 0))
        self.combo_lote_comprador.bind("<<ComboboxSelected>>", lambda e: self._lote_venta_elegido())
        self.entry_precio_venta.bind("<KeyRelease>", lambda e: self._actualizar_pista_venta())

        boton_principal(self.area_contenido, "Registrar Venta",
                         self.accion_registrar_comprador).pack(anchor="w", pady=(24, ESPACIO_SECCION))

        tk.Label(self.area_contenido, text="VENTAS REGISTRADAS", font=FUENTE_ETIQUETA,
                 bg=COLOR_FONDO, fg=COLOR_TEXTO_SUAVE).pack(anchor="w", pady=(0, 10))

        if len(compradores_registrados) == 0:
            tk.Label(self.area_contenido, text="Todavía no hay ventas registradas.",
                     bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE, font=FUENTE_BASE).pack(anchor="w")

        for comprador in compradores_registrados:
            lote = next((l for l in lotes_registrados if l.id_lote == comprador.id_lote), None)
            precio_venta_texto = (f"${lote.precio_venta:,.0f} (${lote.precio_venta_kg:,.0f}/kg)"
                                  if lote and lote.precio_venta is not None else "-")

            fila = tk.Frame(self.area_contenido, bg=COLOR_PANEL,
                             highlightthickness=1, highlightbackground=COLOR_BORDE)
            fila.pack(anchor="w", fill="x", pady=4)

            tk.Label(fila, text=f"{comprador.nombre}  ·  Doc. {comprador.documento}  ·  "
                                 f"Lote {comprador.id_lote}  ·  Venta: {precio_venta_texto}",
                     bg=COLOR_PANEL, fg=COLOR_TEXTO, font=FUENTE_BASE).pack(side="left", padx=14, pady=10)

    def _lote_venta_elegido(self):
        """Al elegir un lote en Vender Lote: si ya tiene puja ganadora, su
        valor por kilo se propone como precio de venta."""
        texto_id = self.combo_lote_comprador.get().strip()
        lote = next((l for l in lotes_registrados if texto_id and l.id_lote == int(texto_id)), None)
        ganadora = next((p for p in (lote.pujas if lote else []) if p.es_ganadora), None)
        if ganadora is not None:
            self.entry_precio_venta.delete(0, tk.END)
            self.entry_precio_venta.insert(0, f"{ganadora.valor:.0f}")
            self.entry_precio_venta.config(fg=COLOR_TEXTO)
        self._actualizar_pista_venta()

    def _actualizar_pista_venta(self):
        texto_id = self.combo_lote_comprador.get().strip()
        lote = next((l for l in lotes_registrados if texto_id and l.id_lote == int(texto_id)), None)
        if lote is None:
            return

        peso = lote.peso_total_kg()
        partes = [f"Lote {lote.id_lote}: {peso:,.0f} kg", f"compra ${lote.precio_compra_kg:,.0f}/kg"]
        if lote.precio_salida_kg is not None:
            partes.append(f"salida ${lote.precio_salida_kg:,.0f}/kg")
        ganadora = next((p for p in lote.pujas if p.es_ganadora), None)
        if ganadora is not None:
            partes.append(f"puja ganadora ${ganadora.valor:,.0f}/kg")
        linea_1 = "  ·  ".join(partes)

        try:
            precio = float(valor_campo(self.entry_precio_venta).lstrip("$").strip().replace(",", ""))
            linea_2 = (f"Total de la venta: ${precio:,.0f} × {peso:,.0f} kg = ${precio * peso:,.0f}  ·  "
                       f"Ganancia: ${(precio - lote.precio_compra_kg) * peso:,.0f}")
        except ValueError:
            linea_2 = ""
        self.label_pista_venta.config(text=linea_1 + ("\n" + linea_2 if linea_2 else ""))

    def accion_registrar_comprador(self):
        if not self._accion_autorizada(["administrador", "registrador"]):
            return

        texto_id_lote = self.combo_lote_comprador.get().strip()

        if not texto_id_lote:
            messagebox.showerror("Error", "Selecciona un lote.")
            return

        texto_precio_venta = valor_campo(self.entry_precio_venta).lstrip("$").strip().replace(",", "")
        forma_pago = self.combo_forma_pago.get()

        if not forma_pago:
            messagebox.showerror("Error", "Selecciona la forma de pago.")
            return

        try:
            id_comprador = int(valor_campo(self.entry_id_comprador))
            id_lote = int(texto_id_lote)
            id_venta = int(valor_campo(self.entry_id_venta))
            precio_venta_kg = float(texto_precio_venta)
        except ValueError:
            messagebox.showerror("Datos invalidos",
                                  "El ID del comprador, de la venta, el lote y el precio por kilo deben ser numeros.")
            return

        # Se valida ANTES de crear el comprador: si al lote le faltan
        # animales por registrar, no debe quedar ningun dato a medias.
        lote_seleccionado = next((l for l in lotes_registrados if l.id_lote == id_lote), None)
        if lote_seleccionado is not None and not lote_seleccionado.esta_completo():
            faltan = lote_seleccionado.cantidad_animales_faltantes()
            messagebox.showerror(
                "Faltan animales por registrar",
                f"Este lote debe tener {lote_seleccionado.cantidad_animales} animales, "
                f"registrados uno por uno en la sección Animales, antes de poder venderse.\n\n"
                f"Llevas {len(lote_seleccionado.animales)} registrados; faltan {faltan}.")
            return

        # Tambien se valida el precio ANTES de crear al comprador
        if lote_seleccionado is not None:
            error_precio = validar_precio_venta_kg(lote_seleccionado, precio_venta_kg)
            if error_precio:
                messagebox.showerror("Precio de venta invalido", error_precio)
                return

        if lote_seleccionado is not None and not lote_seleccionado.jornada_esta_abierta():
            messagebox.showerror(
                "Jornada cerrada",
                "La jornada de este lote ya fue cerrada; ya no se pueden registrar ventas en ella.")
            return

        if any(v.id_venta == id_venta for v in ventas_registradas):
            messagebox.showerror("ID de venta repetido",
                                  f"Ya existe una venta con el ID {id_venta}. Usa otro número.")
            return

        nombre = valor_campo(self.entry_nombre_comprador)
        documento = valor_campo(self.entry_documento_comprador)
        telefono = valor_campo(self.entry_telefono_comprador)

        nuevo_comprador, error = registrar_comprador(id_comprador, nombre, documento, telefono, id_lote)
        if error:
            messagebox.showerror("Error al registrar comprador", error)
            return

        lote_vendido, error = marcar_lote_vendido(id_lote, precio_venta_kg)
        if error:
            compradores_registrados.remove(nuevo_comprador)  # no dejar un comprador sin venta
            messagebox.showerror("Error al registrar la venta", error)
            return

        # RF-15, RF-21, RF-22: se registra la venta formalmente y se
        # actualiza la ganancia general acumulada.
        venta_registrada, error = registrar_venta(id_venta, id_lote, lote_vendido.precio_venta, forma_pago)
        if error:
            # deshacer: no dejar un lote vendido ni un comprador sin su venta
            lote_vendido.estado = "abierto"
            lote_vendido.precio_venta = None
            lote_vendido.precio_venta_kg = None
            if nuevo_comprador in compradores_registrados:
                compradores_registrados.remove(nuevo_comprador)
            messagebox.showerror("Error al registrar la venta", error)
            return

        peso = lote_vendido.peso_total_kg()
        mensaje = (f"Comprador '{nombre}' registrado.\n"
                   f"Lote {id_lote} vendido a ${precio_venta_kg:,.0f} por kg × {peso:,.0f} kg = "
                   f"${lote_vendido.precio_venta:,.0f} ({forma_pago}).\n"
                   f"Ganancia por kilo: ${lote_vendido.ganancia_por_kilo():,.0f}.\n"
                   f"Ganancia total del lote: ${lote_vendido.ganancia_total():,.0f}.\n"
                   f"Ganancia general acumulada: ${calcular_ganancia_general():,.0f}.\n"
                   f"Factura N° {venta_registrada.factura.numero_factura} generada (sección Facturas).")

        messagebox.showinfo("Venta registrada", mensaje)
        if forma_pago == "credito":
            messagebox.showwarning(
                "Saldo pendiente",
                f"{nombre} queda con un saldo pendiente de ${venta_registrada.consultar_saldo_pendiente():,.0f}.\n"
                "Registra sus pagos parciales en la sección Abonos.")  # RF-44
        self.mostrar_pantalla_comprador()

    # PANTALLA: Ganancias por Lote (ganancia total y ganancia por kilo)

    def mostrar_pantalla_ganancias(self):
        self._limpiar_contenido()
        self._titulo("Ganancias por Lote")

        columnas = ("lote", "tipo", "estado", "compra_kg", "precio_promedio", "venta_kg",
                    "precio_venta", "peso_kg", "ganancia_total", "ganancia_kilo")
        contenedor_tabla = tk.Frame(self.area_contenido, bg=COLOR_FONDO,
                                     highlightthickness=1, highlightbackground=COLOR_BORDE)
        contenedor_tabla.pack(fill="both", expand=True)

        tabla = ttk.Treeview(contenedor_tabla, columns=columnas, show="headings", height=15)

        encabezados = {
            "lote": "Lote", "tipo": "Tipo", "estado": "Estado",
            "compra_kg": "Compra $/kg", "precio_promedio": "Prom. compra/animal",
            "venta_kg": "Venta $/kg", "precio_venta": "Total venta",
            "peso_kg": "Peso (kg)", "ganancia_total": "Ganancia total",
            "ganancia_kilo": "Ganancia $/kg"
        }
        for col in columnas:
            tabla.heading(col, text=encabezados[col])
            tabla.column(col, width=100, anchor="center")

        tabla.tag_configure("par", background=COLOR_PANEL)
        tabla.tag_configure("impar", background=COLOR_FONDO)

        scrollbar = ttk.Scrollbar(contenedor_tabla, orient="vertical", command=tabla.yview)
        tabla.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        tabla.pack(side="left", fill="both", expand=True)

        if len(lotes_registrados) == 0:
            tk.Label(self.area_contenido, text="Todavía no hay lotes registrados.",
                     bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE, font=FUENTE_BASE).pack(anchor="w", pady=(12, 0))

        for indice, lote in enumerate(lotes_registrados):
            ganancia_total = lote.ganancia_total()
            ganancia_kilo = lote.ganancia_por_kilo()

            valores = (
                lote.id_lote,
                lote.tipo_animal.capitalize() if lote.tipo_animal else "-",
                lote.estado.upper(),
                f"${lote.precio_compra_kg:,.0f}",
                f"${lote.precio_promedio_compra():,.0f}",
                f"${lote.precio_venta_kg:,.0f}" if lote.precio_venta_kg is not None else "-",
                f"${lote.precio_venta:,.0f}" if lote.precio_venta is not None else "-",
                f"{lote.peso_total_kg():,.0f}",
                f"${ganancia_total:,.0f}" if ganancia_total is not None else "-",
                f"${ganancia_kilo:,.0f}" if ganancia_kilo is not None else "-",
            )
            etiqueta = "par" if indice % 2 == 0 else "impar"
            tabla.insert("", tk.END, values=valores, tags=(etiqueta,))

        # RF-21: ganancia general acumulada de todas las jornadas
        tk.Label(self.area_contenido,
                 text=f"Ganancia general acumulada: ${calcular_ganancia_general():,.0f}",
                 font=FUENTE_BASE_BOLD, bg=COLOR_FONDO, fg=COLOR_ACENTO
                 ).pack(anchor="w", pady=(16, 0))

    # PANTALLA: Iniciar Sesión (RF-27)

    def mostrar_pantalla_login(self):
        self._limpiar_contenido()
        self._titulo("Iniciar Sesión")

        usuario_activo = sesion_actual["usuario"]
        if usuario_activo is not None:
            tk.Label(self.area_contenido,
                     text=f"Sesión iniciada como '{usuario_activo.usuario}'  ·  rol: {usuario_activo.rol}",
                     bg=COLOR_FONDO, fg=COLOR_TEXTO, font=FUENTE_BASE_BOLD).pack(anchor="w", pady=(0, 16))
            boton_secundario(self.area_contenido, "Cerrar sesión",
                              self.accion_cerrar_sesion).pack(anchor="w")
            return

        if len(usuarios_registrados) == 0:
            tk.Label(self.area_contenido,
                     text="Todavía no hay usuarios registrados. Ve a la sección USUARIOS para crear una cuenta.",
                     bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE, font=FUENTE_BASE).pack(anchor="w")
            return

        form = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
        form.pack(anchor="w")
        form.columnconfigure(0, minsize=260)

        self.entry_login_usuario = crear_campo(form, "Usuario", 0, 0, placeholder="Ej. jfernandez")
        self.entry_login_contrasena = crear_campo(form, "Contraseña", 2, 0, placeholder="********")
        self.entry_login_contrasena.config(show="*")

        boton_principal(self.area_contenido, "Ingresar",
                         self.accion_iniciar_sesion).pack(anchor="w", pady=(24, ESPACIO_SECCION))

    def accion_iniciar_sesion(self):
        usuario = self.entry_login_usuario.get().strip()
        contrasena = self.entry_login_contrasena.get().strip()

        usuario_logueado, error = iniciar_sesion(usuario, contrasena)
        if error:
            messagebox.showerror("No se pudo iniciar sesión", error)
            return

        messagebox.showinfo("Sesión iniciada", f"Bienvenido, {usuario_logueado.nombre} ({usuario_logueado.rol}).")
        if consultar_saldos_pendientes():
            messagebox.showwarning("Saldos pendientes", alertar_saldos_pendientes())  # RF-44
        self.mostrar_pantalla_login()

    def accion_cerrar_sesion(self):
        cerrar_sesion()
        self.mostrar_pantalla_login()

    # PANTALLA: Usuarios (RF-26)

    def mostrar_pantalla_usuarios(self):
        self._limpiar_contenido()
        self._titulo("Usuarios del Sistema")

        form = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
        form.pack(anchor="w")
        form.columnconfigure(0, minsize=220)
        form.columnconfigure(1, minsize=220)
        form.columnconfigure(2, minsize=220)

        self.entry_id_usuario = crear_campo(form, "ID de usuario", 0, 0, placeholder="Ej. 1")
        self.entry_nombre_usuario = crear_campo(form, "Nombre completo", 0, 1, placeholder="Ej. Ana Torres")
        self.entry_usuario_usuario = crear_campo(form, "Usuario (login)", 0, 2, placeholder="Ej. atorres")
        self.entry_contrasena_usuario = crear_campo(form, "Contraseña", 2, 0, placeholder="********")
        self.entry_contrasena_usuario.config(show="*")
        self.combo_rol_usuario = crear_combo(form, "Rol", 2, 1,
                                              ["administrador", "registrador", "consulta"])

        boton_principal(self.area_contenido, "Crear Usuario",
                         self.accion_crear_usuario).pack(anchor="w", pady=(24, ESPACIO_SECCION))

        tk.Label(self.area_contenido, text="USUARIOS REGISTRADOS", font=FUENTE_ETIQUETA,
                 bg=COLOR_FONDO, fg=COLOR_TEXTO_SUAVE).pack(anchor="w", pady=(0, 10))

        if len(usuarios_registrados) == 0:
            tk.Label(self.area_contenido, text="Todavía no hay usuarios registrados.",
                     bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE, font=FUENTE_BASE).pack(anchor="w")

        for usuario in usuarios_registrados:
            fila = tk.Frame(self.area_contenido, bg=COLOR_PANEL,
                             highlightthickness=1, highlightbackground=COLOR_BORDE)
            fila.pack(anchor="w", fill="x", pady=4)
            tk.Label(fila, text=f"{usuario.nombre}  ·  usuario: {usuario.usuario}  ·  rol: {usuario.rol}",
                     bg=COLOR_PANEL, fg=COLOR_TEXTO, font=FUENTE_BASE).pack(side="left", padx=14, pady=10)

    def accion_crear_usuario(self):
        try:
            id_usuario = int(self.entry_id_usuario.get().strip())
        except ValueError:
            messagebox.showerror("Datos inválidos", "El ID de usuario debe ser un número.")
            return

        nombre = self.entry_nombre_usuario.get().strip()
        usuario = self.entry_usuario_usuario.get().strip()
        contrasena = self.entry_contrasena_usuario.get().strip()
        rol = self.combo_rol_usuario.get()

        if not rol:
            messagebox.showerror("Error", "Selecciona un rol.")
            return

        nuevo_usuario, error = registrar_usuario(id_usuario, nombre, usuario, contrasena, rol)
        if error:
            messagebox.showerror("Error al crear usuario", error)
            return

        messagebox.showinfo("Usuario creado", f"Cuenta '{usuario}' creada con rol '{rol}'.")
        self.mostrar_pantalla_usuarios()

    # PANTALLA: Auditoría (RF-29)

    def mostrar_pantalla_auditoria(self):
        self._limpiar_contenido()
        self._titulo("Auditoría del Sistema", subtitulo="Qué usuario realizó cada operación de registro o edición")

        autorizado, _ = verificar_autorizacion(["administrador"])
        if not autorizado:
            tk.Label(self.area_contenido, text="Solo un administrador puede consultar la auditoría.",
                     bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE, font=FUENTE_BASE).pack(anchor="w")
            return

        if len(auditorias_registradas) == 0:
            tk.Label(self.area_contenido, text="Todavía no se ha registrado ninguna operación.",
                     bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE, font=FUENTE_BASE).pack(anchor="w")
            return

        for registro in reversed(auditorias_registradas):
            fila = tk.Frame(self.area_contenido, bg=COLOR_PANEL,
                             highlightthickness=1, highlightbackground=COLOR_BORDE)
            fila.pack(anchor="w", fill="x", pady=4)
            tk.Label(fila, text=f"{registro.fecha_hora:%Y-%m-%d %H:%M}  ·  {registro.usuario}  ·  "
                                 f"{registro.operacion}",
                     bg=COLOR_PANEL, fg=COLOR_TEXTO, font=FUENTE_BASE).pack(side="left", padx=14, pady=10)

    # PANTALLA: Historial de Ventas (RF-16, RF-17, RF-18)

    def mostrar_pantalla_historial_ventas(self):
        self._limpiar_contenido()
        self._titulo("Historial de Ventas")

        form = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
        form.pack(anchor="w")
        form.columnconfigure(0, minsize=220)
        form.columnconfigure(1, minsize=220)
        form.columnconfigure(2, minsize=220)

        self.combo_tipo_busqueda_venta = crear_combo(
            form, "Buscar por", 0, 0, ["Comprador (documento)", "Animal (ICA)", "Lote (número)"])
        self.entry_valor_busqueda_venta = crear_campo(form, "Valor a buscar", 0, 1, placeholder="Ej. 1067123456")

        boton_principal(self.area_contenido, "Buscar",
                         self.accion_buscar_historial_ventas).pack(anchor="w", pady=(24, ESPACIO_SECCION))

        self.lista_historial_ventas = tk.Listbox(
            self.area_contenido, width=90, height=14,
            bg=COLOR_PANEL, fg=COLOR_TEXTO, font=FUENTE_BASE, relief="flat", bd=0,
            highlightthickness=1, highlightbackground=COLOR_BORDE,
            selectbackground=COLOR_HOVER, selectforeground=COLOR_TEXTO,
            activestyle="none"
        )
        self.lista_historial_ventas.pack(anchor="w", fill="x", ipady=6)

    def accion_buscar_historial_ventas(self):
        tipo_busqueda = self.combo_tipo_busqueda_venta.get()
        valor = self.entry_valor_busqueda_venta.get().strip()

        if not tipo_busqueda:
            messagebox.showerror("Error", "Selecciona por qué campo quieres buscar.")
            return
        if not valor:
            messagebox.showerror("Error", "Escribe un valor para buscar.")
            return

        if tipo_busqueda.startswith("Comprador"):
            resultado = consultar_ventas_por_comprador(valor)
        elif tipo_busqueda.startswith("Animal"):
            resultado = consultar_ventas_por_animal(valor)
        else:
            try:
                resultado = consultar_ventas_por_lote(int(valor))
            except ValueError:
                messagebox.showerror("Datos inválidos", "El número de lote debe ser un número.")
                return

        self.lista_historial_ventas.delete(0, tk.END)
        if len(resultado) == 0:
            self.lista_historial_ventas.insert(tk.END, "No se encontraron ventas para ese criterio.")
        else:
            for venta in resultado:
                self.lista_historial_ventas.insert(
                    tk.END,
                    f"Venta #{venta.id_venta}   Lote {venta.id_lote}   {venta.fecha}   "
                    f"${venta.precio_final:,.0f}   {venta.forma_pago}")

    # PANTALLA: Configurar rango de animales por lote (RF-36)

    def mostrar_pantalla_configuracion(self):
        self._limpiar_contenido()
        self._titulo("Rango de Animales por Lote")

        form = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
        form.pack(anchor="w")
        form.columnconfigure(0, minsize=260)
        form.columnconfigure(1, minsize=260)

        self.entry_rango_minimo = crear_campo(form, "Mínimo de animales por lote", 0, 0, placeholder="Ej. 10")
        self.entry_rango_maximo = crear_campo(form, "Máximo de animales por lote", 0, 1, placeholder="Ej. 30")

        self.label_rango_actual = tk.Label(
            self.area_contenido,
            text=f"Rango actual: {texto_rango_animales()} animales. "
                 f"Aplica a los lotes que se registren o editen de ahora en adelante.",
            font=FUENTE_AYUDA, bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE)
        self.label_rango_actual.pack(anchor="w", padx=10, pady=(10, 0))

        boton_principal(self.area_contenido, "Guardar Rango",
                         self.accion_configurar_rango).pack(anchor="w", pady=(24, 0))

    def accion_configurar_rango(self):
        if not self._accion_autorizada(["administrador"]):
            return
        try:
            minimo = int(valor_campo(self.entry_rango_minimo))
            maximo = int(valor_campo(self.entry_rango_maximo))
        except ValueError:
            messagebox.showerror("Datos invalidos", "El mínimo y el máximo deben ser números enteros.")
            return

        _, error = configurar_rango_animales(minimo, maximo)
        if error:
            messagebox.showerror("Rango invalido", error)
            return

        messagebox.showinfo("Rango guardado", f"Ahora cada lote debe tener {texto_rango_animales()} animales.")
        self.mostrar_pantalla_configuracion()

    # PANTALLA: Lista de compradores (RF-37)

    def mostrar_pantalla_lista_compradores(self):
        self._limpiar_contenido()
        self._titulo("Compradores Registrados",
                     subtitulo="Cada comprador aparece una sola vez, aunque haya comprado varios lotes")

        columnas = ("id", "nombre", "documento", "telefono", "lotes")
        contenedor_tabla = tk.Frame(self.area_contenido, bg=COLOR_FONDO,
                                     highlightthickness=1, highlightbackground=COLOR_BORDE)
        contenedor_tabla.pack(fill="both", expand=True)

        tabla = ttk.Treeview(contenedor_tabla, columns=columnas, show="headings", height=15)
        for col, texto, ancho in (("id", "ID", 60), ("nombre", "Nombre", 220), ("documento", "Documento", 130),
                                   ("telefono", "Teléfono", 130), ("lotes", "Lotes comprados", 160)):
            tabla.heading(col, text=texto)
            tabla.column(col, width=ancho, anchor="center")

        scrollbar = ttk.Scrollbar(contenedor_tabla, orient="vertical", command=tabla.yview)
        tabla.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        tabla.pack(side="left", fill="both", expand=True)

        compradores = consultar_compradores()
        if len(compradores) == 0:
            tk.Label(self.area_contenido, text="Todavía no hay compradores registrados.",
                     bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE, font=FUENTE_BASE).pack(anchor="w", pady=(12, 0))

        for c in compradores:
            ids_lotes = ", ".join(str(l.id_lote) for l in lotes_comprados_por_documento(c.documento)) or "-"
            tabla.insert("", tk.END, values=(c.id_comprador, c.nombre, c.documento, c.telefono or "-", ids_lotes))

    # PANTALLA: Buscar animal por ICA (RF-38)

    def _lista_resultados(self, alto=12):
        lista = tk.Listbox(
            self.area_contenido, width=90, height=alto,
            bg=COLOR_PANEL, fg=COLOR_TEXTO, font=FUENTE_BASE, relief="flat", bd=0,
            highlightthickness=1, highlightbackground=COLOR_BORDE,
            selectbackground=COLOR_HOVER, selectforeground=COLOR_TEXTO, activestyle="none")
        lista.pack(anchor="w", fill="x", ipady=6)
        return lista

    def mostrar_pantalla_buscar_animal(self):
        self._limpiar_contenido()
        self._titulo("Buscar Animal por Registro ICA")

        form = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
        form.pack(anchor="w")
        form.columnconfigure(0, minsize=260)
        self.entry_buscar_ica = crear_campo(form, "N° ICA", 0, 0, placeholder="Ej. ICA-2026-0012")

        boton_principal(self.area_contenido, "Buscar",
                         self.accion_buscar_animal).pack(anchor="w", pady=(24, ESPACIO_SECCION))
        self.lista_resultado_animal = self._lista_resultados(alto=10)

    def accion_buscar_animal(self):
        registro_ica = valor_campo(self.entry_buscar_ica)
        if not registro_ica:
            messagebox.showerror("Datos invalidos", "Escribe el número de registro ICA.")
            return

        animal, lote = buscar_animal_por_ica(registro_ica)
        self.lista_resultado_animal.delete(0, tk.END)

        if animal is None:
            self.lista_resultado_animal.insert(tk.END, "No se encontró ningún animal con ese registro ICA.")
            return

        for linea in (
            f"ICA: {animal.registro_ica}   ·   ID del animal: {animal.id_animal}",
            f"Tipo: {animal.tipo}   ·   Peso: {animal.peso} kg   ·   Raza: {animal.raza}   ·   Edad: {animal.edad} años",
            f"Observaciones sanitarias: {animal.observaciones_sanitarias}",
            f"Lote: {lote.id_lote}   ·   Jornada: {lote.id_jornada if lote.id_jornada is not None else '-'}   ·   "
            f"Estado del lote: {lote.estado}",
        ):
            self.lista_resultado_animal.insert(tk.END, linea)

    # PANTALLA: Buscar lotes por rango de fechas (RF-39)

    def _linea_lote(self, lote):
        comprador = next((c for c in compradores_registrados if c.id_lote == lote.id_lote), None)
        return (f"Lote {lote.id_lote}  ·  {lote.fecha_registro}  ·  {lote.tipo_animal or '-'}  ·  "
                f"{len(lote.animales)}/{lote.cantidad_animales} animales  ·  {lote.estado.upper()}  ·  "
                f"Comprador: {comprador.nombre if comprador else '-'}"
                + (f"  ·  Venta: ${lote.precio_venta:,.0f}" if lote.precio_venta is not None else ""))

    def mostrar_pantalla_lotes_por_fechas(self):
        self._limpiar_contenido()
        self._titulo("Buscar Lotes por Rango de Fechas")

        form = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
        form.pack(anchor="w")
        form.columnconfigure(0, minsize=260)
        form.columnconfigure(1, minsize=260)
        self.selector_lotes_inicio = crear_selector_fecha(form, "Fecha inicio", 0, 0)
        self.selector_lotes_fin = crear_selector_fecha(form, "Fecha fin", 0, 1)

        boton_principal(self.area_contenido, "Buscar",
                         self.accion_buscar_lotes_por_fechas).pack(anchor="w", pady=(24, ESPACIO_SECCION))
        self.lista_lotes_fechas = self._lista_resultados(alto=14)

    def accion_buscar_lotes_por_fechas(self):
        fecha_inicio = self.selector_lotes_inicio.get_date()
        fecha_fin = self.selector_lotes_fin.get_date()
        if fecha_inicio > fecha_fin:
            messagebox.showerror("Rango invalido", "La fecha de inicio no puede ser posterior a la fecha fin.")
            return

        resultado = buscar_lotes_por_rango_fechas(fecha_inicio, fecha_fin)
        self.lista_lotes_fechas.delete(0, tk.END)
        if len(resultado) == 0:
            self.lista_lotes_fechas.insert(tk.END, "No se encontraron lotes en ese rango de fechas.")
        for lote in resultado:
            self.lista_lotes_fechas.insert(tk.END, self._linea_lote(lote))

    # PANTALLA: Buscar lotes por comprador (RF-40)

    def mostrar_pantalla_lotes_por_comprador(self):
        self._limpiar_contenido()
        self._titulo("Buscar Lotes por Comprador")

        form = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
        form.pack(anchor="w")
        form.columnconfigure(0, minsize=320)
        self.entry_buscar_comprador = crear_campo(
            form, "Documento o nombre del comprador", 0, 0, placeholder="Ej. 1067123456 o Juan")

        boton_principal(self.area_contenido, "Buscar",
                         self.accion_buscar_lotes_por_comprador).pack(anchor="w", pady=(24, ESPACIO_SECCION))
        self.lista_lotes_comprador = self._lista_resultados(alto=14)

    def accion_buscar_lotes_por_comprador(self):
        texto = valor_campo(self.entry_buscar_comprador)
        if not texto:
            messagebox.showerror("Datos invalidos", "Escribe el documento o el nombre del comprador.")
            return

        resultado = buscar_lotes_por_comprador(texto)
        self.lista_lotes_comprador.delete(0, tk.END)
        if len(resultado) == 0:
            self.lista_lotes_comprador.insert(tk.END, "No se encontraron lotes para ese comprador.")
        for lote in resultado:
            self.lista_lotes_comprador.insert(tk.END, self._linea_lote(lote))

    # PANTALLA: Facturas de venta (RF-41, RF-42)

    def mostrar_pantalla_facturas(self):
        self._limpiar_contenido()
        self._titulo("Facturas de Venta", subtitulo="Se genera una factura automática por cada lote vendido")
        self._factura_actual = None

        if len(facturas_registradas) == 0:
            tk.Label(self.area_contenido, text="Todavía no hay facturas: se crean al vender un lote.",
                     bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE, font=FUENTE_BASE).pack(anchor="w")
            return

        form = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
        form.pack(anchor="w")
        form.columnconfigure(0, minsize=260)
        self.combo_factura = crear_combo(
            form, "Factura", 0, 0,
            [f"N° {f.numero_factura} - Lote {f.id_lote}" for f in facturas_registradas])
        self.combo_factura.bind("<<ComboboxSelected>>", lambda e: self._mostrar_factura_elegida())

        botones = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
        botones.pack(anchor="w", pady=(20, 12))
        boton_secundario(botones, "Exportar a PDF",
                          lambda: self.accion_exportar_factura("pdf")).pack(side="left", padx=(0, 10))
        boton_secundario(botones, "Exportar a Excel",
                          lambda: self.accion_exportar_factura("excel")).pack(side="left")

        self.texto_factura = tk.Text(
            self.area_contenido, width=100, height=16, wrap="word",
            bg=COLOR_PANEL, fg=COLOR_TEXTO, font=FUENTE_BASE, relief="flat", bd=0,
            highlightthickness=1, highlightbackground=COLOR_BORDE)
        self.texto_factura.pack(anchor="w", fill="both", pady=(12, 0))

    def _mostrar_factura_elegida(self):
        indice = self.combo_factura.current()
        if indice < 0:
            return
        self._factura_actual = facturas_registradas[indice]
        self.texto_factura.delete("1.0", tk.END)
        self.texto_factura.insert(tk.END, self._factura_actual.texto_factura())

    def accion_exportar_factura(self, formato):
        if self._factura_actual is None:
            messagebox.showerror("Error", "Primero elige una factura.")
            return
        nombre_archivo = self._factura_actual.exportar(formato)
        messagebox.showinfo("Factura exportada", f"Factura exportada en: {nombre_archivo}")

    # PANTALLA: Generar Reportes (RF-23, RF-24, RF-25)

    def mostrar_pantalla_generar_reportes(self):
        self._limpiar_contenido()
        self._titulo("Generar Reportes")

        form = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
        form.pack(anchor="w")
        form.columnconfigure(0, minsize=300)
        form.columnconfigure(1, minsize=200)
        form.columnconfigure(2, minsize=140)
        form.columnconfigure(3, minsize=140)

        self.combo_tipo_reporte = crear_combo(
            form, "Tipo de reporte", 0, 0,
            ["Reporte por Lote", "Reporte Consolidado por Jornada",
             "Ventas por tipo de animal", "Comparativo de ganancia por jornada",
             "Reporte mensual de ganancias", "Reporte anual de ganancias"])
        self.entry_id_para_reporte = crear_campo(form, "Número de lote o de jornada", 0, 1, placeholder="Ej. 1")
        self.entry_mes_reporte = crear_campo(form, "Mes (1-12)", 0, 2, placeholder="Ej. 10")
        self.entry_anio_reporte = crear_campo(form, "Año", 0, 3, placeholder=f"Ej. {date.today().year}")

        tk.Label(self.area_contenido,
                 text="Lote y jornada: escribe su número.  Mensual: mes y año.  Anual: solo el año.  "
                      "Ventas por tipo y comparativo por jornada no necesitan datos.",
                 font=FUENTE_AYUDA, bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE).pack(anchor="w", padx=10, pady=(8, 0))

        botones = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
        botones.pack(anchor="w", pady=(24, 12))
        boton_principal(botones, "Generar", self.accion_generar_reporte).pack(side="left", padx=(0, 10))
        boton_secundario(botones, "Exportar a PDF", self.accion_exportar_reporte_pdf).pack(side="left", padx=(0, 10))
        boton_secundario(botones, "Exportar a Excel", self.accion_exportar_reporte_excel).pack(side="left")

        self.texto_reporte = tk.Text(
            self.area_contenido, width=100, height=16, wrap="word",
            bg=COLOR_PANEL, fg=COLOR_TEXTO, font=FUENTE_BASE, relief="flat", bd=0,
            highlightthickness=1, highlightbackground=COLOR_BORDE
        )
        self.texto_reporte.pack(anchor="w", fill="both", pady=(12, 0))

        self._reporte_actual = None

    def accion_generar_reporte(self):
        tipo_reporte = self.combo_tipo_reporte.get()
        if not tipo_reporte:
            messagebox.showerror("Error", "Selecciona el tipo de reporte.")
            return

        id_reporte = len(lotes_registrados) + len(jornadas_registradas) + 1

        if tipo_reporte in ("Reporte por Lote", "Reporte Consolidado por Jornada"):
            try:
                identificador = int(valor_campo(self.entry_id_para_reporte))
            except ValueError:
                messagebox.showerror("Datos inválidos", "El número debe ser un valor entero.")
                return

            if tipo_reporte == "Reporte por Lote":
                reporte = ReportePorLote(id_reporte=id_reporte, id_lote=identificador)
                contenido = reporte.generar_reporte_por_lote(identificador)
            else:
                reporte = ReporteConsolidadoPorJornada(id_reporte=id_reporte, id_jornada=identificador)
                contenido = reporte.generar_reporte_jornada(identificador)

        elif tipo_reporte == "Ventas por tipo de animal":          # RF-45
            reporte = ReporteVentasPorTipoAnimal(id_reporte)
            contenido = "ESTADISTICAS DE VENTAS POR TIPO DE ANIMAL\n" + reporte.generar_reporte()

        elif tipo_reporte == "Comparativo de ganancia por jornada":  # RF-46
            reporte = ReporteGananciaComparativaPorJornada(id_reporte)
            contenido = reporte.generar_reporte()

        else:                                                       # RF-47
            es_mensual = (tipo_reporte == "Reporte mensual de ganancias")
            try:
                anio = int(valor_campo(self.entry_anio_reporte))
                mes = int(valor_campo(self.entry_mes_reporte)) if es_mensual else None
            except ValueError:
                messagebox.showerror("Datos inválidos",
                                      "El año (y el mes, en el reporte mensual) deben ser números enteros.")
                return
            if anio < 2000 or anio > 2100:
                messagebox.showerror("Datos inválidos", "El año debe estar entre 2000 y 2100.")
                return
            if es_mensual and not 1 <= mes <= 12:
                messagebox.showerror("Datos inválidos", "El mes debe estar entre 1 y 12.")
                return
            if es_mensual:
                contenido, reporte = generar_reporte_mensual(mes, anio)
            else:
                contenido, reporte = generar_reporte_anual(anio)

        self._reporte_actual = reporte
        self.texto_reporte.delete("1.0", tk.END)
        self.texto_reporte.insert(tk.END, contenido)

    def accion_exportar_reporte_pdf(self):
        if self._reporte_actual is None:
            messagebox.showerror("Error", "Primero genera un reporte.")
            return
        nombre_archivo = self._reporte_actual.exportar_pdf()
        messagebox.showinfo("Reporte exportado", f"Reporte exportado en: {nombre_archivo}")

    def accion_exportar_reporte_excel(self):
        if self._reporte_actual is None:
            messagebox.showerror("Error", "Primero genera un reporte.")
            return
        nombre_archivo = self._reporte_actual.exportar_excel()
        messagebox.showinfo("Reporte exportado", f"Reporte exportado en: {nombre_archivo}")


    # PANTALLA: Abonos y saldos pendientes (RF-43, RF-44)

    def mostrar_pantalla_abonos(self):
        self._limpiar_contenido()
        self._titulo("Abonos a Crédito",
                     subtitulo="Registra pagos parciales de las ventas a crédito y consulta los saldos pendientes")

        alertas = consultar_saldos_pendientes()
        self._ventas_con_saldo = alertas

        # RF-44: alerta visible de compradores con saldo pendiente
        banner = tk.Frame(self.area_contenido, bg=COLOR_ALERTA_SUAVE if alertas else COLOR_ACENTO_SUAVE,
                          highlightthickness=1, highlightbackground=COLOR_BORDE)
        banner.pack(anchor="w", fill="x", pady=(0, 20))
        tk.Label(banner, text=alertar_saldos_pendientes(), justify="left", anchor="w",
                 bg=COLOR_ALERTA_SUAVE if alertas else COLOR_ACENTO_SUAVE,
                 fg=COLOR_ALERTA if alertas else COLOR_ACENTO,
                 font=FUENTE_BASE_BOLD).pack(anchor="w", padx=16, pady=12)

        form = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
        form.pack(anchor="w")
        form.columnconfigure(0, minsize=420)
        form.columnconfigure(1, minsize=220)

        self.combo_venta_abono = crear_combo(
            form, "Venta a crédito con saldo", 0, 0,
            [f"Venta #{a['id_venta']} - {a['comprador']} - saldo ${a['saldo_pendiente']:,.0f}" for a in alertas])
        self.entry_monto_abono = crear_campo(form, "Monto del abono ($)", 0, 1, placeholder="Ej. 500000")

        boton_principal(self.area_contenido, "Registrar Abono",
                         self.accion_registrar_abono).pack(anchor="w", pady=(24, ESPACIO_SECCION))

        def tabla(columnas, alto):
            contenedor = tk.Frame(self.area_contenido, bg=COLOR_FONDO,
                                   highlightthickness=1, highlightbackground=COLOR_BORDE)
            contenedor.pack(fill="x", pady=(0, 18))
            t = ttk.Treeview(contenedor, columns=[c[0] for c in columnas], show="headings", height=alto)
            for col, texto, ancho in columnas:
                t.heading(col, text=texto)
                t.column(col, width=ancho, anchor="center")
            t.pack(fill="x")
            return t

        tk.Label(self.area_contenido, text="VENTAS A CRÉDITO", font=FUENTE_ETIQUETA,
                 bg=COLOR_FONDO, fg=COLOR_TEXTO_SUAVE).pack(anchor="w", pady=(0, 10))
        tabla_ventas = tabla((("venta", "Venta", 70), ("comprador", "Comprador", 200), ("total", "Total", 130),
                              ("pagado", "Pagado", 130), ("saldo", "Saldo pendiente", 140),
                              ("estado", "Estado", 110)), 6)
        for venta in ventas_registradas:
            if venta.forma_pago != "credito":
                continue
            comprador = next((c for c in compradores_registrados if c.id_comprador == venta.id_comprador), None)
            saldo = venta.consultar_saldo_pendiente()
            tabla_ventas.insert("", tk.END, values=(
                venta.id_venta, comprador.nombre if comprador else "No registrado",
                f"${venta.precio_final:,.0f}", f"${venta.precio_final - saldo:,.0f}",
                f"${saldo:,.0f}", "Pendiente" if saldo > 0 else "Pagada"))

        tk.Label(self.area_contenido, text="HISTORIAL DE ABONOS", font=FUENTE_ETIQUETA,
                 bg=COLOR_FONDO, fg=COLOR_TEXTO_SUAVE).pack(anchor="w", pady=(0, 10))
        tabla_abonos = tabla((("abono", "Abono", 70), ("venta", "Venta", 70), ("fecha", "Fecha", 130),
                              ("monto", "Monto", 140), ("saldo", "Saldo tras el abono", 170)), 5)
        for ab in abonos_registrados:
            tabla_abonos.insert("", tk.END, values=(
                ab.id_abono, ab.id_venta, ab.fecha, f"${ab.monto:,.0f}", f"${ab.saldo_pendiente:,.0f}"))

    def accion_registrar_abono(self):
        if not self._accion_autorizada(["administrador", "registrador"]):
            return

        indice = self.combo_venta_abono.current()
        if indice < 0:
            messagebox.showerror("Error", "Selecciona una venta a crédito con saldo pendiente.")
            return

        texto_monto = valor_campo(self.entry_monto_abono).lstrip("$").strip().replace(",", "")
        try:
            monto = float(texto_monto)
        except ValueError:
            messagebox.showerror("Datos inválidos", "El monto del abono debe ser un número.")
            return

        id_venta = self._ventas_con_saldo[indice]["id_venta"]
        abono, error = registrar_abono(len(abonos_registrados) + 1, id_venta, monto)
        if error:
            messagebox.showerror("No se pudo registrar el abono", error)
            return

        if abono.saldo_pendiente <= 0:
            detalle = "La venta quedó totalmente pagada."
        else:
            detalle = f"Saldo pendiente: ${abono.saldo_pendiente:,.0f}."
        messagebox.showinfo("Abono registrado", f"Abono de ${monto:,.0f} registrado en la venta #{id_venta}.\n{detalle}")
        self.mostrar_pantalla_abonos()

    # PANTALLA: Copias de seguridad (RF-48, RF-49)

    def mostrar_pantalla_respaldo(self):
        self._limpiar_contenido()
        self._titulo("Copias de Seguridad",
                     subtitulo="Guarda toda la información registrada y restáurala cuando la necesites")

        botones = tk.Frame(self.area_contenido, bg=COLOR_FONDO)
        botones.pack(anchor="w", pady=(0, ESPACIO_SECCION))
        boton_principal(botones, "Hacer copia de seguridad",
                         self.accion_realizar_respaldo).pack(side="left", padx=(0, 10))
        boton_secundario(botones, "Restaurar desde archivo...",
                          self.accion_restaurar_desde_archivo).pack(side="left")

        tk.Label(self.area_contenido, text="COPIAS DE SEGURIDAD ENCONTRADAS", font=FUENTE_ETIQUETA,
                 bg=COLOR_FONDO, fg=COLOR_TEXTO_SUAVE).pack(anchor="w", pady=(0, 10))

        contenedor = tk.Frame(self.area_contenido, bg=COLOR_FONDO,
                               highlightthickness=1, highlightbackground=COLOR_BORDE)
        contenedor.pack(fill="x")
        self.tabla_respaldos = ttk.Treeview(contenedor, columns=("id", "fecha", "ruta"), show="headings", height=7)
        for col, texto, ancho in (("id", "ID", 60), ("fecha", "Fecha", 120), ("ruta", "Archivo", 560)):
            self.tabla_respaldos.heading(col, text=texto)
            self.tabla_respaldos.column(col, width=ancho, anchor="center" if col != "ruta" else "w")
        self.tabla_respaldos.pack(fill="x")
        descubrir_respaldos_en_disco()  # incluye copias de sesiones anteriores guardadas en la carpeta 'reportes'
        for r in respaldos_registrados:
            self.tabla_respaldos.insert("", tk.END, values=(r.id_respaldo, r.fecha, r.ruta_archivo))

        if len(respaldos_registrados) == 0:
            tk.Label(self.area_contenido,
                     text="Todavía no hay copias guardadas. Si tienes un .pkl en otra carpeta, usa "
                          "'Restaurar desde archivo...' y elígelo.",
                     bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE, font=FUENTE_AYUDA).pack(anchor="w", pady=(8, 0))

        boton_peligro(self.area_contenido, "Restaurar copia seleccionada",
                       self.accion_restaurar_respaldo).pack(anchor="w", pady=(18, 6))
        tk.Label(self.area_contenido,
                 text="Al restaurar se reemplaza TODA la información actual por la de la copia.",
                 font=FUENTE_AYUDA, bg=COLOR_FONDO, fg=COLOR_TEXTO_TENUE).pack(anchor="w")

    def accion_realizar_respaldo(self):
        if not self._accion_autorizada(["administrador"]):
            return
        respaldo, error = realizar_respaldo()
        if error:
            messagebox.showerror("No se pudo hacer la copia", error)
            return
        messagebox.showinfo("Copia de seguridad creada",
                             f"Copia #{respaldo.id_respaldo} guardada en:\n{respaldo.ruta_archivo}")
        self.mostrar_pantalla_respaldo()

    def accion_restaurar_respaldo(self):
        if not self._accion_autorizada(["administrador"], permitir_sin_usuarios=True):
            return
        seleccion = self.tabla_respaldos.selection()
        if not seleccion:
            messagebox.showerror("Error", "Selecciona una copia de la lista.")
            return
        id_respaldo = int(self.tabla_respaldos.item(seleccion[0], "values")[0])
        if not messagebox.askyesno("Confirmar restauración",
                                    f"Se reemplazará toda la información actual por la de la copia #{id_respaldo}.\n"
                                    "¿Deseas continuar?"):
            return
        correcto, error = restaurar_respaldo(id_respaldo)
        if error:
            messagebox.showerror("No se pudo restaurar", error)
            return
        messagebox.showinfo("Información restaurada", f"Se restauró la copia #{id_respaldo}.")
        self.mostrar_pantalla_respaldo()

    def accion_restaurar_desde_archivo(self):
        if not self._accion_autorizada(["administrador"], permitir_sin_usuarios=True):
            return
        ruta = filedialog.askopenfilename(
            title="Elige la copia de seguridad", initialdir=_carpeta_reportes(),
            filetypes=[("Copia de seguridad", "*.pkl"), ("Todos los archivos", "*.*")])
        if not ruta:
            return
        if not messagebox.askyesno("Confirmar restauración",
                                    "Se reemplazará toda la información actual por la del archivo elegido.\n"
                                    "¿Deseas continuar?"):
            return
        correcto, error = restaurar_informacion_desde_archivo(ruta)
        if error:
            messagebox.showerror("No se pudo restaurar", error)
            return
        messagebox.showinfo("Información restaurada", "La información se restauró correctamente.")
        self.mostrar_pantalla_respaldo()

    app = tk.Tk()
    for nombre_metodo in [
        "_configurar_estilos_ttk",
        "_seleccionar_menu",
        "_hover_menu",
        "_actualizar_indicador_sesion",
        "_limpiar_contenido",
        "_accion_autorizada",
        "_titulo",
        "mostrar_pantalla_jornada",
        "_actualizar_dia_calculado",
        "accion_registrar_jornada",
        "accion_cerrar_jornada",
        "mostrar_pantalla_consultar_jornadas",
        "accion_consultar_jornadas",
        "mostrar_pantalla_lote",
        "_actualizar_fecha_lote",
        "accion_registrar_lote",
        "mostrar_pantalla_editar_lote",
        "accion_editar_lote",
        "mostrar_pantalla_animal",
        "accion_registrar_animal",
        "mostrar_pantalla_proveedor",
        "accion_registrar_proveedor",
        "mostrar_pantalla_subasta_vivo",
        "_construir_subasta_primera_puja",
        "_construir_subasta_en_curso",
        "_construir_estado_e_historial_subasta",
        "_al_elegir_lote_subasta",
        "_lote_seleccionado_subasta",
        "_actualizar_estado_subasta",
        "_numero_de_campo",
        "accion_establecer_precio_salida",
        "accion_registrar_puja",
        "accion_siguiente_puja",
        "accion_puja_incremento_mayor",
        "accion_determinar_puja_ganadora",
        "mostrar_pantalla_reportes",
        "mostrar_detalle_lote",
        "mostrar_pantalla_filtrar",
        "accion_filtrar",
        "mostrar_pantalla_comprador",
        "_lote_venta_elegido",
        "_actualizar_pista_venta",
        "accion_registrar_comprador",
        "mostrar_pantalla_ganancias",
        "mostrar_pantalla_login",
        "accion_iniciar_sesion",
        "accion_cerrar_sesion",
        "mostrar_pantalla_usuarios",
        "accion_crear_usuario",
        "mostrar_pantalla_auditoria",
        "mostrar_pantalla_historial_ventas",
        "accion_buscar_historial_ventas",
        "mostrar_pantalla_configuracion",
        "accion_configurar_rango",
        "mostrar_pantalla_lista_compradores",
        "_lista_resultados",
        "mostrar_pantalla_buscar_animal",
        "accion_buscar_animal",
        "_linea_lote",
        "mostrar_pantalla_lotes_por_fechas",
        "accion_buscar_lotes_por_fechas",
        "mostrar_pantalla_lotes_por_comprador",
        "accion_buscar_lotes_por_comprador",
        "mostrar_pantalla_facturas",
        "_mostrar_factura_elegida",
        "accion_exportar_factura",
        "mostrar_pantalla_generar_reportes",
        "accion_generar_reporte",
        "accion_exportar_reporte_pdf",
        "accion_exportar_reporte_excel",
        "mostrar_pantalla_abonos",
        "accion_registrar_abono",
        "mostrar_pantalla_respaldo",
        "accion_realizar_respaldo",
        "accion_restaurar_respaldo",
        "accion_restaurar_desde_archivo",
    ]:
        metodo = locals()[nombre_metodo]
        setattr(app, nombre_metodo, metodo.__get__(app, tk.Tk))

    setattr(app, "_inicializar", _inicializar.__get__(app, tk.Tk))
    app._inicializar()
    return app


if __name__ == "__main__":
    app = crear_ventana_principal()
    app.mainloop()
