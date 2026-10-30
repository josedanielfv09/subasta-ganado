"""Version web (Flask) del Sistema de Control de Operaciones de Subasta de Ganado.

La logica de negocio (las 24 clases y las funciones de cada RF) vive en
logica.py, tomada del sistema original. Este archivo solo reemplaza la
interfaz de escritorio (Tkinter) por paginas web.
"""
import io
import os
import tempfile
from datetime import date, timedelta
from functools import wraps

from flask import (Flask, flash, redirect, render_template, request, send_file,
                   session, url_for)

import logica as L

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "clave-de-desarrollo")

ADMIN = ("administrador",)
MENU = [
    ("inicio", "Inicio", None), ("jornadas", "Jornadas", None), ("lotes", "Lotes", None),
    ("animales", "Animales", None), ("proveedores", "Proveedores", None),
    ("subasta", "Subasta en vivo", None), ("venta", "Vender lote", None),
    ("facturas", "Facturas", None), ("abonos", "Abonos", None), ("ganancias", "Ganancias", None),
    ("reportes", "Generar reportes", None), ("buscar", "Búsquedas", None),
    ("usuarios", "Usuarios", ADMIN), ("configuracion", "Configurar rango", ADMIN),
    ("respaldo", "Respaldo", ADMIN), ("auditoria", "Auditoría", None),
]
PUBLICAS = {"login", "login_post", "primer_admin", "subir_respaldo"}
REPORTES = {}   # contenido de los reportes generados, para poder descargarlos


def roles(*permitidos):
    """RF-28: solo los roles indicados pueden ejecutar la acción."""
    def deco(f):
        @wraps(f)
        def envoltura(*a, **k):
            ok, error = L.verificar_autorizacion(list(permitidos))
            if not ok:
                flash(error, "error")
                return redirect(url_for("inicio"))
            return f(*a, **k)
        return envoltura
    return deco


def money(v):
    return f"${v:,.0f}"


def campo(name, label, tipo="text", opciones=None, valor="", paso=None, req=True):
    return dict(name=name, label=label, tipo=tipo, opciones=opciones or [],
                valor=valor, paso=paso, req=req)


def form(accion, campos, boton="Guardar", titulo=None):
    return dict(tipo="form", accion=accion, campos=campos, boton=boton, titulo=titulo)


def tabla(titulo, cols, filas):
    return dict(tipo="tabla", titulo=titulo, cols=cols, filas=filas)


def pagina(clave, titulo, bloques, subtitulo=""):
    return render_template("pantalla.html", activa=clave,
                           titulo=titulo, subtitulo=subtitulo, bloques=bloques)


def num(nombre, entero=False):
    texto = request.form.get(nombre, "").strip().replace("$", "").replace(",", "")
    return int(texto) if entero else float(texto)


def resultado(obj_error, ok, volver):
    """Muestra el mensaje de exito o de error y vuelve a la pantalla."""
    _, error = obj_error
    flash(error if error else ok, "error" if error else "ok")
    return redirect(url_for(volver))


def lote_por_id(id_lote):
    return next((l for l in L.lotes_registrados if l.id_lote == id_lote), None)


def opciones_lotes(solo_abiertos=False):
    return [(l.id_lote, f"Lote {l.id_lote} ({l.tipo_animal})") for l in L.lotes_registrados
            if not solo_abiertos or l.estado == "abierto"]


# ---------------------------------------------------------------- inicio
@app.route("/")
def inicio():
    resumen = [
        ("Jornadas", len(L.jornadas_registradas)), ("Lotes", len(L.lotes_registrados)),
        ("Animales", sum(len(l.animales) for l in L.lotes_registrados)),
        ("Ventas", len(L.ventas_registradas)),
        ("Ganancia general", money(L.calcular_ganancia_general())),
    ]
    return render_template("inicio.html", activa="inicio", resumen=resumen,
                           titulo="Sistema de Subasta de Ganado",
                           subtitulo="Control de lotes, animales, jornadas, pujas y ventas")


@app.post("/demo")
@roles("administrador")
def demo():
    """Carga datos de ejemplo (el plan gratuito de Render reinicia la memoria)."""
    if L.lotes_registrados:
        flash("Ya hay datos cargados.", "error")
        return redirect(url_for("inicio"))
    f = date.today()
    while f.weekday() not in (0, 2, 5):
        f += timedelta(days=1)
    L.registrar_jornada(1, f)
    lote, error = L.registrar_lote(1, 10, 6500, 1, "vaca")
    if error:
        flash(error, "error")
        return redirect(url_for("inicio"))
    for i in range(10):
        animal, error = L.registrar_animal(i + 1, f"ICA-DEMO-{i + 1:03d}", "vaca", 380 + i * 5,
                                           tipo_esperado="vaca", raza="Brahman", edad=4,
                                           observaciones_sanitarias="Vacunada")
        if not error:
            lote.agregar_animal(animal)
    flash("Datos de ejemplo cargados: 1 jornada, 1 lote de 10 vacas.", "ok")
    return redirect(url_for("inicio"))


