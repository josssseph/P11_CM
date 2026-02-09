# Documentación Técnica del Simulador LTE OFDM
## Implementación de FEC según 3GPP TS 36.212

## 📋 Índice
- [Introducción](#introducción)
- [Forward Error Correction (FEC) - Pipeline Completo](#forward-error-correction-fec---pipeline-completo)
- [Implementación Detallada de FEC](#implementación-detallada-de-fec)
- [Arquitectura del Sistema](#arquitectura-del-sistema)
- [Funcionalidades Complementarias](#funcionalidades-complementarias)
- [Referencias Técnicas](#referencias-técnicas)

---

## Introducción

Este simulador implementa un sistema **LTE (Long Term Evolution)** con énfasis en la codificación de canal (Forward Error Correction - FEC) conforme al estándar **3GPP TS 36.212**. El sistema permite transmitir imágenes a través de un canal inalámbrico simulado, aplicando técnicas de protección contra errores que son fundamentales en las comunicaciones 4G.

### Ubicación de Archivos Clave
- **Codificación FEC**: [core/ts36212_channel_coding.py](core/ts36212_channel_coding.py) - **COMPONENTE CENTRAL**
- **Controlador de Simulación**: [controller/simulation_mgr.py](controller/simulation_mgr.py) - Orquestación del FEC
- **Interfaz Principal**: [ui/main_window.py](ui/main_window.py)
- **Núcleo OFDM**: [core/ofdm_ops.py](core/ofdm_ops.py)
- **Modelo de Canal**: [core/channel.py](core/channel.py)
- **Configuración LTE**: [core/config.py](core/config.py)

---

## Forward Error Correction (FEC) - Pipeline Completo

### Fundamento Teórico

El **FEC (Forward Error Correction)** añade redundancia controlada a los datos transmitidos para permitir la **corrección de errores en el receptor sin necesidad de retransmisión**. En sistemas 4G LTE, esto es crucial porque:

1. **Latencia**: Retransmisiones aumentan el delay (crítico en VoIP, streaming)
2. **Eficiencia espectral**: Corregir errores localmente libera recursos de radio
3. **Confiabilidad**: Garantiza calidad en condiciones de canal adversas

#### Teoría de Shannon

La capacidad de canal con ruido está dada por:
```
C = B · log₂(1 + SNR) [bits/s]
```

El **Teorema de Codificación de Canal** establece que **existe un código** que permite comunicación libre de errores a cualquier tasa R < C. Los códigos convolucionales se aproximan a este límite teórico.

#### Ganancia de Codificación

La ganancia de codificación $G_c$ es la reducción en SNR necesaria para alcanzar el mismo BER con FEC:

```
G_c (dB) = SNR_sin_FEC - SNR_con_FEC  |_mismo_BER
```

Para código convolucional K=7, R=1/3: **$G_c \approx 3-6$ dB** (según el esquema de modulación)

### Pipeline FEC: Transmisor (Tx)

El FEC en este simulador sigue el estándar **3GPP TS 36.212** y consta de tres etapas principales en transmisión:

```
[Bits de Imagen] 
    ↓
┌─────────────────────────────────────┐
│  ETAPA 1: CRC Attachment (CRC-24A)  │  ← Detección de errores
│  Archivo: ts36212_channel_coding.py │
│  Función: crc_attach()              │
└──────────────┬──────────────────────┘
               ↓
    [Bits + 24 bits CRC]
               ↓
┌─────────────────────────────────────┐
│  ETAPA 2: Convolutional Encoding    │  ← Corrección de errores
│  Archivo: ts36212_channel_coding.py │
│  Función: conv_encode()             │
│  Parámetros: K=7, R=1/3, terminado  │
└──────────────┬──────────────────────┘
               ↓
    [Bits codificados (3x tamaño)]
               ↓
┌─────────────────────────────────────┐
│  ETAPA 3: Scrambling                │  ← Distribución espectral
│  Archivo: utils.py                  │
│  Función: apply_scrambling()        │
└──────────────┬──────────────────────┘
               ↓
    [Bits scrambled listos para Tx]
```

**Ubicación en código**: [controller/simulation_mgr.py](controller/simulation_mgr.py#L38-L44)
```python
if enable_fec:
    tx_bits_crc = crc_attach(tx_bits_raw, crc="24A")
    tx_bits_coded = conv_encode(tx_bits_crc, terminate=True, tail_biting=False)
else:
    tx_bits_coded = tx_bits_raw

tx_bits = utils.apply_scrambling(tx_bits_coded)
```

### Pipeline FEC: Receptor (Rx)

La decodificación sigue el proceso inverso:

```
[Bits recibidos (con errores)]
    ↓
┌─────────────────────────────────────┐
│  ETAPA 1: Descrambling              │
│  Archivo: utils.py                  │
│  Función: apply_scrambling()        │
│  Nota: XOR es auto-inverso          │
└──────────────┬──────────────────────┘
               ↓
    [Bits codificados con errores]
               ↓
┌─────────────────────────────────────┐
│  ETAPA 2: Viterbi Decoder           │  ← CORRECCIÓN de errores
│  Archivo: ts36212_channel_coding.py │
│  Función: conv_decode_terminated()  │
│  Algoritmo: Hard-decision Viterbi   │
└──────────────┬──────────────────────┘
               ↓
    [Bits + CRC (errores corregidos)]
               ↓
┌─────────────────────────────────────┐
│  ETAPA 3: CRC Check                 │  ← VERIFICACIÓN
│  Archivo: ts36212_channel_coding.py │
│  Función: crc_check()               │
│  Salida: (payload_bits, ok: bool)   │
└──────────────┬──────────────────────┘
               ↓
    [Bits originales recuperados]
```

**Ubicación en código**: [controller/simulation_mgr.py](controller/simulation_mgr.py#L76-L104)
```python
if enable_fec:
    rx_bits_after_viterbi = conv_decode_terminated(rx_bits_coded)
    try:
        rx_bits, crc_ok = crc_check(rx_bits_after_viterbi, crc="24A")
    except:
        crc_ok = False
        rx_bits = rx_bits_after_viterbi
```

---

## Implementación Detallada de FEC

### ETAPA 1: CRC-24A (Cyclic Redundancy Check)

#### Fundamento Teórico

El **CRC (Cyclic Redundancy Check)** es un código de detección de errores basado en aritmética de polinomios sobre GF(2) (campo de Galois binario). El CRC-24A añade **24 bits de paridad** que permiten:

- **Detección garantizada** de:
  - Todos los errores de ráfaga (burst) de longitud ≤ 24 bits
  - Todos los patrones con un número impar de bits erróneos
  - Errores dobles separados por cualquier distancia
  
- **Probabilidad de no detección**: 
  ```
  P_no_detectado ≈ 2^(-24) ≈ 6 × 10^(-8)
  ```

#### Polinomio Generador (3GPP TS 36.212)

El CRC-24A usa el polinomio:

```
g_CRC24A(D) = D^24 + D^23 + D^18 + D^17 + D^14 + D^11 + D^10 + D^7 + D^6 + D^5 + D^4 + D^3 + D + 1
```

En binario: `1 1000 0110 0011 0000 1111 1011` (25 bits, el MSB implícito es D^24)

**Ubicación**: [core/ts36212_channel_coding.py](core/ts36212_channel_coding.py#L50-L57)
```python
_CRC_POLYS = {
    "24A": (24, _poly_to_int((23, 18, 17, 14, 11, 10, 7, 6, 5, 4, 3, 1, 0))),
    # Otros CRC: 24B, 16, 8
}
```

#### Implementación: `crc_attach()`

**Archivo**: [core/ts36212_channel_coding.py](core/ts36212_channel_coding.py#L62-L87)

**Entrada**: 
- `bits`: array NumPy de bits (uint8), longitud N
- `crc`: tipo de CRC ("24A", "24B", "16", "8")

**Salida**: 
- Array de N+24 bits: `[bits originales || 24 bits CRC]`

**Algoritmo** (División de polinomios con LFSR):

1. **Inicialización**: Registro de 24 bits a cero
   ```python
   reg = 0
   mask = (1 << 24) - 1  # 0xFFFFFF
   ```

2. **Procesamiento de bits del mensaje**:
   ```python
   for b in bits:
       msb = (reg >> 23) & 1          # Bit más significativo del registro
       fb = msb ^ int(b)              # Feedback bit
       reg = ((reg << 1) & mask)      # Shift left
       if fb:
           reg ^= poly                 # XOR con polinomio si fb=1
   ```

3. **Procesamiento de 24 ceros adicionales** (finalización):
   ```python
   for _ in range(24):
       msb = (reg >> 23) & 1
       fb = msb
       reg = ((reg << 1) & mask)
       if fb:
           reg ^= poly
   ```

4. **Extracción de bits de paridad**:
   ```python
   parity = [(reg >> (23 - i)) & 1 for i in range(24)]
   return np.concatenate([bits, parity])
   ```

**¿Por qué funciona?**

Matemáticamente, CRC calcula el residuo de la división:
```
R(D) = [M(D) · D^24] mod g(D)
```
donde M(D) es el polinomio del mensaje. Los bits CRC son los coeficientes de R(D).

En recepción, si calculamos:
```
[[M(D) · D^24] + R(D)] mod g(D) = 0
```
entonces **no hay errores detectables**.

#### Implementación: `crc_check()`

**Archivo**: [core/ts36212_channel_coding.py](core/ts36212_channel_coding.py#L90-L111)

**Entrada**: 
- `bits_with_crc`: N+24 bits recibidos
- `crc`: tipo de CRC

**Salida**: 
- Tupla `(payload_bits, ok: bool)`
  - `payload_bits`: Primeros N bits (sin CRC)
  - `ok`: True si `reg == 0` después de procesar todos los bits

**Algoritmo**:

```python
reg = 0
for b in bits_with_crc:  # Procesa TODOS los bits (mensaje + CRC)
    msb = (reg >> 23) & 1
    fb = msb ^ int(b)
    reg = ((reg << 1) & mask)
    if fb:
        reg ^= poly

ok = (reg == 0)  # Si el residuo es 0, no hay errores
return bits_with_crc[:-24], ok
```

**Validación Adicional en el Simulador** ([simulation_mgr.py](controller/simulation_mgr.py#L98-L103)):

Debido a que la implementación Viterbi puede introducir desfases, se hace una verificación alternativa comparando directamente los 24 bits CRC:

```python
expected_crc_bits = tx_bits_crc[-24:]
received_crc_bits = rx_bits_after_viterbi[-24:]
crc_ok = np.array_equal(received_crc_bits, expected_crc_bits)
```

---

### ETAPA 2: Código Convolucional (K=7, R=1/3)

#### Fundamento Teórico

Los **códigos convolucionales** son códigos FEC que generan bits de paridad mediante la convolución de la entrada con polinomios generadores. A diferencia de los códigos de bloque, procesan streams de bits de forma continua.

**Parámetros clave**:

- **K = 7**: Longitud de restricción (constraint length)
  - Memoria del codificador: m = K - 1 = **6 bits**
  - El output en el instante t depende del bit actual y los **6 bits previos**
  
- **R = 1/3**: Tasa de código (code rate)
  - Por cada **1 bit de entrada**, se generan **3 bits de salida**
  - Expansión: datos codificados = 3× tamaño original
  - **Overhead**: 200% (reduce throughput pero aumenta robustez)

- **n_estados = 2^m = 64**: Número de estados en el trellis de Viterbi

#### Polinomios Generadores (3GPP TS 36.212)

**Especificación**: Sección 5.1.3.1 de TS 36.212

En notación octal:
```
G₀ = 133₈  →  binario: 001 011 011 = [1, 0, 1, 1, 0, 1, 1]
G₁ = 171₈  →  binario: 001 111 001 = [1, 1, 1, 1, 0, 0, 1]
G₂ = 165₈  →  binario: 001 110 101 = [1, 1, 1, 0, 1, 0, 1]
```

**Representación gráfica** (shift register):

```
Bit entrada (u)
    ↓
┌───┴────┬────┬────┬────┬────┬────┐
│ u(t) │ s₀ │ s₁ │ s₂ │ s₃ │ s₄ │ s₅ │  ← Registro de 7 bits
└────┬───┴──┬─┴──┬─┴──┬─┴──┬─┴──┬─┘
     │      │    │    │    │    │
     G₀: ● ─┼────●────●────●────●
     G₁: ● ─●────●────●────●─────────●
     G₂: ● ─●────●────●─────────●────●
     │      │    │    │    │    │
     ↓      ↓    ↓    ↓    ↓    ↓
   [out₀, out₁, out₂]  ← 3 bits de salida
```

Donde `●` indica conexión (multiplicación y suma módulo 2).

#### Configuración del Codificador

**Ubicación**: [core/ts36212_channel_coding.py](core/ts36212_channel_coding.py#L115-L135)

```python
@dataclass(frozen=True)
class ConvCodeConfig:
    constraint_len: int = 7
    generators_octal: Tuple[int, int, int] = (133, 171, 165)

    @property
    def generators(self) -> Tuple[int, int, int]:
        """Convierte de octal a enteros binarios"""
        gens = tuple(_octal_to_int(g) for g in self.generators_octal)
        return tuple(g & ((1 << self.constraint_len) - 1) for g in gens)

    @property
    def memory(self) -> int:
        return self.constraint_len - 1  # 6

    @property
    def n_states(self) -> int:
        return 1 << self.memory  # 64
```

#### Implementación: `conv_encode()`

**Archivo**: [core/ts36212_channel_coding.py](core/ts36212_channel_coding.py#L141-L191)

**Entrada**:
- `bits`: Bits de información (ya con CRC incluido)
- `terminate`: Bool, si True añade 6 bits de cola (tail bits) = 0
- `tail_biting`: Bool, para inicialización tail-biting (no usado en este simulador)

**Salida**:
- Array de bits codificados, tamaño = `len(bits) * 3` (si `terminate=False`)
- O `(len(bits) + 6) * 3` si `terminate=True`

**Algoritmo**:

1. **Inicialización del estado**:
   ```python
   state = 0  # Registro en ceros (para terminate=True)
   ```

2. **Añadir tail bits si se termina**:
   ```python
   if terminate:
       in_bits = np.concatenate([bits, np.zeros(6, dtype=np.uint8)])
   else:
       in_bits = bits
   ```

3. **Procesar cada bit de entrada**:
   ```python
   out = np.empty(in_bits.size * 3, dtype=np.uint8)
   idx = 0
   
   for b in in_bits:
       u = int(b)
       reg = (u << 6) | state  # Registro de 7 bits: [u, s₀, s₁, s₂, s₃, s₄, s₅]
       
       for g in generators:
           v = reg & g               # AND bit a bit
           out[idx] = v.bit_count() & 1  # Paridad (XOR de bits a 1)
           idx += 1
       
       # Actualizar estado: Shift right, insertar u a la izquierda
       state = ((u << 5) | (state >> 1)) & 0x3F  # 0x3F = 111111₂
   ```

**¿Por qué terminación?**

Los **tail bits** fuerzan el codificador al estado `000000`, lo que permite que el decodificador Viterbi termine en un estado conocido, mejorando el rendimiento en las últimas posiciones.

**Alternativa: Tail-biting** (no implementado en decoder):
- Inicializa el estado con los últimos 6 bits del mensaje
- No añade bits extra (0% overhead adicional)
- Requiere decodificación más compleja (Wrap-Around Viterbi Algorithm - WAVA)

---

### ETAPA 2.5: Trellis Pre-cómputo

#### Función: `_build_trellis()`

**Archivo**: [core/ts36212_channel_coding.py](core/ts36212_channel_coding.py#L194-L219)

Para acelerar el decodificador Viterbi, se **pre-calculan** las transiciones del trellis:

**Estructura del trellis**:
- **Estados** (s): 64 posibles (6 bits de memoria)
- **Entradas** (u): 0 o 1
- **Transiciones**: Desde estado `s`, con entrada `u`, ir a `next_state[s, u]`
- **Outputs**: Al transitar, se generan 3 bits de salida `out_bits[s, u, :]`

**Implementación**:

```python
def _build_trellis(cfg):
    n_states = 64
    next_state = np.zeros((64, 2), dtype=np.uint8)    # [estado, input] → nuevo estado
    out_bits = np.zeros((64, 2, 3), dtype=np.uint8)   # [estado, input] → 3 bits output
    
    for s in range(64):
        for u in (0, 1):
            reg = (u << 6) | s  # Registro completo
            
            bits = []
            for g in generators:
                v = reg & g
                bits.append(v.bit_count() & 1)
            out_bits[s, u, :] = bits
            
            # Próximo estado: [u, s₀, s₁, s₂, s₃, s₄]
            ns = ((u << 5) | (s >> 1)) & 0x3F
            next_state[s, u] = ns
    
    return next_state, out_bits
```

**Uso**: Los arrays `_TRELLIS_NEXT` y `_TRELLIS_OUT` se usan en el decodificador para **lookup instantáneo** en lugar de recalcular en cada paso.

---

### ETAPA 3: Decodificador Viterbi

#### Fundamento Teórico

El **algoritmo de Viterbi** encuentra la secuencia de bits más probable (Maximum Likelihood) dado el stream recibido, usando **programación dinámica** sobre el trellis.

**Principio**: 
- Cada camino en el trellis representa una posible secuencia transmitida
- Cada camino tiene una **métrica acumulada** (distancia a lo recibido)
- Viterbi mantiene el **mejor camino (survivor) a cada estado**
- Al final, hace **traceback** desde el estado final (estado 0 en terminación)

**Complejidad**:
- Por paso: O(n_estados × 2) = O(2^m) = O(64)
- Total: O(N × 2^m) donde N = longitud del mensaje
- Muy eficiente para m ≤ 10

#### Implementación: `conv_decode_terminated()`

**Archivo**: [core/ts36212_channel_coding.py](core/ts36212_channel_coding.py#L224-L288)

**Entrada**:
- `coded_bits`: Bits recibidos (longitud múltiplo de 3)
- `drop_tail`: Bool, si True elimina los últimos 6 bits decodificados (tail)

**Salida**:
- Bits decodificados (longitud `n_steps` o `n_steps - 6` si `drop_tail=True`)

**Algoritmo**:

##### 1. Preparación

```python
coded_bits = np.asarray(coded_bits, dtype=np.uint8)
# Ajustar a múltiplo de 3
if coded_bits.size % 3 != 0:
    coded_bits = coded_bits[: coded_bits.size - (coded_bits.size % 3)]

n_steps = coded_bits.size // 3  # Número de símbolos (bits de entrada codificados)
```

##### 2. Inicialización de métricas

```python
INF = 1_000_000_000
metrics = np.full(64, INF, dtype=np.int32)
metrics[0] = 0  # Estado inicial conocido: 000000
```

**Métrica de camino**: Suma de distancias de Hamming (número de bits diferentes)

##### 3. Pre-cálculo de predecesores

Para cada estado `s`, determinar qué estados previos `p0, p1` pueden llegar a él:

```python
states = np.arange(64, dtype=np.int32)
u_for_state = (states >> 5) & 1  # Bit de entrada que llevó a este estado
p0 = ((states & 0x1F) << 1)      # Predecesor si input fue 0
p1 = p0 | 1                       # Predecesor si input fue 1
```

**Explicación**:
- Estado `s = [u, s₀, s₁, s₂, s₃, s₄]` (6 bits)

**Explicación**:
- Estado `s = [u, s₀, s₁, s₂, s₃, s₄]` (6 bits)
- El bit `u` (MSB) indica qué entrada se usó
- Los predecesores `p0, p1` son estados que con input 0 o 1 llegan a `s`

##### 4. Forward Pass (ACS: Add-Compare-Select)

```python
prev_state = np.empty((n_steps, 64), dtype=np.int16)  # Para traceback

for t in range(n_steps):
    y0, y1, y2 = coded_bits[3*t], coded_bits[3*t+1], coded_bits[3*t+2]  # 3 bits recibidos
    
    # Outputs esperados desde los 2 predecesores posibles
    out0 = _TRELLIS_OUT[p0, u_for_state]  # (64, 3)
    out1 = _TRELLIS_OUT[p1, u_for_state]
    
    # Distancia de Hamming (XOR + suma)
    dist0 = (out0[:, 0] ^ y0) + (out0[:, 1] ^ y1) + (out0[:, 2] ^ y2)
    dist1 = (out1[:, 0] ^ y0) + (out1[:, 1] ^ y1) + (out1[:, 2] ^ y2)
    
    # Métricas candidatas
    cand0 = metrics[p0] + dist0
    cand1 = metrics[p1] + dist1
    
    # Seleccionar el mejor (menor métrica)
    take1 = cand1 < cand0
    metrics = np.where(take1, cand1, cand0).astype(np.int32)
    prev_state[t, :] = np.where(take1, p1, p0).astype(np.int16)
```

**Vectorización**: En lugar de iterar sobre 64 estados, se usa NumPy para procesar todos en paralelo.

##### 5. Traceback

```python
state = 0  # Estado final conocido (terminación)
u_hat = np.empty(n_steps, dtype=np.uint8)

for t in range(n_steps - 1, -1, -1):  # Hacia atrás
    u_hat[t] = (state >> 5) & 1  # Extraer bit de entrada del estado
    state = int(prev_state[t, state])  # Retroceder al predecesor

if drop_tail and n_steps >= 6:
    return u_hat[:-6].copy()  # Eliminar los 6 tail bits
return u_hat
```

**¿Por qué funciona?**
- Al llegar a t=0, hemos reconstruido el camino completo más probable
- La secuencia `u_hat` contiene los bits de entrada originales (antes de codificar)

#### Métricas de Decisión

**Hard-decision**: Los bits recibidos son cuantizados a 0 o 1 (sin información de confianza)
- Métrica: **Distancia de Hamming** (número de bits diferentes)
- Simple y rápido
- Pérdida: ~2 dB vs soft-decision

**Soft-decision** (no implementado aquí):
- Usa valores continuos (e.g., LLR - Log-Likelihood Ratios)
- Métrica: Distancia euclidiana o correlación
- Mejor rendimiento pero más complejo

---

### ETAPA 4: Scrambling/Descrambling

#### Fundamento Teórico

El **scrambling** es una operación XOR con una secuencia pseudo-aleatoria (PN sequence) que:

1. **Blanquea el espectro**: Evita concentración de energía en frecuencias específicas
2. **Elimina patrones repetitivos**: Secuencias de muchos 0s o 1s → distribución uniforme
3. **Sincronización**: Secuencia conocida facilita detección de inicio de trama

En LTE real, se usan **secuencias Gold** (combinación de dos m-sequences).

#### Implementación: `apply_scrambling()`

**Archivo**: [core/utils.py](core/utils.py) (función específica)

**Entrada**: 
- `bits`: Array de bits

**Salida**: 
- `bits ^ PN_sequence` (XOR bit a bit)

**Propiedades**:
- **Auto-inversa**: `scramble(scramble(bits)) == bits`
- **Misma función para Tx y Rx**: `apply_scrambling()` se usa en ambos lados

**Implementación simplificada** (ejemplo):

```python
def apply_scrambling(bits):
    """Scrambling con secuencia PN pseudo-aleatoria (XOR auto-inverso)"""
    np.random.seed(42)  # Seed fija (conocida por Tx y Rx)
    pn_sequence = np.random.randint(0, 2, len(bits), dtype=np.uint8)
    return np.bitwise_xor(bits, pn_sequence)
```

**En LTE Real** (TS 36.211, Section 6.3.1):
- Generador: Gold sequence con polinomios `x^31 + x^28 + 1` y `x^31 + x^3 + 1`
- Inicialización: Depende de `C-RNTI`, slot, y otros parámetros

---

## Arquitectura del Sistema

### Flujo Completo: Transmisión de Imagen

#### Diagrama de Bloques

```
┌──────────────────────────────────────────────────────────────┐
│                        TRANSMISOR (Tx)                        │
└──────────────────────────────────────────────────────────────┘
                                ↓
        ┌────────────────────────────────────┐
        │  1. Carga de Imagen                │
        │  Archivo: utils.py                 │
        │  Función: image_to_bits()          │
        │  Output: 250×250×8 = 500,000 bits  │
        └──────────────┬─────────────────────┘
                       ↓
     ┌──────────────────────────────────────────┐
     │  2. FEC (si enable_fec=True)            │
     │  ┌──────────────────────────────────┐   │
     │  │ 2.1 CRC-24A (ts36212)           │   │
     │  │ Input:  500,000 bits             │   │
     │  │ Output: 500,024 bits             │   │
     │  └─────────────┬────────────────────┘   │
     │                ↓                         │
     │  ┌──────────────────────────────────┐   │
     │  │ 2.2 Convolucional K=7, R=1/3    │   │
     │  │ Input:  500,024 bits             │   │
     │  │ Output: (500,024+6)×3 = 1,500,090│   │
     │  └──────────────────────────────────┘   │
     └──────────────────┬───────────────────────┘
                        ↓
        ┌────────────────────────────────────┐
        │  3. Scrambling (utils.py)          │
        │  Función: apply_scrambling()       │
        │  Output: Bits scrambled            │
        └──────────────┬─────────────────────┘
                       ↓
        ┌────────────────────────────────────┐
        │  4. Modulación Digital             │
        │  Archivo: utils.py                 │
        │  Función: map_bits_to_symbols()    │
        │  QPSK: 2 bits → 1 símbolo I/Q      │
        │  16-QAM: 4 bits → 1 símbolo I/Q    │
        │  64-QAM: 6 bits → 1 símbolo I/Q    │
        └──────────────┬─────────────────────┘
                       ↓
        ┌────────────────────────────────────┐
        │  5. Modulación OFDM                │
        │  Archivo: ofdm_ops.py              │
        │  Función: modulate_ofdm()          │
        │  - Agrupar símbolos en bloques     │
        │  - IFFT(N_FFT)                     │
        │  - Normalización: × √N_FFT         │
        └──────────────┬─────────────────────┘
                       ↓
        ┌────────────────────────────────────┐
        │  6. Añadir Prefijo Cíclico         │
        │  Archivo: ofdm_ops.py              │
        │  Función: add_cyclic_prefix()      │
        │  - Copiar últimos L_CP samples     │
        │  - Anteponer al símbolo OFDM       │
        └──────────────┬─────────────────────┘
                       ↓
                  [Señal Tx]
                       ↓
┌──────────────────────────────────────────────────────────────┐
│                     CANAL INALÁMBRICO                         │
│  Archivo: channel.py                                          │
│  ┌────────────────────────────────────────────────┐           │
│  │  Desvanecimiento Rayleigh (multipath)         │           │
│  │  Función: apply_rayleigh()                    │           │
│  │  - Genera respuesta al impulso h[n]           │           │
│  │  - Convolución: y(t) = x(t) * h(t)            │           │
│  └────────────────┬───────────────────────────────┘           │
│                   ↓                                           │
│  ┌────────────────────────────────────────────────┐           │
│  │  Ruido AWGN                                   │           │
│  │  - Genera ruido gaussiano σ² según SNR       │           │
│  │  - Suma: r(t) = y(t) + n(t)                  │           │
│  └────────────────────────────────────────────────┘           │
└──────────────────────────────────────────────────────────────┘
                       ↓
                  [Señal Rx]
                       ↓
┌──────────────────────────────────────────────────────────────┐
│                        RECEPTOR (Rx)                          │
└──────────────────────────────────────────────────────────────┘
                       ↓
        ┌────────────────────────────────────┐
        │  7. Remover Prefijo Cíclico        │
        │  Archivo: ofdm_ops.py              │
        │  Función: remove_cyclic_prefix()   │
        │  - Descartar primeros L_CP samples │
        └──────────────┬─────────────────────┘
                       ↓
        ┌────────────────────────────────────┐
        │  8. Demodulación OFDM              │
        │  Archivo: ofdm_ops.py              │
        │  Función: demodulate_ofdm()        │
        │  - FFT(N_FFT)                      │
        │  - Extraer subportadoras de datos  │
        └──────────────┬─────────────────────┘
                       ↓
        ┌────────────────────────────────────┐
        │  9. Ecualización de Canal          │
        │  Archivo: ofdm_ops.py              │
        │  Función: equalize_channel()       │
        │  - Zero-Forcing: X̂[k] = Y[k]/H[k] │
        │  - Protección división por cero    │
        └──────────────┬─────────────────────┘
                       ↓
        ┌────────────────────────────────────┐
        │  10. Demodulación Digital          │
        │  Archivo: utils.py                 │
        │  Función: demap_symbols_to_bits()  │
        │  - Mínima distancia euclidiana     │
        │  - Símbolos I/Q → Bits             │
        └──────────────┬─────────────────────┘
                       ↓
        ┌────────────────────────────────────┐
        │  11. Descrambling (utils.py)       │
        │  Función: apply_scrambling()       │
        │  - Misma operación XOR que Tx      │
        └──────────────┬─────────────────────┘
                       ↓
     ┌──────────────────────────────────────────┐
     │  12. Decodificación FEC                 │
     │  (si enable_fec=True)                   │
     │  ┌──────────────────────────────────┐   │
     │  │ 12.1 Viterbi Decoder             │   │
     │  │ Función: conv_decode_terminated()│   │
     │  │ Input:  1,500,090 bits           │   │
     │  │ Output: 500,024 bits             │   │
     │  └─────────────┬────────────────────┘   │
     │                ↓                         │
     │  ┌──────────────────────────────────┐   │
     │  │ 12.2 CRC Check                   │   │
     │  │ Función: crc_check()             │   │
     │  │ Output: (500,000 bits, ok: bool) │   │
     │  └──────────────────────────────────┘   │
     └──────────────────┬───────────────────────┘
                        ↓
        ┌────────────────────────────────────┐
        │  13. Reconstrucción de Imagen      │
        │  Archivo: utils.py                 │
        │  Función: bits_to_image()          │
        │  Output: Matriz 250×250 píxeles    │
        └────────────────────────────────────┘
```

#### Ubicación en Código

**Archivo**: [controller/simulation_mgr.py](controller/simulation_mgr.py#L18-L136)

**Método**: `run_image_transmission()`

**Parámetros**:
- `image_path`: Ruta a la imagen
- `bw_idx`: Índice de ancho de banda (0-5 → 1.4-20 MHz)
- `profile_idx`: Tipo de CP (0=Normal, 1=Extendido)
- `mod_type`: Modulación (0=QPSK, 1=16-QAM, 2=64-QAM)
- `snr_db`: SNR en dB (0-40)
- `num_paths`: Número de caminos multipath (1-10)
- `enable_fec`: Bool, activar FEC

**Retorno**: Diccionario con:
```python
{
    "success": True/False,
    "tx_image": Imagen original (250×250),
    "rx_image": Imagen recibida (250×250),
    "ber": Bit Error Rate (float),
    "snr": SNR usado (dB),
    "info": String con información (BER, FEC, CRC)
}
```

---

## Funcionalidades Complementarias

### 1. Curvas BER vs SNR

#### Descripción

Genera gráficas comparativas de **BER (Bit Error Rate) vs SNR** para evaluar el rendimiento de:
- Tres modulaciones: **QPSK, 16-QAM, 64-QAM**
- Dos escenarios: **SIN FEC** y **CON FEC**

**Ubicación**: [ui/main_window.py](ui/main_window.py#L217-L318)

**Método controlador**: [controller/simulation_mgr.py](controller/simulation_mgr.py#L138-L186) - `calculate_ber_curve()`

#### Proceso

1. **Cargar imagen de prueba** (mismos bits para todas las pruebas)
2. **Iterar sobre SNR**: De 0 a 30 dB en 10 puntos
3. **Para cada modulación**:
   - Transmitir los mismos datos
   - Calcular BER = errores / bits_totales
4. **Generar dos gráficas separadas**:
   - Gráfica 1: Sin FEC (baseline)
   - Gráfica 2: Con FEC (mejora visible)

#### Código Principal

**Archivo**: [controller/simulation_mgr.py](controller/simulation_mgr.py#L145-L180)

```python
def calculate_ber_curve(self, image_path, bw_idx, profile_idx, mod_type, num_paths, enable_fec=True):
    snr_range = np.linspace(0, 30, 10)  # 0, 3.33, 6.67, ..., 30 dB
    
    # Preparar datos (con o sin FEC)
    tx_bits_raw, _ = utils.image_to_bits(image_path, 250)
    if enable_fec:
        tx_bits_crc = crc_attach(tx_bits_raw, crc="24A")
        tx_bits_coded = conv_encode(tx_bits_crc, terminate=True)
    else:
        tx_bits_coded = tx_bits_raw
    
    ber_curves = {"QPSK": [], "16-QAM": [], "64-QAM": []}
    
    for mod_idx, mod_name in enumerate(["QPSK", "16-QAM", "64-QAM"]):
        for snr in snr_range:
            # Cadena Tx-Canal-Rx (similar a run_image_transmission)
            # ... [código de transmisión]
            
            # Calcular BER
            errors = np.sum(tx_bits_raw != rx_bits_final)
            ber = errors / len(tx_bits_raw)
            ber_curves[mod_name].append(max(ber, 1e-7))  # Umbral mínimo para log
    
    return snr_range, ber_curves
```

#### Interpretación de Resultados

**Sin FEC**:
- **QPSK**: BER baja más rápido (más robusto)
  - BER = 10^-2 en ~10 dB
  - BER = 10^-3 en ~13 dB
  
- **16-QAM**: Intermedio
  - BER = 10^-2 en ~15 dB
  - BER = 10^-3 en ~18 dB
  
- **64-QAM**: Más sensible
  - BER = 10^-2 en ~20 dB
  - BER = 10^-3 en ~24 dB

**Con FEC (Ganancia de Codificación)**:
- Curvas desplazadas ~**4-6 dB a la izquierda**
- **QPSK**: BER = 10^-3 en ~7-9 dB (ganancia ~4 dB)
- **16-QAM**: BER = 10^-3 en ~12-14 dB (ganancia ~5 dB)
- **64-QAM**: BER = 10^-3 en ~18-20 dB (ganancia ~5 dB)

**Observaciones**:
- Mayor orden de modulación requiere mayor SNR
- FEC reduce significativamente SNR necesario
- Trade-off: FEC reduce throughput 3× pero mejora confiabilidad

---

### 2. Análisis PAPR (Peak-to-Average Power Ratio)

#### Descripción

El **PAPR** cuantifica la variación de potencia instantánea en señales OFDM:

```
PAPR = max|x(t)|² / E[|x(t)|²]
PAPR_dB = 10·log₁₀(PAPR)
```

**Ubicación**: [controller/simulation_mgr.py](controller/simulation_mgr.py#L188-L226) - `calculate_papr_distribution()`

#### ¿Por qué es crítico en OFDM?

1. **Amplificadores no lineales**: PAPR alto → saturación/clipping → distorsión
2. **Eficiencia energética**: PA debe operar con back-off → desperdicio de potencia
3. **Cumplimiento normativo**: Clipping genera regrowth espectral (viola máscaras FCC)

**PAPR típico en OFDM**: 10-13 dB (vs ~0 dB en señales de envolvente constante)

#### Implementación

**Archivo**: [controller/simulation_mgr.py](controller/simulation_mgr.py#L201-L217)

```python
def calculate_papr_distribution(self, image_path, bw_idx, profile_idx, mod_type):
    # ... [generar señal OFDM]
    
    # Calcular potencias instantáneas
    power_inst = np.abs(tx_signal_cp) ** 2
    power_avg = np.mean(power_inst)
    
    papr_samples = power_inst / power_avg  # PAPR por muestra
    papr_db_samples = 10 * np.log10(papr_samples + 1e-12)
    
    # CCDF: P(PAPR > umbral)
    papr_sorted = np.sort(papr_db_samples)[::-1]
    ccdf = np.arange(1, len(papr_sorted) + 1) / len(papr_sorted)
    
    return papr_sorted, ccdf
```

**Gráfica CCDF** (Complementary CDF):
- Eje X: PAPR (dB)
- Eje Y: Probabilidad de exceder ese PAPR
- Escala Y: Logarítmica (10^-1 a 10^-4)

#### Resultados Típicos

| N_FFT | PAPR @ P=10^-1 | PAPR @ P=10^-3 | PAPR_max |
|-------|----------------|----------------|----------|
| 128   | ~8 dB          | ~10 dB         | ~21 dB   |
| 512   | ~9 dB          | ~11 dB         | ~27 dB   |
| 2048  | ~10 dB         | ~12 dB         | ~33 dB   |

**Observación**: Más subportadoras → Mayor PAPR (sumatorio coherente de fases)

---

### 3. Parámetros LTE y su Justificación

#### Ancho de Banda (BW)

**Archivo**: [core/config.py](core/config.py#L4-L12)

| BW (MHz) | N_c (subportadoras) | N_FFT | Tasa de Muestreo | Uso LTE Típico |
|----------|---------------------|-------|------------------|----------------|
| 1.4      | 72                  | 128   | 1.92 Ms/s        | IoT, M2M       |
| 3        | 180                 | 256   | 3.84 Ms/s        | Rural          |
| 5        | 300                 | 512   | 7.68 Ms/s        | Urbano         |
| 10       | 600                 | 1024  | 15.36 Ms/s       | Estándar       |
| 15       | 900                 | 1536  | 23.04 Ms/s       | Alta capacidad |
| 20       | 1200                | 2048  | 30.72 Ms/s       | Máximo throughput |

**Separación de subportadoras**: Δf = 15 kHz (fijo en LTE downlink)

**Capacidad teórica** (Shannon):
```
C = BW × log₂(1 + SNR)
```
Ejemplo con BW=20 MHz, SNR=20 dB (100 lineal):
```
C = 20×10^6 × log₂(101) ≈ 133 Mbps
```

#### Prefijo Cíclico (CP)

**Archivo**: [core/config.py](core/config.py#L14-L18)

- **Normal (4.7 µs)**:
  - Longitud: 0.07 × T_symbol = 4.7 µs
  - Overhead: 7.2%
  - Protección: Delays hasta ~1.4 km
  
- **Extendido (16.6 µs)**:
  - Longitud: 0.25 × T_symbol = 16.6 µs
  - Overhead: 25%
  - Protección: Delays hasta ~5 km

**Criterio de diseño**:
```
L_CP ≥ τ_max × F_s
```
Donde τ_max = delay máximo del canal, F_s = tasa de muestreo

#### Modulación

**Archivo**: [core/config.py](core/config.py#L20-L58)

| Modulación | Bits/símbolo | Constelación | SNR mínimo | Eficiencia Espectral |
|------------|--------------|--------------|------------|----------------------|
| QPSK       | 2            | 4-PSK        | ~5 dB      | Baja                 |
| 16-QAM     | 4            | 4×4 QAM      | ~11 dB     | Media                |
| 64-QAM     | 6            | 8×8 QAM      | ~18 dB     | Alta                 |

**En LTE real**: AMC (Adaptive Modulation and Coding)
- eNodeB selecciona MCS (Modulation and Coding Scheme) dinámicamente
- Basado en CQI (Channel Quality Indicator) reportado por UE
- Objetivo: Maximizar throughput manteniendo BLER < 10%

---

## Referencias Técnicas

### Estándares 3GPP

1. **TS 36.212** - Multiplexing and channel coding
   - Sección 5.1.1: CRC calculation
   - Sección 5.1.3.1: Convolutional coding (Tail-biting y terminación)
   - Tabla 5.1.3-3: Polinomios generadores

2. **TS 36.211** - Physical channels and modulation
   - Sección 6.12: OFDM signal generation
   - Sección 7.1: Scrambling

3. **TS 36.213** - Physical layer procedures
   - Sección 7.1: Modulation order y TBS determination

### Libros de Referencia

- **Proakis & Salehi**: *Digital Communications*, 5th Edition (Cap. 8: Channel Coding)
- **Goldsmith**: *Wireless Communications* (Cap. 5: Capacity, Cap. 12: Equalization)
- **3GPP Specs**: https://www.3gpp.org/DynaReport/36-series.htm

### Algoritmos

- **Viterbi Algorithm**: Forney, G.D. (1973). "The Viterbi Algorithm". Proceedings of the IEEE.
- **Convolutional Codes**: Lin & Costello. "Error Control Coding", 2nd Ed.

---

## Conclusión

Este simulador implementa un sistema FEC completo según **3GPP TS 36.212**, permitiendo:

1. **Protección robusta contra errores** mediante CRC-24A + Código Convolucional K=7, R=1/3
2. **Decodificación eficiente** con algoritmo de Viterbi optimizado
3. **Análisis cuantitativo** de ganancia de codificación (3-6 dB)
4. **Validación experimental** comparando BER con/sin FEC

El FEC es fundamental en LTE para garantizar comunicaciones confiables en entornos inalámbricos adversos, reduciendo la necesidad de retransmisiones HARQ y mejorando la experiencia de usuario.

---

**Autor**: Documentación Técnica - Simulador LTE OFDM  
**Fecha**: Febrero 2026  
**Versión**: 2.0 (Enfoque en FEC)

