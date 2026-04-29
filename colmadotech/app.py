from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'colmadotech2025'

DB_PATH = 'colmadotech.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            categoria TEXT NOT NULL,
            precio_compra REAL NOT NULL,
            precio_venta REAL NOT NULL,
            cantidad INTEGER NOT NULL DEFAULT 0,
            cantidad_minima INTEGER NOT NULL DEFAULT 5,
            fecha_vencimiento TEXT,
            creado_en TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            nota TEXT,
            fecha TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (producto_id) REFERENCES productos(id)
        );
    ''')
    # Insertar datos de ejemplo si la tabla está vacía
    cursor = conn.execute("SELECT COUNT(*) FROM productos")
    if cursor.fetchone()[0] == 0:
        productos_ejemplo = [
            ('Arroz Cristal 5lb', 'Granos', 120, 145, 30, 10, '2025-12-01'),
            ('Aceite Vegetal 1L', 'Aceites', 90, 115, 12, 5, '2026-03-15'),
            ('Salami Induveca', 'Embutidos', 55, 75, 8, 5, '2025-06-20'),
            ('Habichuela Negra 1lb', 'Granos', 35, 50, 25, 8, None),
            ('Pepsi 2L', 'Bebidas', 80, 105, 3, 6, '2025-09-10'),
            ('Pan de agua x5', 'Panadería', 20, 30, 20, 10, '2025-05-02'),
            ('Leche Lechosa 1L', 'Lácteos', 75, 95, 15, 5, '2025-05-15'),
            ('Detergente Fab', 'Limpieza', 60, 80, 18, 6, None),
        ]
        conn.executemany(
            "INSERT INTO productos (nombre, categoria, precio_compra, precio_venta, cantidad, cantidad_minima, fecha_vencimiento) VALUES (?,?,?,?,?,?,?)",
            productos_ejemplo
        )
    conn.commit()
    conn.close()

@app.route('/')
def dashboard():
    conn = get_db()
    total_productos = conn.execute("SELECT COUNT(*) FROM productos").fetchone()[0]
    stock_bajo = conn.execute("SELECT COUNT(*) FROM productos WHERE cantidad <= cantidad_minima").fetchone()[0]
    valor_inventario = conn.execute("SELECT SUM(precio_compra * cantidad) FROM productos").fetchone()[0] or 0
    ganancia_potencial = conn.execute("SELECT SUM((precio_venta - precio_compra) * cantidad) FROM productos").fetchone()[0] or 0
    
    hoy = datetime.now().strftime('%Y-%m-%d')
    proximos_vencer = conn.execute(
        "SELECT * FROM productos WHERE fecha_vencimiento IS NOT NULL AND fecha_vencimiento <= date('now', '+30 days') ORDER BY fecha_vencimiento ASC LIMIT 5"
    ).fetchall()
    
    alertas = conn.execute(
        "SELECT * FROM productos WHERE cantidad <= cantidad_minima ORDER BY cantidad ASC LIMIT 5"
    ).fetchall()
    
    movimientos_recientes = conn.execute(
        "SELECT m.*, p.nombre FROM movimientos m JOIN productos p ON m.producto_id = p.id ORDER BY m.fecha DESC LIMIT 8"
    ).fetchall()
    
    conn.close()
    return render_template('dashboard.html',
        total_productos=total_productos,
        stock_bajo=stock_bajo,
        valor_inventario=valor_inventario,
        ganancia_potencial=ganancia_potencial,
        proximos_vencer=proximos_vencer,
        alertas=alertas,
        movimientos_recientes=movimientos_recientes
    )

@app.route('/productos')
def productos():
    conn = get_db()
    buscar = request.args.get('buscar', '')
    categoria = request.args.get('categoria', '')
    query = "SELECT * FROM productos WHERE 1=1"
    params = []
    if buscar:
        query += " AND nombre LIKE ?"
        params.append(f'%{buscar}%')
    if categoria:
        query += " AND categoria = ?"
        params.append(categoria)
    query += " ORDER BY nombre ASC"
    productos = conn.execute(query, params).fetchall()
    categorias = conn.execute("SELECT DISTINCT categoria FROM productos ORDER BY categoria").fetchall()
    conn.close()
    return render_template('productos.html', productos=productos, categorias=categorias, buscar=buscar, categoria_sel=categoria)

@app.route('/productos/nuevo', methods=['GET','POST'])
def nuevo_producto():
    if request.method == 'POST':
        nombre = request.form['nombre']
        categoria = request.form['categoria']
        precio_compra = float(request.form['precio_compra'])
        precio_venta = float(request.form['precio_venta'])
        cantidad = int(request.form['cantidad'])
        cantidad_minima = int(request.form['cantidad_minima'])
        fecha_vencimiento = request.form.get('fecha_vencimiento') or None
        conn = get_db()
        conn.execute(
            "INSERT INTO productos (nombre, categoria, precio_compra, precio_venta, cantidad, cantidad_minima, fecha_vencimiento) VALUES (?,?,?,?,?,?,?)",
            (nombre, categoria, precio_compra, precio_venta, cantidad, cantidad_minima, fecha_vencimiento)
        )
        conn.commit()
        pid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO movimientos (producto_id, tipo, cantidad, nota) VALUES (?, 'entrada', ?, 'Stock inicial')", (pid, cantidad))
        conn.commit()
        conn.close()
        flash('Producto agregado exitosamente ✅', 'success')
        return redirect(url_for('productos'))
    return render_template('form_producto.html', producto=None)

@app.route('/productos/editar/<int:id>', methods=['GET','POST'])
def editar_producto(id):
    conn = get_db()
    producto = conn.execute("SELECT * FROM productos WHERE id=?", (id,)).fetchone()
    if request.method == 'POST':
        conn.execute(
            "UPDATE productos SET nombre=?, categoria=?, precio_compra=?, precio_venta=?, cantidad_minima=?, fecha_vencimiento=? WHERE id=?",
            (request.form['nombre'], request.form['categoria'], float(request.form['precio_compra']),
             float(request.form['precio_venta']), int(request.form['cantidad_minima']),
             request.form.get('fecha_vencimiento') or None, id)
        )
        conn.commit()
        conn.close()
        flash('Producto actualizado ✅', 'success')
        return redirect(url_for('productos'))
    conn.close()
    return render_template('form_producto.html', producto=producto)

@app.route('/productos/eliminar/<int:id>', methods=['POST'])
def eliminar_producto(id):
    conn = get_db()
    conn.execute("DELETE FROM movimientos WHERE producto_id=?", (id,))
    conn.execute("DELETE FROM productos WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash('Producto eliminado', 'info')
    return redirect(url_for('productos'))

@app.route('/movimiento/<int:id>', methods=['POST'])
def registrar_movimiento(id):
    tipo = request.form['tipo']
    cantidad = int(request.form['cantidad'])
    nota = request.form.get('nota', '')
    conn = get_db()
    if tipo == 'salida':
        prod = conn.execute("SELECT cantidad FROM productos WHERE id=?", (id,)).fetchone()
        if prod['cantidad'] < cantidad:
            flash('No hay suficiente stock ❌', 'danger')
            conn.close()
            return redirect(url_for('productos'))
        conn.execute("UPDATE productos SET cantidad = cantidad - ? WHERE id=?", (cantidad, id))
    else:
        conn.execute("UPDATE productos SET cantidad = cantidad + ? WHERE id=?", (cantidad, id))
    conn.execute("INSERT INTO movimientos (producto_id, tipo, cantidad, nota) VALUES (?,?,?,?)", (id, tipo, cantidad, nota))
    conn.commit()
    conn.close()
    flash(f'Movimiento registrado ✅', 'success')
    return redirect(url_for('productos'))

@app.route('/reportes')
def reportes():
    conn = get_db()
    por_categoria = conn.execute(
        "SELECT categoria, COUNT(*) as total, SUM(cantidad) as stock, SUM(precio_compra*cantidad) as valor FROM productos GROUP BY categoria"
    ).fetchall()
    mas_vendidos = conn.execute(
        "SELECT p.nombre, SUM(m.cantidad) as total FROM movimientos m JOIN productos p ON m.producto_id=p.id WHERE m.tipo='salida' GROUP BY p.id ORDER BY total DESC LIMIT 5"
    ).fetchall()
    historial = conn.execute(
        "SELECT m.*, p.nombre FROM movimientos m JOIN productos p ON m.producto_id=p.id ORDER BY m.fecha DESC LIMIT 30"
    ).fetchall()
    conn.close()
    return render_template('reportes.html', por_categoria=por_categoria, mas_vendidos=mas_vendidos, historial=historial)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