# --------------------------------------------------------------- jornadas
@app.route("/jornadas")
def jornadas():
    filas = [(j.id_jornada, j.dia_semana, j.fecha.strftime("%Y-%m-%d"), j.estado,
              dict(boton="Cerrar", accion=url_for("jornada_cerrar", id_jornada=j.id_jornada))
              if j.estado == "abierta" else "") for j in L.jornadas_registradas]
    return pagina("jornadas", "Jornadas", [
        form(url_for("jornada_nueva"), [
            campo("id_jornada", "ID de la jornada", "number"),
            campo("fecha", "Fecha (lunes, miércoles o sábado)", "date")], "Registrar jornada"),
        tabla("Jornadas registradas", ["ID", "Día", "Fecha", "Estado", ""], filas)],
        "RF-03, RF-04, RF-11 a RF-13")


@app.post("/jornadas/nueva")
@roles("administrador", "registrador")
def jornada_nueva():
    try:
        r = L.registrar_jornada(num("id_jornada", True), date.fromisoformat(request.form["fecha"]))
    except ValueError:
        return resultado((None, "Revisa el ID y la fecha."), "", "jornadas")
    return resultado(r, "Jornada registrada.", "jornadas")


@app.post("/jornadas/cerrar/<int:id_jornada>")
@roles("administrador")
def jornada_cerrar(id_jornada):
    r = L.cerrar_jornada(id_jornada)
    if not r[1]:
        L.notificar_cierre_jornada(r[0])
    return resultado(r, f"La jornada {id_jornada} se cerró. Sus lotes ya no se pueden editar.", "jornadas")


# ------------------------------------------------------------------ lotes
@app.route("/lotes")
def lotes():
    abiertas = [(j.id_jornada, f"Jornada {j.id_jornada} - {j.dia_semana} {j.fecha}")
                for j in L.jornadas_registradas if j.estado == "abierta"]
    filas = [(l.id_lote, l.id_jornada, l.tipo_animal, f"{len(l.animales)}/{l.cantidad_animales}",
              money(l.precio_compra_kg), l.estado) for l in L.lotes_registrados]
    return pagina("lotes", "Lotes", [
        form(url_for("lote_nuevo"), [
            campo("id_lote", "Número de lote", "number"),
            campo("id_jornada", "Jornada", "select", abiertas),
            campo("tipo", "Tipo de animal", "select", [(t, t) for t in ("ternero", "novilla", "vaca")]),
            campo("cantidad", f"Cantidad de animales ({L.texto_rango_animales()})", "number"),
            campo("precio", "Precio de compra por kg ($)", "number", paso="any")], "Registrar lote"),
        form(url_for("lote_editar"), [
            campo("id_lote", "Lote a editar", "select", opciones_lotes(True)),
            campo("cantidad", "Nueva cantidad (opcional)", "number", req=False),
            campo("precio", "Nuevo precio por kg (opcional)", "number", paso="any", req=False)],
            "Editar lote", "Editar lote (solo con la jornada abierta)"),
        tabla("Lotes registrados", ["Lote", "Jornada", "Tipo", "Animales", "Compra/kg", "Estado"], filas)],
        "RF-01, RF-02, RF-03, RF-05")


@app.post("/lotes/nuevo")
@roles("administrador", "registrador")
def lote_nuevo():
    try:
        r = L.registrar_lote(num("id_lote", True), num("cantidad", True), num("precio"),
                             num("id_jornada", True), request.form["tipo"])
    except (ValueError, KeyError):
        return resultado((None, "Revisa que los campos sean números válidos."), "", "lotes")
    return resultado(r, "Lote registrado.", "lotes")


@app.post("/lotes/editar")
@roles("administrador", "registrador")
def lote_editar():
    try:
        cantidad = num("cantidad", True) if request.form.get("cantidad") else None
        precio = num("precio") if request.form.get("precio") else None
        r = L.editar_lote(num("id_lote", True), cantidad, precio)
    except ValueError:
        return resultado((None, "Revisa que los campos sean números válidos."), "", "lotes")
    return resultado(r, "Lote editado.", "lotes")


