#!/usr/bin/env python3
"""
Test final mostrando el FEC en acción con transmisión de imagen.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from controller.simulation_mgr import OFDMSimulationManager
import numpy as np

# Crear el manager
sim = OFDMSimulationManager()

# Usar la imagen de ejemplo
image_path = "imagenes/cameraman.jpg"

if not os.path.exists(image_path):
    print(f"Error: No se encuentra {image_path}")
    sys.exit(1)

print("=" * 80)
print("DEMOSTRACIÓN: TRANSMISIÓN DE IMAGEN CON Y SIN FEC")
print("=" * 80)

# Parámetros
bw_idx = 4  # 10 MHz
profile_idx = 1  # Normal  
mod_type = 2  # 16-QAM
snr_db = 8  # dB - SNR donde FEC debería mostrar mejora clara
num_paths = 3  # Canal multipath

print(f"\nConfiguraci\u00f3n de Simulaci\u00f3n:")
print(f"  Ancho de Banda:        10 MHz")
print(f"  Modulaci\u00f3n:           16-QAM (4 bits/símbolo)")
print(f"  SNR:                   {snr_db} dB")
print(f"  Caminos del Canal:     {num_paths} (Rayleigh multipath)")
print(f"  Codificación:          CRC24A + Convolucional (TS 36.212)")
print(f"  Decodificador:         Hard-decision Viterbi con terminación")

print("\n" + "=" * 80)
print("ESCENARIO 1: TRANSMISIÓN SIN FEC")
print("=" * 80)

result_no_fec = sim.run_image_transmission(
    image_path, bw_idx, profile_idx, mod_type, snr_db, num_paths, enable_fec=False
)

if result_no_fec["success"]:
    print(f"✓ Transmisión completada")
    print(f"  BER:     {result_no_fec['ber']:.6f} ({result_no_fec['ber']*100:.2f}%)")
    print(f"  Errores: {int(result_no_fec['ber'] * 250 * 250 * 8)} bits de {250*250*8} bits totales")
    print(f"  Estado:  {result_no_fec['info']}")
else:
    print(f"✗ Error: {result_no_fec['error']}")

print("\n" + "=" * 80)
print("ESCENARIO 2: TRANSMISIÓN CON FEC (CRC24A + Convolucional)")
print("=" * 80)

result_with_fec = sim.run_image_transmission(
    image_path, bw_idx, profile_idx, mod_type, snr_db, num_paths, enable_fec=True
)

if result_with_fec["success"]:
    print(f"✓ Transmisión completada")
    print(f"  BER:     {result_with_fec['ber']:.6f} ({result_with_fec['ber']*100:.2f}%)")
    print(f"  Errores: {int(result_with_fec['ber'] * 250 * 250 * 8)} bits de {250*250*8} bits totales")
    print(f"  Estado:  {result_with_fec['info']}")
else:
    print(f"✗ Error: {result_with_fec['error']}")

print("\n" + "=" * 80)
print("ANÁLISIS COMPARATIVO")
print("=" * 80)

if result_no_fec["success"] and result_with_fec["success"]:
    ber_no_fec = result_no_fec['ber']
    ber_with_fec = result_with_fec['ber']
    
    print(f"\nBER (Bit Error Rate):")
    print(f"  Sin FEC:   {ber_no_fec:.6f} ({ber_no_fec*100:.2f}%)")
    print(f"  Con FEC:   {ber_with_fec:.6f} ({ber_with_fec*100:.2f}%)")
    
    if ber_no_fec > 0:
        mejora = ((ber_no_fec - ber_with_fec) / ber_no_fec * 100)
        print(f"  Mejora:    {mejora:.1f}%")
    
    # Estimación de bits correctos
    total_bits = 250 * 250 * 8
    errores_no_fec = int(ber_no_fec * total_bits)
    errores_con_fec = int(ber_with_fec * total_bits)
    
    print(f"\nErrores en {total_bits} bits transmitidos:")
    print(f"  Sin FEC:   {errores_no_fec} errores")
    print(f"  Con FEC:   {errores_con_fec} errores")
    print(f"  Diferencia: {errores_no_fec - errores_con_fec} menos errores con FEC")
    
    if ber_with_fec < ber_no_fec:
        print(f"\n✓ FEC ESTÁ FUNCIONANDO CORRECTAMENTE")
        print(f"  El Forward Error Correction está reduciendo significativamente")
        print(f"  el número de errores de bits transmitidos.")
    else:
        print(f"\n✗ FEC NO ESTÁ MEJORANDO")
        
    if "OK" in result_with_fec['info']:
        print(f"✓ CRC: OK - La secuencia de datos se decodificó correctamente")
    else:
        print(f"✗ CRC: FAIL - Hay errores no recuperables en los datos")

print("\n" + "=" * 80)
print("CONCLUSIÓN")
print("=" * 80)
print("""
El FEC (Forward Error Correction) es una técnica que añade redundancia a los datos
para poder detectar y corregir errores de transmisión causados por ruido del canal.

En esta simulación:
1. Los datos se codifican con CRC para detección de errores
2. Se aplica codificación convolucional para corrección de errores
3. El receptor decodifica usando el algoritmo Viterbi (optimal para canales gaussianos)
4. Se verifica la integridad con el CRC

Resultado esperado: FEC debe mejorar significativamente el BER a costa de:
  - Mayor complejidad computacional
  - Mayor uso de ancho de banda (expansión de 3x en este caso)
  - Mayor latencia de procesamiento

Este es un trade-off fundamental en comunicaciones: confiabilidad vs eficiencia.
""")

print("=" * 80)
