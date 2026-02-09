import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from PIL import Image

# Importamos el Controlador
from controller.simulation_mgr import OFDMSimulationManager

# Configuración inicial de apariencia
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        # 1. Configuración de la Ventana Principal
        self.title("Simulador LTE OFDM")
        self.geometry("1100x750") # Un poco más alto para el nuevo botón

        # Inicializar el "Gerente"
        self.manager = OFDMSimulationManager()
        
        # Variable para almacenar la ruta de la imagen seleccionada
        self.selected_image_path = None
        
        # Mapeos
        self.bw_map = {"1.4 MHz": 1, "3 MHz": 2, "5 MHz": 3, "10 MHz": 4, "15 MHz": 5, "20 MHz": 6}
        self.cp_map = {"Normal (4.7µs)": 1, "Extendido (16.6µs)": 2}
        self.mod_map = {"QPSK": 1, "16-QAM": 2, "64-QAM": 3}

        # FEC (TS 36.212)
        self.var_fec = ctk.BooleanVar(value=True)

        # 2. Construcción de la Interfaz
        self.setup_ui()

    def setup_ui(self):
        """Disposición de elementos visuales (Grid Layout)"""
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- PANEL LATERAL (CONTROLES) ---
        self.sidebar_frame = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(20, weight=1) # Espaciador al final

        # Título
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="LTE SIMULATOR", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Grupo 1: Física
        self.lbl_phys = ctk.CTkLabel(self.sidebar_frame, text="Parámetros Físicos:", anchor="w")
        self.lbl_phys.grid(row=1, column=0, padx=20, pady=(10, 0))
        
        self.option_bw = ctk.CTkOptionMenu(self.sidebar_frame, values=list(self.bw_map.keys()))
        self.option_bw.grid(row=2, column=0, padx=20, pady=5)
        self.option_bw.set("10 MHz")

        self.option_cp = ctk.CTkOptionMenu(self.sidebar_frame, values=list(self.cp_map.keys()))
        self.option_cp.grid(row=3, column=0, padx=20, pady=5)
        self.option_cp.set("Normal (4.7µs)")

        # Grupo 2: Enlace y Canal
        self.lbl_link = ctk.CTkLabel(self.sidebar_frame, text="Enlace y Canal:", anchor="w")
        self.lbl_link.grid(row=4, column=0, padx=20, pady=(20, 0))

        self.option_mod = ctk.CTkOptionMenu(self.sidebar_frame, values=list(self.mod_map.keys()))
        self.option_mod.grid(row=5, column=0, padx=20, pady=5)
        self.option_mod.set("16-QAM")

        # --- FEC Switch (TS 36.212) ---
        self.switch_fec = ctk.CTkSwitch(
            self.sidebar_frame,
            text="FEC (TS 36.212)",
            variable=self.var_fec,
            onvalue=True,
            offvalue=False,
        )
        self.switch_fec.grid(row=6, column=0, padx=20, pady=(10, 0), sticky="w")

        self.lbl_snr = ctk.CTkLabel(self.sidebar_frame, text="SNR: 15 dB")
        self.lbl_snr.grid(row=7, column=0, padx=20, pady=(10,0))
        self.slider_snr = ctk.CTkSlider(self.sidebar_frame, from_=0, to=40, number_of_steps=40, command=self.update_snr_label)
        self.slider_snr.grid(row=8, column=0, padx=20, pady=5)
        self.slider_snr.set(15)

        self.lbl_paths = ctk.CTkLabel(self.sidebar_frame, text="Caminos (Multipath): 1")
        self.lbl_paths.grid(row=9, column=0, padx=20, pady=(10,0))
        self.slider_paths = ctk.CTkSlider(self.sidebar_frame, from_=1, to=10, number_of_steps=9, command=self.update_paths_label)
        self.slider_paths.grid(row=10, column=0, padx=20, pady=5)
        self.slider_paths.set(1)

        # Grupo 3: Selección de Archivo (NUEVO)
        self.lbl_source = ctk.CTkLabel(self.sidebar_frame, text="Fuente de Datos:", anchor="w")
        self.lbl_source.grid(row=11, column=0, padx=20, pady=(20, 0))

        self.btn_select_file = ctk.CTkButton(self.sidebar_frame, text="Seleccionar Imagen...", 
                                             fg_color="#4B4B4B", hover_color="#5B5B5B", 
                                             command=self.select_file)
        self.btn_select_file.grid(row=12, column=0, padx=20, pady=5)

        self.lbl_filename = ctk.CTkLabel(self.sidebar_frame, text="[Ningún archivo]", font=("Arial", 11), text_color="gray")
        self.lbl_filename.grid(row=13, column=0, padx=20, pady=0)

        # Grupo 4: Botones de Acción
        self.btn_run_img = ctk.CTkButton(self.sidebar_frame, text="TRANSMITIR IMAGEN", 
                                         fg_color="#1f538d", hover_color="#14375e", # Azul profesional
                                         command=self.action_run_image)
        self.btn_run_img.grid(row=14, column=0, padx=20, pady=(20, 10))

        self.btn_run_ber = ctk.CTkButton(self.sidebar_frame, text="GENERAR CURVA BER", 
                                         fg_color="transparent", border_width=2, 
                                         command=self.action_plot_ber)
        self.btn_run_ber.grid(row=15, column=0, padx=20, pady=10)

        self.btn_run_papr = ctk.CTkButton(self.sidebar_frame, text="ANALIZAR PAPR", 
                                          fg_color="transparent", border_width=2, 
                                          command=self.action_plot_papr)
        self.btn_run_papr.grid(row=16, column=0, padx=20, pady=10)


        # --- PANEL CENTRAL (VISUALIZACIÓN) ---
        self.tabview = ctk.CTkTabview(self, width=800)
        self.tabview.grid(row=0, column=1, padx=(20, 20), pady=(20, 20), sticky="nsew")
        
        self.tab_img = self.tabview.add("Visualización Imagen")
        self.tab_ber = self.tabview.add("Análisis BER")
        self.tab_papr = self.tabview.add("Análisis PAPR")

        # Configuración Tab Imagen
        self.tab_img.grid_columnconfigure(0, weight=1)
        self.tab_img.grid_columnconfigure(1, weight=1)
        
        self.lbl_tx_title = ctk.CTkLabel(self.tab_img, text="Imagen Transmitida", font=("Arial", 16, "bold"))
        self.lbl_tx_title.grid(row=0, column=0, pady=10)
        self.lbl_tx_img = ctk.CTkLabel(self.tab_img, text="\n\n[Seleccione una imagen\npara comenzar]", font=("Arial", 14), text_color="gray")
        self.lbl_tx_img.grid(row=1, column=0)

        self.lbl_rx_title = ctk.CTkLabel(self.tab_img, text="Imagen Recibida", font=("Arial", 16, "bold"))
        self.lbl_rx_title.grid(row=0, column=1, pady=10)
        self.lbl_rx_img = ctk.CTkLabel(self.tab_img, text="\n\n[Esperando simulación...]", font=("Arial", 14), text_color="gray")
        self.lbl_rx_img.grid(row=1, column=1)

        self.lbl_status = ctk.CTkLabel(self.tab_img, text="Estado: Esperando configuración", font=("Courier", 14), text_color="yellow")
        self.lbl_status.grid(row=2, column=0, columnspan=2, pady=20)


    # --- EVENTOS Y LÓGICA DE INTERFAZ ---

    def update_snr_label(self, value):
        self.lbl_snr.configure(text=f"SNR: {int(value)} dB")

    def update_paths_label(self, value):
        self.lbl_paths.configure(text=f"Caminos (Multipath): {int(value)}")

    def select_file(self):
        """Abre cuadro de diálogo para seleccionar imagen"""
        file_path = filedialog.askopenfilename(
            title="Seleccionar Imagen",
            filetypes=[("Archivos de Imagen", "*.jpg *.jpeg *.png *.bmp")]
        )
        
        if file_path:
            self.selected_image_path = file_path
            # Mostrar solo el nombre del archivo para no saturar la UI
            filename = os.path.basename(file_path)
            if len(filename) > 25:
                filename = filename[:22] + "..."
            self.lbl_filename.configure(text=filename, text_color="#30D760") # Verde si hay archivo
            self.lbl_status.configure(text="Imagen cargada. Lista para transmitir.", text_color="white")

    def action_run_image(self):
        """Ejecuta la simulación de imagen"""
        # 0. Validación de entrada
        if not self.selected_image_path:
            messagebox.showwarning("Falta Imagen", "Por favor selecciona una imagen primero usando el botón 'Seleccionar Imagen'.")
            return

        # 1. Recolectar Inputs
        bw_idx = self.bw_map[self.option_bw.get()]
        prof_idx = self.cp_map[self.option_cp.get()]
        mod_idx = self.mod_map[self.option_mod.get()]
        snr = int(self.slider_snr.get())
        paths = int(self.slider_paths.get())
        
        self.lbl_status.configure(text="Procesando OFDM... Espere.")
        self.update() # Forzar refresco de UI

        # 2. Llamar al Controlador
        enable_fec = bool(self.var_fec.get())
        result = self.manager.run_image_transmission(self.selected_image_path, bw_idx, prof_idx, mod_idx, snr, paths, enable_fec=enable_fec)

        # 3. Mostrar Resultados
        if result["success"]:
            # Convertir Matrices Numpy a Imágenes CTk
            img_tx_pil = Image.fromarray(result["tx_image"]).resize((300, 300), Image.Resampling.NEAREST)
            img_rx_pil = Image.fromarray(result["rx_image"]).resize((300, 300), Image.Resampling.NEAREST)

            tk_img_tx = ctk.CTkImage(light_image=img_tx_pil, dark_image=img_tx_pil, size=(300, 300))
            tk_img_rx = ctk.CTkImage(light_image=img_rx_pil, dark_image=img_rx_pil, size=(300, 300))

            self.lbl_tx_img.configure(image=tk_img_tx, text="")
            self.lbl_rx_img.configure(image=tk_img_rx, text="")
            self.lbl_status.configure(text=result["info"], text_color="#30D760") # Verde SPTF
            self.tabview.set("Visualización Imagen") # Cambiar foco a la pestaña relevante
        else:
            self.lbl_status.configure(text=f"Error: {result.get('error')}", text_color="red")
            messagebox.showerror("Error de Simulación", f"Ocurrió un error al procesar la imagen:\n{result.get('error')}")

    def action_plot_ber(self):
        """Genera y muestra gráficas BER para diferentes modulaciones sin y con FEC"""
        # Validación de seguridad
        if not self.selected_image_path:
            messagebox.showwarning("Falta Imagen", "Selecciona una imagen para analizar su BER.")
            return

        bw_idx = self.bw_map[self.option_bw.get()]
        prof_idx = self.cp_map[self.option_cp.get()]
        paths = int(self.slider_paths.get())

        self.lbl_status.configure(text="Calculando BER para múltiples modulaciones... (Espere)")
        self.update()

        try:
            # Limpiar la pestaña anterior
            for widget in self.tab_ber.winfo_children():
                widget.destroy()

            # Crear un Frame con scrolling
            self.tab_ber.grid_columnconfigure(0, weight=1)
            self.tab_ber.grid_rowconfigure(0, weight=1)

            # Canvas con scrollbar
            canvas = ctk.CTkCanvas(self.tab_ber, bg="#2b2b2b", highlightthickness=0)
            scrollbar = ctk.CTkScrollbar(self.tab_ber, orientation="vertical", command=canvas.yview)
            scrollable_frame = ctk.CTkFrame(canvas, fg_color="#2b2b2b")

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            # Bind mouse wheel para scrolling
            def _on_mousewheel(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

            canvas.grid(row=0, column=0, sticky="nsew")
            scrollbar.grid(row=0, column=1, sticky="ns")

            # --- PRIMERA GRÁFICA: SIN FEC ---
            snr_axis, ber_curves_no_fec = self.manager.calculate_ber_curve(
                self.selected_image_path, bw_idx, prof_idx, 2, paths, enable_fec=False
            )

            fig_no_fec = Figure(figsize=(10, 6), dpi=100)
            fig_no_fec.patch.set_facecolor('#2b2b2b')
            ax_no_fec = fig_no_fec.add_subplot(111)
            ax_no_fec.set_facecolor('#2b2b2b')

            # Colores para cada modulación
            colors = {'QPSK': '#00FF00', '16-QAM': '#FF6B6B', '64-QAM': '#4169FF'}
            
            for mod_name, ber_values in ber_curves_no_fec.items():
                ax_no_fec.plot(snr_axis, ber_values, marker='o', linewidth=2, 
                              label=mod_name, color=colors[mod_name])

            ax_no_fec.set_title("BER vs SNR (SIN FEC)", color='white', fontsize=14, fontweight='bold')
            ax_no_fec.set_xlabel("SNR (dB)", color='white', fontsize=12)
            ax_no_fec.set_ylabel("Bit Error Rate (BER)", color='white', fontsize=12)
            ax_no_fec.tick_params(axis='x', colors='white')
            ax_no_fec.tick_params(axis='y', colors='white')
            ax_no_fec.grid(True, color='#444444', linestyle='--', alpha=0.5)
            ax_no_fec.set_yscale('log')
            ax_no_fec.legend(loc='best', facecolor='#3b3b3b', edgecolor='white', labelcolor='white')
            
            # Limitar los ejes Y para mejor visualización
            try:
                min_val = min([min(v) for v in ber_curves_no_fec.values() if any(v > 0 for v in v)])
                ax_no_fec.set_ylim(bottom=min_val*0.1, top=1.1)
            except:
                pass

            # Canvas para la primera gráfica
            frame_no_fec = ctk.CTkFrame(scrollable_frame, fg_color="#2b2b2b")
            frame_no_fec.pack(fill="both", expand=True, padx=10, pady=10)
            
            canvas_no_fec = FigureCanvasTkAgg(fig_no_fec, master=frame_no_fec)
            canvas_no_fec.draw()
            canvas_no_fec.get_tk_widget().pack(fill="both", expand=True)

            # --- SEGUNDA GRÁFICA: CON FEC ---
            snr_axis_fec, ber_curves_con_fec = self.manager.calculate_ber_curve(
                self.selected_image_path, bw_idx, prof_idx, 2, paths, enable_fec=True
            )

            fig_con_fec = Figure(figsize=(10, 6), dpi=100)
            fig_con_fec.patch.set_facecolor('#2b2b2b')
            ax_con_fec = fig_con_fec.add_subplot(111)
            ax_con_fec.set_facecolor('#2b2b2b')

            for mod_name, ber_values in ber_curves_con_fec.items():
                ax_con_fec.plot(snr_axis_fec, ber_values, marker='s', linewidth=2, 
                               label=mod_name, color=colors[mod_name])

            ax_con_fec.set_title("BER vs SNR (CON FEC - TS 36.212)", color='white', fontsize=14, fontweight='bold')
            ax_con_fec.set_xlabel("SNR (dB)", color='white', fontsize=12)
            ax_con_fec.set_ylabel("Bit Error Rate (BER)", color='white', fontsize=12)
            ax_con_fec.tick_params(axis='x', colors='white')
            ax_con_fec.tick_params(axis='y', colors='white')
            ax_con_fec.grid(True, color='#444444', linestyle='--', alpha=0.5)
            ax_con_fec.set_yscale('log')
            ax_con_fec.legend(loc='best', facecolor='#3b3b3b', edgecolor='white', labelcolor='white')
            
            # Limitar los ejes Y para mejor visualización
            try:
                min_val = min([min(v) for v in ber_curves_con_fec.values() if any(v > 0 for v in v)])
                ax_con_fec.set_ylim(bottom=min_val*0.1, top=1.1)
            except:
                pass

            # Canvas para la segunda gráfica
            frame_con_fec = ctk.CTkFrame(scrollable_frame, fg_color="#2b2b2b")
            frame_con_fec.pack(fill="both", expand=True, padx=10, pady=10)
            
            canvas_con_fec = FigureCanvasTkAgg(fig_con_fec, master=frame_con_fec)
            canvas_con_fec.draw()
            canvas_con_fec.get_tk_widget().pack(fill="both", expand=True)

            self.lbl_status.configure(text="Gráficas BER generadas exitosamente.")
            self.tabview.set("Análisis BER")
            
        except Exception as e:
            self.lbl_status.configure(text="Error en cálculo BER")
            messagebox.showerror("Error", str(e))

    def action_plot_papr(self):
        """Genera y muestra gráfica PAPR con la IMAGEN"""
        if not self.selected_image_path:
            messagebox.showwarning("Falta Imagen", "Selecciona una imagen para analizar su PAPR.")
            return

        bw_idx = self.bw_map[self.option_bw.get()]
        prof_idx = self.cp_map[self.option_cp.get()]
        mod_idx = self.mod_map[self.option_mod.get()]

        self.lbl_status.configure(text="Calculando PAPR de la imagen...")
        self.update()
        
        try:
            # --- CAMBIO: Pasamos self.selected_image_path ---
            enable_fec = bool(self.var_fec.get())
            thresholds, ccdf = self.manager.calculate_papr_distribution(
                self.selected_image_path, bw_idx, prof_idx, mod_idx, enable_fec=enable_fec
            )

            self.embed_plot(self.tab_papr, thresholds, ccdf, 
                           "CCDF de PAPR (Datos de Imagen)", "Umbral de Potencia (dB)", "Probabilidad (PAPR > Umbral)", log_y=True)
            self.lbl_status.configure(text="Gráfica PAPR generada.")
            self.tabview.set("Análisis PAPR")
            
        except Exception as e:
             self.lbl_status.configure(text="Error en cálculo PAPR")
             messagebox.showerror("Error", str(e))

    def embed_plot(self, parent_frame, x_data, y_data, title, xlabel, ylabel, log_y=False):
        """Función auxiliar para incrustar gráficos Matplotlib en CustomTkinter"""
        # Limpiar gráfico anterior si existe
        for widget in parent_frame.winfo_children():
            widget.destroy()

        # Crear Figura
        fig = Figure(figsize=(6, 4), dpi=100)
        # Fondo oscuro para coincidir con la app
        fig.patch.set_facecolor('#2b2b2b') 
        
        ax = fig.add_subplot(111)
        ax.set_facecolor('#2b2b2b')
        ax.plot(x_data, y_data, marker='o', color='#30D760', linewidth=2) # Verde SPTF
        
        ax.set_title(title, color='white', fontsize=12)
        ax.set_xlabel(xlabel, color='white')
        ax.set_ylabel(ylabel, color='white')
        ax.tick_params(axis='x', colors='white')
        ax.tick_params(axis='y', colors='white')
        ax.grid(True, color='#444444', linestyle='--')

        if log_y:
            ax.set_yscale('log')
            # Ajuste dinámico de límites para que se vea bien
            try:
                min_val = min(filter(lambda x: x > 0, y_data)) if any(y > 0 for y in y_data) else 1e-5
                ax.set_ylim(bottom=min_val*0.1, top=1.1)
            except:
                pass

        # Canvas de Tkinter
        canvas = FigureCanvasTkAgg(fig, master=parent_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)