# --------------------------------------------------------------- animales
@app.route("/animales")
def animales():
    filas = [(l.id_lote, a.id_animal, a.registro_ica, l.tipo_animal, a.peso, a.raza, a.edad)
             for l in L.lotes_registrados for a in l.animales]
    return pagina("animales", "Animales", [
        form(url_for("animal_nuevo"), [
            campo("id_lote", "Lote", "select", opciones_lotes(True)),
            campo("id_animal", "ID del animal", "number"),
            campo("ica", "Registro ICA (único)"),
            campo("peso", "Peso (kg)", "number", paso="any"),
            campo("raza", "Raza", "select", [(r, r) for r in L.RAZAS_DISPONIBLES]),
            campo("edad", "Edad aproximada (meses)", "number"),
            campo("obs", "Observaciones sanitarias", req=False)], "Registrar animal"),
        tabla("Animales registrados", ["Lote", "ID", "ICA", "Tipo", "Peso kg", "Raza", "Edad"], filas)],
        "RF-02, RF-06 a RF-10, RF-31 a RF-33")


@app.post("/animales/nuevo")
@roles("administrador", "registrador")
def animal_nuevo():
    try:
        lote = lote_por_id(num("id_lote", True))
        if lote is None:
            return resultado((None, "Selecciona un lote."), "", "animales")
        if lote.esta_completo():
            return resultado((None, f"El lote {lote.id_lote} ya tiene sus {lote.cantidad_animales} animales."), "", "animales")
        if not lote.jornada_esta_abierta():
            return resultado((None, "La jornada de este lote ya fue cerrada."), "", "animales")
        animal, error = L.registrar_animal(num("id_animal", True), request.form["ica"], lote.tipo_animal,
                                           num("peso"), tipo_esperado=lote.tipo_animal,
                                           raza=request.form["raza"], edad=num("edad", True),
                                           observaciones_sanitarias=request.form.get("obs", ""))
    except (ValueError, KeyError):
        return resultado((None, "Revisa que ID, peso y edad sean números válidos."), "", "animales")
    if not error:
        lote.agregar_animal(animal)
    return resultado((animal, error), f"Animal agregado al lote {lote.id_lote}.", "animales")


# ------------------------------------------------------------ proveedores
@app.route("/proveedores")
def proveedores():
    filas = [(p.id_proveedor, p.nombre, p.documento, p.telefono, p.finca, p.id_lote)
             for p in L.proveedores_registrados]
    return pagina("proveedores", "Proveedores", [
        form(url_for("proveedor_nuevo"), [
            campo("id_proveedor", "ID del proveedor", "number"),
            campo("id_lote", "Lote", "select", opciones_lotes()),
            campo("nombre", "Nombre"), campo("documento", "Documento"),
            campo("telefono", "Teléfono", req=False), campo("finca", "Finca de procedencia")],
            "Registrar proveedor"),
        tabla("Proveedores", ["ID", "Nombre", "Documento", "Teléfono", "Finca", "Lote"], filas)], "RF-30")


@app.post("/proveedores/nuevo")
@roles("administrador", "registrador")
def proveedor_nuevo():
    try:
        r = L.registrar_proveedor(num("id_proveedor", True), request.form["nombre"], request.form["documento"],
                                  request.form.get("telefono", ""), request.form["finca"], num("id_lote", True))
    except ValueError:
        return resultado((None, "El ID y el lote deben ser números."), "", "proveedores")
    return resultado(r, "Proveedor registrado.", "proveedores")


# ---------------------------------------------------------------- subasta
@app.route("/subasta")
def subasta():
    sel = request.args.get("lote", type=int)
    lote = lote_por_id(sel) if sel else None
    bloques = [form(url_for("subasta"), [campo("lote", "Elige el lote a subastar", "select",
                                               opciones_lotes(True), valor=sel or "")],
                    "Abrir subasta", None).copy()]
    bloques[0]["metodo"] = "get"
    if lote:
        estado = (f"Precio de salida: {money(lote.precio_salida_kg)}/kg · "
                  f"Incremento mínimo: {money(lote.incremento_minimo_kg)}/kg · "
                  f"Puja mínima: {money(lote.puja_minima_kg())}/kg") if lote.precio_salida_kg else \
                 "Este lote aún no tiene precio de salida: la primera puja lo establece."
        bloques.append(dict(tipo="texto", texto=f"Lote {lote.id_lote} ({lote.tipo_animal}) · "
                            f"{lote.peso_total_kg():,.0f} kg · {estado}"))
        campos = [campo("id_lote", "", "hidden", valor=lote.id_lote),
                  campo("valor", "Valor de la puja ($/kg)", "number", paso="any")]
        if lote.precio_salida_kg is None:
            campos += [campo("salida", "Precio de salida ($/kg)", "number", paso="any"),
                       campo("incremento", "Incremento mínimo ($/kg)", "number", paso="any", req=False)]
        bloques.append(form(url_for("puja_nueva"), campos, "Registrar puja"))
        bloques.append(form(url_for("puja_ganadora"), [campo("id_lote", "", "hidden", valor=lote.id_lote)],
                            "Determinar puja ganadora"))
        bloques.append(tabla("Historial de pujas", ["#", "Valor $/kg", "Hora", "Ganadora"],
                             [(p.id_puja, money(p.valor), p.fecha_hora.strftime("%H:%M:%S"),
                               "Sí" if p.es_ganadora else "") for p in lote.pujas]))
    return pagina("subasta", "Subasta en vivo", bloques, "RF-34, RF-35")


