import os
import sys
from datetime import datetime
import time
import logging
import sqlite3

# Añadir el directorio raíz del proyecto al path de Python
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database.sqlite_db import SQLiteDB

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_sqlite_logs():
    """Verificar el estado actual de los logs en SQLite"""
    try:
        conn = sqlite3.connect('instance/local_gate.db')
        cursor = conn.execute('SELECT * FROM pending_logs ORDER BY timestamp DESC')
        logs = cursor.fetchall()
        logger.info(f"Logs pendientes en SQLite: {len(logs)}")
        for log in logs:
            logger.info(f"Log: {log}")
        conn.close()
        return logs
    except Exception as e:
        logger.error(f"Error verificando logs en SQLite: {e}")
        return []

def test_log_sync():
    """Probar la sincronización de logs"""
    # Verificar estado inicial
    logger.info("=== Estado inicial de los logs en SQLite ===")
    check_sqlite_logs()
    
    # Crear algunos logs de prueba
    sqlite_db = SQLiteDB('instance/local_gate.db')
    
    # Crear 3 logs de prueba
    test_logs = []
    for i in range(3):
        log_id = sqlite_db.create_access_log(
            plate_number=f"TEST{int(time.time())}-{i}",
            gate_id="EC:64:C9:AC:C9:A4",
            access_granted=True,
            confidence_score=0.95
        )
        test_logs.append(log_id)
        logger.info(f"Creado log de prueba {i+1} con ID: {log_id}")
    
    # Verificar que se crearon los logs
    logger.info("\n=== Estado después de crear logs ===")
    check_sqlite_logs()
    
    # Esperar a que ocurra la sincronización
    logger.info("\nEsperando 30 segundos para que ocurra la sincronización...")
    time.sleep(30)
    
    # Verificar estado final
    logger.info("\n=== Estado final de los logs ===")
    final_logs = check_sqlite_logs()
    
    # Verificar si los logs se sincronizaron
    synced_count = 0
    for log in final_logs:
        if log[6] == 'synced':  # sync_status está en el índice 6
            synced_count += 1
    
    logger.info(f"\nLogs sincronizados: {synced_count} de {len(test_logs)}")

if __name__ == "__main__":
    test_log_sync()
    # conn = sqlite3.connect('instance/local_gate.db')
    # cursor = conn.execute('SELECT * FROM authorized_vehicles')
    # vehicles = cursor.fetchall()
    # logger.info(f"Vehículos autorizados: {len(vehicles)}")
    # for vehicle in vehicles:
    #     logger.info(f"Vehículo: {vehicle}")
