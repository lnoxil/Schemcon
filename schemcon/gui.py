from __future__ import annotations

import json
import pathlib
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .convert import convert_schematic
from .matcher import pick_best_match
from .registry import (
    extract_reports,
    fetch_version_json,
    fetch_version_manifest,
    load_registry,
    download_server_jar,
    resolve_version_info,
)


class SchemconApp(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master)
        self.master = master
        self._build_style()
        self._build_layout()

    def _build_style(self) -> None:
        style = ttk.Style()
        theme = "clam" if "clam" in style.theme_names() else style.theme_use()
        style.theme_use(theme)
        style.configure("Header.TLabel", font=("Helvetica", 13, "bold"))
        style.configure("Section.TLabelframe", padding=(12, 8))
        style.configure("Primary.TButton", font=("Helvetica", 10, "bold"))

    def _build_layout(self) -> None:
        self.pack(fill=tk.BOTH, expand=True)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        container = ttk.Frame(self)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)

        header = ttk.Label(container, text="Schemcon GUI", style="Header.TLabel")
        header.grid(row=0, column=0, sticky="w", padx=16, pady=(12, 6))

        sections = ttk.Frame(container)
        sections.grid(row=1, column=0, sticky="nsew", padx=12)
        sections.columnconfigure(0, weight=1)

        self._build_fetch_section(sections)
        self._build_mapping_section(sections)
        self._build_convert_section(sections)

        self.log = tk.Text(container, height=10, wrap="word", state="disabled")
        self.log.grid(row=2, column=0, sticky="nsew", padx=16, pady=(12, 16))
        container.rowconfigure(2, weight=1)

    def _build_fetch_section(self, parent: ttk.Frame) -> None:
        frame = ttk.Labelframe(parent, text="1. Скачать реестры", style="Section.TLabelframe")
        frame.grid(row=0, column=0, sticky="ew", pady=6)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Версия").grid(row=0, column=0, sticky="w")
        self.version_var = tk.StringVar(value="1.21")
        ttk.Entry(frame, textvariable=self.version_var).grid(row=0, column=1, sticky="ew", padx=6)

        ttk.Label(frame, text="Папка для данных").grid(row=1, column=0, sticky="w")
        self.registry_out_var = tk.StringVar(value="data/versions")
        ttk.Entry(frame, textvariable=self.registry_out_var).grid(row=1, column=1, sticky="ew", padx=6)
        ttk.Button(frame, text="Выбрать", command=self._choose_registry_out).grid(row=1, column=2, padx=6)

        ttk.Button(frame, text="Скачать", style="Primary.TButton", command=self._run_fetch).grid(
            row=2, column=0, columnspan=3, pady=8, sticky="ew"
        )

    def _build_mapping_section(self, parent: ttk.Frame) -> None:
        frame = ttk.Labelframe(parent, text="2. Построить mapping", style="Section.TLabelframe")
        frame.grid(row=1, column=0, sticky="ew", pady=6)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Источник (директория с blocks.json)").grid(row=0, column=0, sticky="w")
        self.source_dir_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.source_dir_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(frame, text="Выбрать", command=self._choose_source_dir).grid(row=0, column=2, padx=6)

        ttk.Label(frame, text="Цель (директория с blocks.json)").grid(row=1, column=0, sticky="w")
        self.target_dir_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.target_dir_var).grid(row=1, column=1, sticky="ew", padx=6)
        ttk.Button(frame, text="Выбрать", command=self._choose_target_dir).grid(row=1, column=2, padx=6)

        ttk.Label(frame, text="Файл mapping").grid(row=2, column=0, sticky="w")
        self.mapping_out_var = tk.StringVar(value="data/mappings/mapping.json")
        ttk.Entry(frame, textvariable=self.mapping_out_var).grid(row=2, column=1, sticky="ew", padx=6)
        ttk.Button(frame, text="Выбрать", command=self._choose_mapping_out).grid(row=2, column=2, padx=6)

        ttk.Button(frame, text="Построить", style="Primary.TButton", command=self._run_mapping).grid(
            row=3, column=0, columnspan=3, pady=8, sticky="ew"
        )

    def _build_convert_section(self, parent: ttk.Frame) -> None:
        frame = ttk.Labelframe(parent, text="3. Конвертировать схему", style="Section.TLabelframe")
        frame.grid(row=2, column=0, sticky="ew", pady=6)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Входной файл .schem").grid(row=0, column=0, sticky="w")
        self.input_schem_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.input_schem_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(frame, text="Выбрать", command=self._choose_input_schem).grid(row=0, column=2, padx=6)

        ttk.Label(frame, text="Выходной файл .schem").grid(row=1, column=0, sticky="w")
        self.output_schem_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.output_schem_var).grid(row=1, column=1, sticky="ew", padx=6)
        ttk.Button(frame, text="Выбрать", command=self._choose_output_schem).grid(row=1, column=2, padx=6)

        ttk.Label(frame, text="Файл mapping").grid(row=2, column=0, sticky="w")
        self.mapping_in_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.mapping_in_var).grid(row=2, column=1, sticky="ew", padx=6)
        ttk.Button(frame, text="Выбрать", command=self._choose_mapping_in).grid(row=2, column=2, padx=6)

        ttk.Label(frame, text="Отчет JSON").grid(row=3, column=0, sticky="w")
        self.report_out_var = tk.StringVar(value="conversion_report.json")
        ttk.Entry(frame, textvariable=self.report_out_var).grid(row=3, column=1, sticky="ew", padx=6)
        ttk.Button(frame, text="Выбрать", command=self._choose_report_out).grid(row=3, column=2, padx=6)

        ttk.Button(frame, text="Конвертировать", style="Primary.TButton", command=self._run_convert).grid(
            row=4, column=0, columnspan=3, pady=8, sticky="ew"
        )

    def _choose_registry_out(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.registry_out_var.set(path)

    def _choose_source_dir(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.source_dir_var.set(path)

    def _choose_target_dir(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.target_dir_var.set(path)

    def _choose_mapping_out(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            self.mapping_out_var.set(path)

    def _choose_input_schem(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Schematic", "*.schem")])
        if path:
            self.input_schem_var.set(path)

    def _choose_output_schem(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".schem", filetypes=[("Schematic", "*.schem")])
        if path:
            self.output_schem_var.set(path)

    def _choose_mapping_in(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if path:
            self.mapping_in_var.set(path)

    def _choose_report_out(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            self.report_out_var.set(path)

    def _run_fetch(self) -> None:
        self._run_in_thread(self._fetch_registry)

    def _run_mapping(self) -> None:
        self._run_in_thread(self._build_mapping)

    def _run_convert(self) -> None:
        self._run_in_thread(self._convert_schematic)

    def _run_in_thread(self, func: callable) -> None:
        thread = threading.Thread(target=self._safe_execute, args=(func,), daemon=True)
        thread.start()

    def _safe_execute(self, func: callable) -> None:
        try:
            func()
        except Exception as exc:  # noqa: BLE001 - UI feedback
            self._log(f"Ошибка: {exc}")
            messagebox.showerror("Ошибка", str(exc))

    def _log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert(tk.END, message + "\n")
        self.log.configure(state="disabled")
        self.log.see(tk.END)

    def _fetch_registry(self) -> None:
        version = self.version_var.get().strip()
        output_dir = pathlib.Path(self.registry_out_var.get().strip())
        if not version:
            raise ValueError("Укажите версию.")
        manifest = fetch_version_manifest()
        info = resolve_version_info(version, manifest)
        version_json = fetch_version_json(info)
        output_dir.mkdir(parents=True, exist_ok=True)
        server_jar = output_dir / f"{version}.jar"
        download_server_jar(version_json, server_jar)
        extract_reports(server_jar, output_dir / version)
        self._log(f"Реестры версии {version} сохранены в {output_dir / version}.")

    def _build_mapping(self) -> None:
        source_dir = pathlib.Path(self.source_dir_var.get().strip())
        target_dir = pathlib.Path(self.target_dir_var.get().strip())
        output_path = pathlib.Path(self.mapping_out_var.get().strip())
        if not source_dir.exists() or not target_dir.exists():
            raise FileNotFoundError("Укажите существующие директории с blocks.json.")
        source_registry = load_registry(source_dir)
        target_registry = load_registry(target_dir)
        target_blocks = set(target_registry.keys())
        mapping = {}
        for block in sorted(source_registry.keys()):
            result = pick_best_match(block, target_blocks)
            mapping[block] = {"target": result.target, "reason": result.reason}
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
        self._log(f"Mapping сохранен: {output_path}")

    def _convert_schematic(self) -> None:
        input_path = self.input_schem_var.get().strip()
        output_path = self.output_schem_var.get().strip()
        mapping_path = self.mapping_in_var.get().strip()
        report_path = pathlib.Path(self.report_out_var.get().strip())
        if not input_path or not output_path or not mapping_path:
            raise ValueError("Укажите входной файл, выходной файл и mapping.")
        mapping_data = json.loads(pathlib.Path(mapping_path).read_text(encoding="utf-8"))
        flat_mapping = {
            key: value["target"] if isinstance(value, dict) else value for key, value in mapping_data.items()
        }
        report = convert_schematic(input_path, output_path, flat_mapping)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        self._log(f"Конвертация завершена: {output_path}")
        self._log(f"Отчет сохранен: {report_path}")


def launch_gui() -> None:
    root = tk.Tk()
    root.title("Schemcon")
    root.geometry("880x720")
    SchemconApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