@app.post("/subasta/puja")
@roles("administrador", "registrador")
def puja_nueva():
    try:
        id_lote = num("id_lote", True)
        lote = lote_por_id(id_lote)
        if request.form.get("salida"):
            incremento = num("incremento") if request.form.get("incremento") else None
            _, error = L.establecer_precio_salida(id_lote, num("salida"), incremento)
            if error:
                flash(error, "error")
                return redirect(url_for("subasta", lote=id_lote))
        _, error = L.registrar_puja(len(L.pujas_registradas) + 1, id_lote, num("valor"))
    except ValueError:
        error = "Escribe valores numéricos."
        id_lote = request.form.get("id_lote")
    flash(error if error else "Puja registrada.", "error" if error else "ok")
    return redirect(url_for("subasta", lote=id_lote))


@app.post("/subasta/ganadora")
@roles("administrador", "registrador")
def puja_ganadora():
    id_lote = num("id_lote", True)
    p, error = L.determinar_puja_ganadora(id_lote)
    flash(error if error else f"Puja ganadora: {money(p.valor)}/kg.", "error" if error else "ok")
    return redirect(url_for("subasta", lote=id_lote))


# ------------------------------------------------------------------ venta
@app.route("/venta")
def venta():
    return pagina("venta", "Vender lote y registrar comprador", [
        form(url_for("venta_nueva"), [
            campo("id_lote", "Lote", "select", opciones_lotes(True)),
            campo("id_comprador", "ID del comprador", "number"),
            campo("id_venta", "ID de la venta", "number"),
            campo("nombre", "Nombre del comprador"), campo("documento", "Documento"),
            campo("telefono", "Teléfono", req=False),
            campo("precio", "Precio de venta ($/kg)", "number", paso="any"),
            campo("pago", "Forma de pago", "select", [(f, f) for f in L.FORMAS_PAGO])], "Registrar venta"),
        tabla("Ventas", ["Venta", "Lote", "Comprador", "Total", "Pago", "Factura"],
              [(v.id_venta, v.id_lote, v.id_comprador, money(v.precio_final), v.forma_pago,
                v.factura.numero_factura if v.factura else "") for v in L.ventas_registradas])],
        "RF-14 a RF-22")


@app.post("/venta/nueva")
@roles("administrador", "registrador")
def venta_nueva():
    try:
        id_lote, id_comprador, id_venta, precio = (num("id_lote", True), num("id_comprador", True),
                                                   num("id_venta", True), num("precio"))
    except ValueError:
        return resultado((None, "Revisa que los números sean válidos."), "", "venta")
    lote = lote_por_id(id_lote)
    if lote is None or not lote.esta_completo():
        faltan = lote.cantidad_animales_faltantes() if lote else 0
        return resultado((None, f"Al lote le faltan {faltan} animales por registrar antes de venderse."), "", "venta")
    error = L.validar_precio_venta_kg(lote, precio)
    if error:
        return resultado((None, error), "", "venta")
    if not lote.jornada_esta_abierta():
        return resultado((None, "La jornada de este lote ya fue cerrada."), "", "venta")
    if any(v.id_venta == id_venta for v in L.ventas_registradas):
        return resultado((None, f"Ya existe una venta con el ID {id_venta}."), "", "venta")
    comprador, error = L.registrar_comprador(id_comprador, request.form["nombre"], request.form["documento"],
                                            request.form.get("telefono", ""), id_lote)
    if error:
        return resultado((None, error), "", "venta")
    vendido, error = L.marcar_lote_vendido(id_lote, precio)
    if error:
        L.compradores_registrados.remove(comprador)
        return resultado((None, error), "", "venta")
    reg, error = L.registrar_venta(id_venta, id_lote, vendido.precio_venta, request.form["pago"])
    if error:
        vendido.estado, vendido.precio_venta, vendido.precio_venta_kg = "abierto", None, None
        L.compradores_registrados.remove(comprador)
        return resultado((None, error), "", "venta")
    msg = (f"Lote {id_lote} vendido: {money(precio)}/kg × {vendido.peso_total_kg():,.0f} kg = "
           f"{money(vendido.precio_venta)}. Ganancia del lote: {money(vendido.ganancia_total())}. "
           f"Factura N° {reg.factura.numero_factura}.")
    flash(msg, "ok")
    if request.form["pago"] == "credito":
        flash(f"Saldo pendiente: {money(reg.consultar_saldo_pendiente())}. Regístralo en Abonos.", "aviso")
    return redirect(url_for("venta"))


