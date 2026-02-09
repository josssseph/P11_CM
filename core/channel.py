import numpy as np

def apply_awgn(signal, snr_db, return_noise_power=False):
    """Añade ruido blanco gaussiano.

    Si `return_noise_power=True`, también devuelve `noise_power`, que en este proyecto
    corresponde a la varianza compleja E{|n|^2} del AWGN generado.
    """
    # Potencia de la señal
    sig_power = np.mean(np.abs(signal) ** 2)
    # Potencia del ruido requerida
    noise_power = sig_power / (10 ** (snr_db / 10))
    # Generar ruido complejo (varianza por dimensión = noise_power/2)
    noise = np.sqrt(noise_power / 2) * (
        np.random.randn(len(signal)) + 1j * np.random.randn(len(signal))
    )
    out = signal + noise
    if return_noise_power:
        return out, noise_power
    return out

def apply_rayleigh(signal, snr_db, num_taps=1, return_noise_power=False):
    """
    Simula canal multipath y añade ruido.
    Retorna: Señal_Afectada, h (Respuesta al Impulso)
    """
    # 1. Definir respuesta al impulso (h)
    # Modelo exponencial decreciente simple o taps aleatorios
    if num_taps == 1:
        h = np.array([1.0 + 0j]) # Canal plano (solo AWGN básicamente)
    else:
        # Ejemplo fijo
        base_h = np.array([1.0, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.5, 0.5])
        if num_taps <= len(base_h):
            h = base_h[:num_taps]
        else:
            h = np.pad(base_h, (0, num_taps - len(base_h)))
        
        # Normalizar energía del canal a 1 para no amplificar/atenuar ganancia pura
        h = h / np.sqrt(np.sum(np.abs(h)**2))

    # 2. Convolución (Efecto físico del canal)
    # 'same' mantiene la longitud, 'full' añade cola. 
    # En OFDM real es convolución circular gracias al CP. 
    # Usamos 'full' y dejamos que el CP maneje la interferencia.
    signal_convolved = np.convolve(signal, h, mode='full')
    
    # Recortar al tamaño original para simplificar recepción 
    # (asumiendo sincronización perfecta)
    signal_convolved = signal_convolved[:len(signal)]

    # 3. Añadir ruido AWGN
    if return_noise_power:
        signal_noisy, noise_power = apply_awgn(signal_convolved, snr_db, return_noise_power=True)
        return signal_noisy, h, noise_power

    signal_noisy = apply_awgn(signal_convolved, snr_db)
    return signal_noisy, h









'''
def apply_rayleigh(signal, snr_db, num_taps=1):
    """
    Simula canal multipath SISO (1 Tx -> 1 Rx).
    """
    if num_taps == 1:
        h = np.array([1.0 + 0j]) 
    else:
        # Generación Aleatoria (Rayleigh) ---
        h_random = (np.random.randn(num_taps) + 1j*np.random.randn(num_taps))

        decay_factor = np.exp(-0.5 * np.arange(num_taps))
        h = h_random * decay_factor
        
        # Normalizar energía del canal a 1
        h = h / np.sqrt(np.sum(np.abs(h)**2))

    # Convolución
    signal_convolved = np.convolve(signal, h, mode='full')
    signal_convolved = signal_convolved[:len(signal)]

    # Añadir ruido AWGN
    signal_noisy = apply_awgn(signal_convolved, snr_db)
    
    return signal_noisy, h

'''