# --------------------------------------------------------------- facturas
@app.route("/facturas")
def facturas():
    n = request.args.get("n", type=int)
    bloques = [tabla("Facturas generadas", ["N°", "Venta", "Lote", "Total", "Pago", ""],
                     [(v.factura.numero_factura, v.id_venta, v.id_lote, money(v.factura.total), v.factura.forma_pago,
                       dict(enlaces=[("Ver", url_for("facturas", n=v.factura.numero_factura)),
                                     ("PDF", url_for("descargar_factura", n=v.factura.numero_factura, formato="pdf")),
                                     ("Excel", url_for("descargar_factura", n=v.factura.numero_factura, formato="xlsx"))]))
                      for v in L.ventas_registradas if v.factura])]
    for v in L.ventas_registradas:
        if v.factura and v.factura.numero_factura == n:
            bloques.append(dict(tipo="pre", texto=v.factura.texto_factura()))
    return pagina("facturas", "Facturas", bloques, "RF-41")


# ----------------------------------------------------------------- abonos
@app.route("/abonos")
def abonos():
    pend = L.consultar_saldos_pendientes()
    return pagina("abonos", "Abonos y saldos pendientes", [
        form(url_for("abono_nuevo"), [
            campo("id_venta", "Venta a crédito", "select",
                  [(a["id_venta"], f"Venta {a['id_venta']} - {a['comprador']}") for a in pend]),
            campo("monto", "Monto del abono ($)", "number", paso="any")], "Registrar abono"),
        tabla("Saldos pendientes", ["Venta", "Comprador", "Saldo pendiente"],
              [(a["id_venta"], a["comprador"], money(a["saldo_pendiente"])) for a in pend])], "RF-43, RF-44")


@app.post("/abonos/nuevo")
@roles("administrador", "registrador")
def abono_nuevo():
    try:
        r = L.registrar_abono(len(L.abonos_registrados) + 1, num("id_venta", True), num("monto"))
    except ValueError:
        return resultado((None, "Revisa el monto."), "", "abonos")
    return resultado(r, "Abono registrado.", "abonos")


# -------------------------------------------------------------- ganancias
@app.route("/ganancias")
def ganancias():
    vendidos = [l for l in L.lotes_registrados if l.estado == "vendido"]
    est = L.generar_estadisticas_ventas_por_tipo()
    bloques = [dict(tipo="texto", texto=f"Ganancia general acumulada: {money(L.calcular_ganancia_general())}"),
               tabla("Ganancia por lote", ["Lote", "Tipo", "Peso kg", "Costo compra", "Venta", "Ganancia", "Ganancia/kg"],
                     [(l.id_lote, l.tipo_animal, f"{l.peso_total_kg():,.0f}", money(l.costo_total_compra()),
                       money(l.precio_venta), money(l.ganancia_total()), money(l.ganancia_por_kilo())) for l in vendidos])]
    if est:
        bloques.append(dict(tipo="texto", texto="Ventas por tipo de animal: " + str(est)))
    return pagina("ganancias", "Ganancias", bloques, "RF-19 a RF-25")


# ---------------------------------------------------------------- buscar
@app.route("/buscar")
def buscar():
    bloques = [
        form(url_for("buscar"), [campo("ica", "Registro ICA", valor=request.args.get("ica", ""))], "Buscar animal", "Buscar animal por ICA").copy(),
        form(url_for("buscar"), [campo("comprador", "Documento o nombre del comprador", valor=request.args.get("comprador", ""))],
             "Buscar", "Lotes por comprador").copy(),
        form(url_for("buscar"), [campo("desde", "Desde", "date", valor=request.args.get("desde", "")),
                                 campo("hasta", "Hasta", "date", valor=request.args.get("hasta", ""))],
             "Buscar", "Lotes por rango de fechas").copy(),
    ]
    for b in bloques:
        b["metodo"] = "get"
    linea = lambda l: (l.id_lote, l.tipo_animal, l.fecha_registro.strftime("%Y-%m-%d"), l.estado)
    cols = ["Lote", "Tipo", "Fecha", "Estado"]
    if request.args.get("ica"):
        a, l = L.buscar_animal_por_ica(request.args["ica"])
        bloques.append(tabla("Resultado", ["ICA", "Tipo", "Peso kg", "Raza", "Lote"],
                             [(a.registro_ica, l.tipo_animal, a.peso, a.raza, l.id_lote)] if a else []))
    if request.args.get("comprador"):
        bloques.append(tabla("Lotes del comprador", cols, [linea(l) for l in L.buscar_lotes_por_comprador(request.args["comprador"])]))
    if request.args.get("desde") and request.args.get("hasta"):
        try:
            r = L.buscar_lotes_por_rango_fechas(date.fromisoformat(request.args["desde"]), date.fromisoformat(request.args["hasta"]))
            bloques.append(tabla("Lotes en el rango", cols, [linea(l) for l in r]))
        except ValueError:
            flash("Fechas inválidas.", "error")
    return pagina("buscar", "Búsquedas", bloques, "RF-13, RF-37 a RF-40")


# ------------------------------------------------- configuracion/auditoria
@app.route("/configuracion")
@roles("administrador")
def configuracion():
    return pagina("configuracion", "Configurar rango de animales por lote", [
        dict(tipo="texto", texto=f"Rango actual: {L.texto_rango_animales()} animales."),
        form(url_for("configuracion_guardar"), [campo("minimo", "Mínimo", "number"), campo("maximo", "Máximo", "number")],
             "Guardar rango")], "RF-36")


@app.post("/configuracion")
@roles("administrador")
def configuracion_guardar():
    try:
        r = L.configurar_rango_animales(num("minimo", True), num("maximo", True))
    except ValueError:
        return resultado((None, "Escribe números enteros."), "", "configuracion")
    return resultado(r, "Rango actualizado.", "configuracion")


@app.route("/auditoria")
def auditoria():
    filas = [(a.id_auditoria, a.fecha_hora.strftime("%Y-%m-%d %H:%M:%S"), a.usuario, a.operacion)
             for a in reversed(L.auditorias_registradas)]
    return pagina("auditoria", "Auditoría", [tabla("Operaciones registradas", ["#", "Fecha y hora", "Usuario", "Operación"], filas)], "RF-29")


# ---------------------------------------------------- sesión y permisos
@app.before_request
def cargar_sesion():
    uid = session.get("uid")
    usuario = next((u for u in L.usuarios_registrados if u.id_usuario == uid), None) if uid is not None else None
    L.sesion_actual["usuario"] = usuario
    if usuario is None and request.endpoint not in PUBLICAS and request.endpoint != "static":
        return redirect(url_for("login"))


@app.context_processor
def contexto():
    u = L.sesion_actual["usuario"]
    menu = [(c, n) for c, n, r in MENU if u and (r is None or u.rol in r)]
    return dict(menu=menu, usuario=u)


@app.route("/login")
def login():
    if L.sesion_actual["usuario"]:
        return redirect(url_for("inicio"))
    bloques = []
    if L.usuarios_registrados:
        bloques.append(form(url_for("login_post"), [campo("usuario", "Usuario"),
                       campo("contrasena", "Contraseña", "password")], "Iniciar sesión"))
    else:
        bloques.append(dict(tipo="texto", texto="Aún no hay usuarios. Crea la primera cuenta (debe ser administrador) o restaura una copia de seguridad."))
        bloques.append(form(url_for("primer_admin"), [
            campo("nombre", "Nombre completo"), campo("usuario", "Usuario"),
            campo("contrasena", "Contraseña", "password")], "Crear administrador", "Primer administrador"))
        bloques.append(form(url_for("subir_respaldo"), [campo("archivo", "Archivo de copia (.pkl)", "file")],
                            "Restaurar copia", "Restaurar una copia de seguridad"))
    return pagina("login", "Iniciar sesión", bloques, "RF-26, RF-27")


@app.post("/login")
def login_post():
    u, error = L.iniciar_sesion(request.form.get("usuario", "").strip(), request.form.get("contrasena", ""))
    if error:
        flash(error, "error")
        return redirect(url_for("login"))
    session["uid"] = u.id_usuario
    L.registrar_auditoria(f"Inicio de sesion de '{u.usuario}'")
    flash(f"Bienvenido, {u.nombre or u.usuario} (rol: {u.rol}).", "ok")
    return redirect(url_for("inicio"))


@app.post("/logout")
def logout():
    L.cerrar_sesion()
    session.clear()
    return redirect(url_for("login"))


@app.post("/primer-admin")
def primer_admin():
    if L.usuarios_registrados:
        return redirect(url_for("login"))
    u, error = L.registrar_usuario(1, request.form["nombre"], request.form["usuario"].strip(),
                                   request.form["contrasena"], "administrador")
    if error:
        flash(error, "error")
    else:
        flash("Administrador creado. Ya puedes iniciar sesión.", "ok")
    return redirect(url_for("login"))


# --------------------------------------------------------------- usuarios
@app.route("/usuarios")
@roles("administrador")
def usuarios():
    return pagina("usuarios", "Usuarios y roles", [
        form(url_for("usuario_nuevo"), [
            campo("id_usuario", "ID de usuario", "number", valor=len(L.usuarios_registrados) + 1),
            campo("nombre", "Nombre completo"), campo("usuario", "Usuario"),
            campo("contrasena", "Contraseña", "password"),
            campo("rol", "Rol", "select", [(r, r) for r in ("administrador", "registrador", "consulta")])],
            "Crear usuario"),
        dict(tipo="texto", texto="Administrador: todo. Registrador: registra y edita (lotes, animales, subasta, ventas, abonos). Consulta: solo consulta."),
        tabla("Usuarios", ["ID", "Nombre", "Usuario", "Rol", "Activo"],
              [(u.id_usuario, u.nombre, u.usuario, u.rol, "Sí" if u.estado else "No") for u in L.usuarios_registrados])],
        "RF-26 a RF-28")


@app.post("/usuarios/nuevo")
@roles("administrador")
def usuario_nuevo():
    try:
        r = L.registrar_usuario(num("id_usuario", True), request.form["nombre"], request.form["usuario"].strip(),
                                request.form["contrasena"], request.form["rol"])
    except ValueError:
        return resultado((None, "El ID debe ser un número."), "", "usuarios")
    return resultado(r, "Usuario creado.", "usuarios")


# --------------------------------------------------- exportar PDF / Excel
def hacer_pdf(titulo, texto):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import simpleSplit
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    ancho, alto = A4
    y = alto - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, titulo)
    y -= 28
    c.setFont("Courier", 9)
    for linea in texto.splitlines() or [""]:
        for parte in simpleSplit(linea or " ", "Courier", 9, ancho - 80):
            if y < 50:
                c.showPage()
                c.setFont("Courier", 9)
                y = alto - 50
            c.drawString(40, y, parte)
            y -= 12
    c.save()
    buf.seek(0)
    return buf


def hacer_excel(titulo, texto):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Reporte"
    ws.append([titulo])
    ws.append([])
    for linea in texto.splitlines():
        ws.append([p.strip() for p in linea.split(":", 1)] if ": " in linea else [linea])
    ws.column_dimensions["A"].width = 48
    ws.column_dimensions["B"].width = 36
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def entregar(formato, titulo, texto, nombre):
    if formato == "pdf":
        return send_file(hacer_pdf(titulo, texto), as_attachment=True, download_name=nombre + ".pdf",
                         mimetype="application/pdf")
    return send_file(hacer_excel(titulo, texto), as_attachment=True, download_name=nombre + ".xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/facturas/<int:n>.<formato>")
def descargar_factura(n, formato):
    v = next((v for v in L.ventas_registradas if v.factura and v.factura.numero_factura == n), None)
    if v is None or formato not in ("pdf", "xlsx"):
        flash("Factura no encontrada.", "error")
        return redirect(url_for("facturas"))
    return entregar(formato, f"Factura N° {n}", v.factura.texto_factura(), f"factura_{n}")


# --------------------------------------------------------------- reportes
TIPOS_REPORTE = [("lote", "Reporte por lote"), ("jornada", "Reporte consolidado por jornada"),
                 ("tipo", "Ventas por tipo de animal"), ("comparativa", "Ganancia comparativa por jornada"),
                 ("mensual", "Ganancias mensuales"), ("anual", "Ganancias anuales")]


def formulario_reporte():
    return form(url_for("reporte_generar"), [
        campo("tipo", "Tipo de reporte", "select", TIPOS_REPORTE),
        campo("numero", "N° de lote o de jornada (según el tipo)", "number", req=False),
        campo("mes", "Mes (1-12, solo mensual)", "number", req=False),
        campo("anio", "Año (mensual y anual)", "number", valor=date.today().year, req=False)], "Generar reporte")


@app.route("/reportes")
def reportes():
    return pagina("reportes", "Generar reportes", [formulario_reporte()], "RF-23 a RF-25")


@app.post("/reportes")
def reporte_generar():
    rid = len(REPORTES) + 1
    tipo = request.form["tipo"]
    try:
        if tipo in ("lote", "jornada"):
            n = num("numero", True)
            contenido = (L.ReportePorLote(rid, n).generar_reporte_por_lote(n) if tipo == "lote"
                         else L.ReporteConsolidadoPorJornada(rid, n).generar_reporte_jornada(n))
        elif tipo == "tipo":
            contenido = "ESTADISTICAS DE VENTAS POR TIPO DE ANIMAL\n" + L.ReporteVentasPorTipoAnimal(rid).generar_reporte()
        elif tipo == "comparativa":
            contenido = L.ReporteGananciaComparativaPorJornada(rid).generar_reporte()
        else:
            anio = num("anio", True)
            if not 2000 <= anio <= 2100:
                return resultado((None, "El año debe estar entre 2000 y 2100."), "", "reportes")
            if tipo == "mensual":
                mes = num("mes", True)
                if not 1 <= mes <= 12:
                    return resultado((None, "El mes debe estar entre 1 y 12."), "", "reportes")
                contenido, _ = L.generar_reporte_mensual(mes, anio)
            else:
                contenido, _ = L.generar_reporte_anual(anio)
    except ValueError:
        return resultado((None, "Escribe números enteros en los campos que corresponden."), "", "reportes")
    titulo = dict(TIPOS_REPORTE)[tipo]
    REPORTES[rid] = (titulo, contenido)
    L.registrar_auditoria(f"Generacion de reporte: {titulo}")
    return pagina("reportes", "Generar reportes", [
        formulario_reporte(),
        dict(tipo="pre", texto=contenido),
        dict(tipo="texto", texto="Descargar:", enlaces=[("PDF", url_for("descargar_reporte", rid=rid, formato="pdf")),
                                                         ("Excel", url_for("descargar_reporte", rid=rid, formato="xlsx"))])],
        "RF-23 a RF-25")


@app.route("/reportes/<int:rid>.<formato>")
def descargar_reporte(rid, formato):
    if rid not in REPORTES or formato not in ("pdf", "xlsx"):
        flash("Reporte no encontrado; genéralo de nuevo.", "error")
        return redirect(url_for("reportes"))
    titulo, contenido = REPORTES[rid]
    return entregar(formato, titulo, contenido, f"reporte_{rid}")


# ---------------------------------------------------------------- respaldo
@app.route("/respaldo")
@roles("administrador")
def respaldo():
    L.descubrir_respaldos_en_disco()
    filas = [(r.id_respaldo, str(r.fecha), os.path.basename(r.ruta_archivo),
              dict(enlaces=[("Descargar", url_for("respaldo_descargar", id_respaldo=r.id_respaldo))]),
              dict(boton="Restaurar", accion=url_for("respaldo_restaurar", id_respaldo=r.id_respaldo)))
             for r in L.respaldos_registrados]
    return pagina("respaldo", "Respaldo y restauración", [
        form(url_for("respaldo_crear"), [], "Crear copia de seguridad", "Copia de seguridad"),
        form(url_for("subir_respaldo"), [campo("archivo", "Archivo de copia (.pkl)", "file")],
             "Restaurar desde archivo", "Restaurar desde un archivo (reemplaza TODA la información actual)"),
        tabla("Copias disponibles", ["ID", "Fecha", "Archivo", "", ""], filas),
        dict(tipo="texto", texto="Descarga la copia a tu computador: en el servidor gratuito los archivos se borran al reiniciar.")],
        "RF-48, RF-49")


@app.post("/respaldo/crear")
@roles("administrador")
def respaldo_crear():
    r, error = L.realizar_respaldo()
    flash(error if error else f"Copia #{r.id_respaldo} creada.", "error" if error else "ok")
    return redirect(url_for("respaldo"))


@app.post("/respaldo/restaurar/<int:id_respaldo>")
@roles("administrador")
def respaldo_restaurar(id_respaldo):
    ok, error = L.restaurar_respaldo(id_respaldo)
    flash(error if error else "Copia restaurada: la información fue reemplazada.", "error" if error else "ok")
    return redirect(url_for("respaldo" if L.sesion_actual["usuario"] else "login"))


@app.route("/respaldo/<int:id_respaldo>/descargar")
@roles("administrador")
def respaldo_descargar(id_respaldo):
    r = next((r for r in L.respaldos_registrados if r.id_respaldo == id_respaldo), None)
    if r is None or not os.path.isfile(r.ruta_archivo):
        flash("No se encontró el archivo de esa copia.", "error")
        return redirect(url_for("respaldo"))
    return send_file(r.ruta_archivo, as_attachment=True, download_name=os.path.basename(r.ruta_archivo))


@app.post("/respaldo/subir")
def subir_respaldo():
    u = L.sesion_actual["usuario"]
    if L.usuarios_registrados and (u is None or u.rol != "administrador"):
        flash("Solo un administrador puede restaurar una copia.", "error")
        return redirect(url_for("login"))
    archivo = request.files.get("archivo")
    if not archivo or not archivo.filename:
        flash("Selecciona el archivo de la copia.", "error")
        return redirect(url_for("respaldo" if u else "login"))
    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as tmp:
        archivo.save(tmp.name)
    ok, error = L.restaurar_informacion_desde_archivo(tmp.name)
    os.unlink(tmp.name)
    flash(error if error else "Copia restaurada: la información fue reemplazada.", "error" if error else "ok")
    return redirect(url_for("respaldo") if L.sesion_actual["usuario"] and L.usuarios_registrados else url_for("login"))


# El administrador inicial puede definirse con variables de entorno (Render)
if os.environ.get("ADMIN_USUARIO") and os.environ.get("ADMIN_CONTRASENA") and not L.usuarios_registrados:
    L.registrar_usuario(1, "Administrador", os.environ["ADMIN_USUARIO"], os.environ["ADMIN_CONTRASENA"], "administrador")


if __name__ == "__main__":
    app.run(debug=True)
