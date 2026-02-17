from __future__ import annotations

import json
import pathlib
import re
import shutil
import zipfile
from typing import Any
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .categories import categorize_block
from .convert import convert_schematic
from .gradient import (
    build_gradient_map,
    list_local_versions,
    load_gradient_map,
    refresh_gradient_maps_for_local_versions,
    save_gradient_map,
)
from .matcher import pick_best_match
from .registry import (
    download_client_jar,
    download_server_jar,
    ensure_registry_reports,
    fetch_version_json,
    fetch_version_manifest,
    load_registry,
    resolve_version_info,
)
from .schem import export_fawe_compatible, load_schematic, save_schematic


class SchemconApp(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master)
        self.configure(padding=8)
        self.pack(fill=tk.BOTH, expand=True)

        self._mapping_rows: list[dict[str, str]] = []
        self._version_root = pathlib.Path("data/versions")
        self._current_source_version = ""
        self._current_target_version = ""
        self._current_target_blocks: set[str] = set()
        self._pending_mapping: dict[str, dict[str, str]] = {}
        self._pending_output_schem = ""
        self._pending_input_schem = ""
        self._current_gradient_map: dict[str, tuple[int, int, int]] = {}
        self._stairs_to_block_fallback_var = tk.BooleanVar(value=True)
        self.format_input_var = tk.StringVar()
        self.format_output_var = tk.StringVar(value="converted_output.schematic")
        self.format_kind_var = tk.StringVar(value="old_schematic_v2")

        self._jar_member_index: dict[str, set[str]] = {}
        self._photo_refs: dict[str, tk.PhotoImage] = {}
        self._block_icon_cache: dict[str, tk.PhotoImage] = {}
        self._pair_icon_cache: dict[str, tk.PhotoImage] = {}
        self._group_children: dict[str, list[dict[str, str]]] = {}
        self._multi_target_versions: set[str] = set()

        self._build_style()
        self._build_layout()
        self._refresh_version_choices()
        self._preload_local_gradient_maps()

    def _preload_local_gradient_maps(self) -> None:
        try:
            stats = refresh_gradient_maps_for_local_versions(
                self._version_root,
                pathlib.Path("data/gradients"),
            )
            if stats:
                self._log(
                    "Авто-инициализация градиент-карт: "
                    + ", ".join(f"{ver}={count}" for ver, count in sorted(stats.items()))
                )
        except Exception as exc:  # noqa: BLE001
            self._log(f"Авто-инициализация градиентов пропущена: {exc}")

    def _build_style(self) -> None:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

        bg = "#f4f6fb"
        panel_bg = "#ffffff"
        accent = "#2f6fed"
        accent_hover = "#2458bd"

        style.configure("TFrame", background=bg)
        style.configure("TLabelframe", background=panel_bg, borderwidth=1, relief="solid")
        style.configure("TLabelframe.Label", background=panel_bg)
        style.configure("TLabel", background=bg)
        style.configure("Panel.TLabelframe", background=panel_bg, borderwidth=1, relief="solid")
        style.configure("Panel.TLabelframe.Label", background=panel_bg, font=("Segoe UI", 10, "bold"))

        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure(
            "Primary.TButton",
            font=("Segoe UI", 10, "bold"),
            foreground="white",
            background=accent,
            padding=(10, 6),
            borderwidth=0,
        )
        style.map("Primary.TButton", background=[("active", accent_hover), ("pressed", accent_hover)])
        style.configure("Secondary.TButton", font=("Segoe UI", 9), padding=(8, 5))

        style.configure("Mapping.Treeview", rowheight=22, font=("Segoe UI", 9), fieldbackground="white", background="white")
        style.configure("Mapping.Treeview.Heading", font=("Segoe UI", 9, "bold"), padding=(4, 4))

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=1)

        header = ttk.Label(self, text="Schemcon — авто-конвертация схем", style="Header.TLabel")
        header.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))

        versions_panel = ttk.LabelFrame(self, text="Панель версий", style="Panel.TLabelframe")
        versions_panel.grid(row=1, column=0, sticky="ew", padx=12, pady=6)
        versions_panel.columnconfigure(1, weight=1)

        ttk.Label(versions_panel, text="Из версии").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        self.source_version_var = tk.StringVar(value="1.21")
        self.source_combo = ttk.Combobox(versions_panel, textvariable=self.source_version_var, state="readonly", width=18)
        self.source_combo.grid(row=0, column=1, sticky="w", padx=8, pady=6)

        ttk.Label(versions_panel, text="В версию").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        self.target_version_var = tk.StringVar(value="1.16.5")
        self.target_combo = ttk.Combobox(versions_panel, textvariable=self.target_version_var, state="readonly", width=18)
        self.target_combo.grid(row=1, column=1, sticky="w", padx=8, pady=6)

        ttk.Button(versions_panel, text="Обновить список версий", command=self._refresh_version_choices, style="Secondary.TButton").grid(
            row=0, column=2, padx=8, pady=6
        )
        ttk.Button(
            versions_panel,
            text="Загрузить выбранные версии (+client.jar)",
            command=self._download_selected_versions,
            style="Secondary.TButton",
        ).grid(
            row=1, column=2, padx=8, pady=6
        )

        ttk.Button(
            versions_panel,
            text="Выбрать версии для batch (галочки)",
            command=self._open_multi_target_dialog,
            style="Secondary.TButton",
        ).grid(row=2, column=2, padx=8, pady=6)

        self.multi_targets_var = tk.StringVar(value="Batch-версии: не выбраны")
        ttk.Label(
            versions_panel,
            textvariable=self.multi_targets_var,
            foreground="#4f5d75",
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=8, pady=6)

        ttk.Label(
            versions_panel,
            text="Совет: сначала загрузите нужные версии, затем стройте mapping.",
            foreground="#4f5d75",
        ).grid(row=3, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 6))

        form = ttk.LabelFrame(self, text="Параметры конвертации", style="Panel.TLabelframe")
        form.grid(row=2, column=0, sticky="ew", padx=12, pady=6)
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Входной .schem").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        self.input_schem_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.input_schem_var).grid(row=0, column=1, sticky="ew", padx=8, pady=6)
        ttk.Button(form, text="Выбрать", command=self._pick_input).grid(row=0, column=2, padx=8, pady=6)

        ttk.Label(form, text="Выходной .schem").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        self.output_schem_var = tk.StringVar(value="converted_output.schem")
        ttk.Entry(form, textvariable=self.output_schem_var).grid(row=1, column=1, sticky="ew", padx=8, pady=6)
        ttk.Button(form, text="Выбрать", command=self._pick_output).grid(row=1, column=2, padx=8, pady=6)

        ttk.Label(form, text="FAWE папка schematics (необязательно)").grid(row=2, column=0, sticky="w", padx=8, pady=6)
        self.fawe_dir_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.fawe_dir_var).grid(row=2, column=1, sticky="ew", padx=8, pady=6)
        ttk.Button(form, text="Выбрать", command=self._pick_fawe_dir).grid(row=2, column=2, padx=8, pady=6)

        ttk.Label(form, text="Имя файла в FAWE").grid(row=3, column=0, sticky="w", padx=8, pady=6)
        self.fawe_name_var = tk.StringVar(value="converted")
        ttk.Entry(form, textvariable=self.fawe_name_var).grid(row=3, column=1, sticky="ew", padx=8, pady=6)

        tk.Checkbutton(
            form,
            text="Замена ступенек на блок при плохом совпадении цвета (>30%)",
            variable=self._stairs_to_block_fallback_var,
            onvalue=True,
            offvalue=False,
            anchor="w",
            justify="left",
            bg="#ffffff",
            activebackground="#ffffff",
        ).grid(row=4, column=0, columnspan=3, sticky="w", padx=8, pady=(2, 6))

        ttk.Label(
            form,
            text="Рекомендуется оставить галочку включённой для 1.7–1.12.",
            foreground="#4f5d75",
            background="#ffffff",
        ).grid(row=4, column=0, columnspan=3, sticky="e", padx=8, pady=(2, 6))

        ttk.Button(
            form,
            text="1) Построить mapping (только реальные замены)",
            style="Primary.TButton",
            command=self._run_auto,
        ).grid(row=5, column=0, columnspan=3, sticky="ew", padx=8, pady=(8, 6))

        ttk.Button(
            form,
            text="2) Подтвердить mapping и конвертировать",
            style="Primary.TButton",
            command=self._apply_mapping,
        ).grid(row=6, column=0, columnspan=3, sticky="ew", padx=8, pady=(0, 6))

        ttk.Button(
            form,
            text="3) Batch: автоконвертация в отмеченные версии",
            style="Secondary.TButton",
            command=self._batch_convert_selected_versions,
        ).grid(row=7, column=0, columnspan=3, sticky="ew", padx=8, pady=(0, 8))

        ttk.Separator(form, orient="horizontal").grid(row=8, column=0, columnspan=3, sticky="ew", padx=8, pady=(2, 6))
        ttk.Label(form, text="Конвертация формата схемы (.schem -> .schematic для старых версий)", background="#ffffff").grid(
            row=9, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 4)
        )

        format_row = ttk.Frame(form)
        format_row.grid(row=10, column=0, columnspan=3, sticky="ew", padx=8, pady=(0, 8))
        format_row.columnconfigure(1, weight=1)

        ttk.Label(format_row, text="Вход").grid(row=0, column=0, sticky="w")
        ttk.Entry(format_row, textvariable=self.format_input_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(format_row, text="...", width=4, command=self._pick_format_input).grid(row=0, column=2, padx=(0, 8))

        ttk.Label(format_row, text="Выход").grid(row=1, column=0, sticky="w")
        ttk.Entry(format_row, textvariable=self.format_output_var).grid(row=1, column=1, sticky="ew", padx=6)
        ttk.Button(format_row, text="...", width=4, command=self._pick_format_output).grid(row=1, column=2, padx=(0, 8))

        ttk.Label(format_row, text="Режим").grid(row=2, column=0, sticky="w")
        ttk.Combobox(
            format_row,
            textvariable=self.format_kind_var,
            state="readonly",
            values=("old_schematic_v2", "new_schem_v3"),
            width=20,
        ).grid(row=2, column=1, sticky="w", padx=6, pady=(2, 0))
        ttk.Button(
            format_row,
            text="Конвертировать формат",
            style="Secondary.TButton",
            command=self._convert_schematic_format,
        ).grid(row=2, column=2, padx=(0, 0), pady=(2, 0))

        preview = ttk.LabelFrame(self, text="Лог mapping (группы блоков, сворачиваемые)", style="Panel.TLabelframe")
        preview.grid(row=3, column=0, sticky="nsew", padx=12, pady=6)
        preview.columnconfigure(0, weight=1)
        preview.rowconfigure(1, weight=1)

        top_controls = ttk.Frame(preview)
        top_controls.grid(row=0, column=0, sticky="ew", padx=8, pady=6)
        top_controls.columnconfigure(0, weight=1)

        self.filter_var = tk.StringVar()
        filter_entry = ttk.Entry(top_controls, textvariable=self.filter_var)
        filter_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        filter_entry.bind("<KeyRelease>", lambda _e: self._refresh_tree())

        ttk.Button(top_controls, text="Изменить цель (выбранные блоки)", command=self._edit_selected_mapping, style="Secondary.TButton").grid(row=0, column=1, padx=(0, 8))
        ttk.Button(top_controls, text="Изменить цель для группы", command=self._edit_selected_group_mapping, style="Secondary.TButton").grid(row=0, column=2, padx=(0, 8))
        ttk.Button(top_controls, text="Выделить все блоки", command=self._select_all_mapping_rows, style="Secondary.TButton").grid(row=0, column=3, padx=(0, 8))
        ttk.Button(top_controls, text="Экспорт лога цветов", command=self._export_color_log, style="Secondary.TButton").grid(row=0, column=4)

        cols = ("source", "target", "reason", "src_props", "dst_props")
        self.tree = ttk.Treeview(preview, columns=cols, show="tree headings", height=16, style="Mapping.Treeview", selectmode="extended")
        self.tree.heading("#0", text="Текстуры src|dst")
        self.tree.column("#0", width=130, anchor="center")

        self.tree.heading("source", text="Исходный тег")
        self.tree.heading("target", text="Тег замены")
        self.tree.heading("reason", text="Причина")
        self.tree.heading("src_props", text="Свойства исходного")
        self.tree.heading("dst_props", text="Свойства замены")
        self.tree.column("source", width=320)
        self.tree.column("target", width=320)
        self.tree.column("reason", width=150, anchor="center")
        self.tree.column("src_props", width=240)
        self.tree.column("dst_props", width=240)

        self.tree.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=8)
        self.tree.bind("<Control-a>", self._select_all_mapping_rows)
        self.tree.tag_configure("changed", background="#fff5cc")
        self.tree.tag_configure("group", background="#dde9f7")

        ybar = ttk.Scrollbar(preview, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ybar.set)
        ybar.grid(row=1, column=1, sticky="ns", padx=(0, 8), pady=8)

        log_frame = ttk.LabelFrame(self, text="Системный лог", style="Panel.TLabelframe")
        log_frame.grid(row=4, column=0, sticky="nsew", padx=12, pady=(0, 12))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log = tk.Text(log_frame, height=8, wrap="word", state="disabled")
        self.log.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        self.rowconfigure(3, weight=1)
        self.rowconfigure(4, weight=1)

    def _refresh_version_choices(self) -> None:
        local = list_local_versions(self._version_root)
        common = [
            "1.21", "1.20.6", "1.20.4", "1.19.4", "1.18.2", "1.17.1", "1.16.5",
            "1.15.2", "1.14.4", "1.13.2", "1.12.2", "1.11.2", "1.10.2", "1.9.4", "1.8.9", "1.7.10",
        ]
        values = sorted(set(common + local), key=lambda v: tuple(int(p) if p.isdigit() else p for p in v.split('.')), reverse=True)
        self.source_combo["values"] = values
        self.target_combo["values"] = values
        if self.source_version_var.get() not in values and values:
            self.source_version_var.set(values[0])
        if self.target_version_var.get() not in values:
            self.target_version_var.set("1.16.5" if "1.16.5" in values else (values[-1] if values else ""))
        self._multi_target_versions = {v for v in self._multi_target_versions if v in values}
        self._update_multi_target_label()
        self._log(f"Доступные версии: {', '.join(values[:12])}{' ...' if len(values) > 12 else ''}")

    def _update_multi_target_label(self) -> None:
        if not hasattr(self, "multi_targets_var"):
            return
        if not self._multi_target_versions:
            self.multi_targets_var.set("Batch-версии: не выбраны")
            return
        versions = sorted(self._multi_target_versions, key=lambda v: tuple(int(p) if p.isdigit() else p for p in v.split('.')), reverse=True)
        preview = ", ".join(versions[:4])
        suffix = f" +{len(versions) - 4}" if len(versions) > 4 else ""
        self.multi_targets_var.set(f"Batch-версии ({len(versions)}): {preview}{suffix}")

    def _open_multi_target_dialog(self) -> None:
        values = list(self.source_combo["values"])
        if not values:
            messagebox.showwarning("Нет версий", "Сначала обновите/загрузите список версий.")
            return

        win = tk.Toplevel(self)
        win.title("Выбор batch-версий")
        win.transient(self.winfo_toplevel())
        win.grab_set()
        win.geometry("340x460")

        ttk.Label(win, text="Отметьте версии, в которые нужно сразу конвертировать:").pack(anchor="w", padx=12, pady=(12, 8))

        container = ttk.Frame(win)
        container.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)

        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        vars_by_version: dict[str, tk.BooleanVar] = {}
        source_version = self.source_version_var.get().strip()
        for ver in values:
            var = tk.BooleanVar(value=ver in self._multi_target_versions)
            vars_by_version[ver] = var
            state = "disabled" if ver == source_version else "normal"
            cb = tk.Checkbutton(inner, text=ver, variable=var, anchor="w", justify="left", state=state)
            if ver == source_version:
                cb.configure(disabledforeground="#888888")
            cb.pack(fill="x", anchor="w", padx=2, pady=2)

        btns = ttk.Frame(win)
        btns.pack(fill="x", padx=12, pady=(0, 12))

        def _select_all() -> None:
            for ver, var in vars_by_version.items():
                if ver != source_version:
                    var.set(True)

        def _clear_all() -> None:
            for var in vars_by_version.values():
                var.set(False)

        def _save() -> None:
            selected = {ver for ver, var in vars_by_version.items() if var.get() and ver != source_version}
            self._multi_target_versions = selected
            self._update_multi_target_label()
            self._log(f"Batch-версии обновлены: {', '.join(sorted(selected)) if selected else 'не выбраны'}")
            win.destroy()

        ttk.Button(btns, text="Выбрать все", command=_select_all).pack(side="left")
        ttk.Button(btns, text="Снять всё", command=_clear_all).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="Сохранить", command=_save).pack(side="right")

    def _download_selected_versions(self) -> None:
        try:
            source_version = self.source_version_var.get().strip()
            target_version = self.target_version_var.get().strip()
            if not source_version or not target_version:
                raise ValueError("Выберите обе версии в выпадающем списке.")

            manifest = fetch_version_manifest()
            self._prepare_version_registry(source_version, manifest, self._version_root)
            self._prepare_version_registry(target_version, manifest, self._version_root)
            self._refresh_version_choices()
            messagebox.showinfo("Готово", f"Версии подготовлены:\n{source_version}\n{target_version}")
        except Exception as exc:  # noqa: BLE001
            self._log(f"Ошибка загрузки версий: {exc}")
            messagebox.showerror("Ошибка", str(exc))

    def _pick_input(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Schematic", "*.schem")])
        if path:
            self.input_schem_var.set(path)
            if not self.output_schem_var.get().strip() or self.output_schem_var.get() == "converted_output.schem":
                src = pathlib.Path(path)
                self.output_schem_var.set(str(src.with_name(f"{src.stem}_converted.schem")))

    def _pick_output(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".schem", filetypes=[("Schematic", "*.schem")])
        if path:
            self.output_schem_var.set(path)

    def _pick_format_input(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Schematic", "*.schem *.schematic")])
        if path:
            self.format_input_var.set(path)
            if not self.format_output_var.get().strip() or self.format_output_var.get() == "converted_output.schematic":
                src = pathlib.Path(path)
                self.format_output_var.set(str(src.with_name(f"{src.stem}_legacy.schematic")))

    def _pick_format_output(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".schematic", filetypes=[("Schematic", "*.schematic *.schem")])
        if path:
            self.format_output_var.set(path)

    def _convert_schematic_format(self) -> None:
        try:
            input_path = self.format_input_var.get().strip() or self.input_schem_var.get().strip()
            output_path = self.format_output_var.get().strip()
            if not input_path or not pathlib.Path(input_path).exists():
                raise FileNotFoundError("Укажите существующий входной .schem/.schematic файл.")
            if not output_path:
                raise ValueError("Укажите путь для выходного файла формата.")

            mode = self.format_kind_var.get().strip() or "old_schematic_v2"
            schem = load_schematic(input_path)
            save_schematic(schem, output_path)

            sponge_version = 2 if mode == "old_schematic_v2" else 3
            export_fawe_compatible(output_path, sponge_version=sponge_version)

            self._log(f"Формат конвертирован: {input_path} -> {output_path} (Sponge v{sponge_version})")
            messagebox.showinfo("Готово", f"Формат схемы успешно конвертирован.\nРежим: Sponge v{sponge_version}")
        except Exception as exc:  # noqa: BLE001
            self._log(f"Ошибка конвертации формата: {exc}")
            messagebox.showerror("Ошибка", str(exc))

    def _pick_fawe_dir(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.fawe_dir_var.set(path)

    def _log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert(tk.END, text + "\n")
        self.log.configure(state="disabled")
        self.log.see(tk.END)

    def _normalize_block(self, block_name: str) -> str:
        base = block_name.split("[", 1)[0]
        return base if ":" in base else f"minecraft:{base}"

    def _color_from_gradient_map(self, block_name: str) -> tuple[int, int, int] | None:
        base = self._normalize_block(block_name)
        bare = base.replace("minecraft:", "")
        candidates = [block_name, base, bare, f"minecraft:{bare}"]
        for key in candidates:
            value = self._current_gradient_map.get(key)
            if value:
                return value
        return None

    def _block_color(self, block_name: str) -> tuple[int, int, int]:
        sampled = self._color_from_gradient_map(block_name)
        if sampled:
            return sampled
        tr = categorize_block(block_name)
        return tr.color or (120, 120, 120)

    def _props(self, block_name: str) -> str:
        tr = categorize_block(block_name)
        color = self._block_color(block_name)
        return f"shape={tr.shape}, family={tr.family}, color={color}"

    def _group_key_for_block(self, block_name: str) -> str:
        tr = categorize_block(block_name)
        return f"{tr.category}/{tr.shape}"

    def _color_mismatch_ratio(self, left: tuple[int, int, int], right: tuple[int, int, int]) -> float:
        dr = left[0] - right[0]
        dg = left[1] - right[1]
        db = left[2] - right[2]
        dist = (dr * dr + dg * dg + db * db) ** 0.5
        return dist / 441.6729559300637  # sqrt(255^2 * 3)

    def _explicit_color_token(self, block_name: str) -> str | None:
        base = self._normalize_block(block_name).replace("minecraft:", "")
        order = [
            "light_blue",
            "light_gray",
            "white",
            "orange",
            "magenta",
            "yellow",
            "lime",
            "pink",
            "gray",
            "cyan",
            "purple",
            "blue",
            "brown",
            "green",
            "red",
            "black",
        ]
        for token in order:
            if token in base:
                return token
        return None

    def _stairs_mismatch_ratio(self, source_block: str, target_block: str) -> float:
        ratio = self._color_mismatch_ratio(self._block_color(source_block), self._block_color(target_block))
        src_color = self._explicit_color_token(source_block)
        tgt_color = self._explicit_color_token(target_block)
        if src_color and tgt_color and src_color != tgt_color:
            return max(ratio, 0.75)
        return ratio

    def _fallback_block_for_stair(self, source_block: str, target_blocks: set[str]) -> str | None:
        src_color = self._block_color(source_block)
        src_traits = categorize_block(source_block)

        best: tuple[float, str] | None = None
        for candidate in sorted(target_blocks):
            cand_base = self._normalize_block(candidate)
            cand_traits = categorize_block(cand_base)

            # Replace stair only with full solid-looking blocks.
            if cand_traits.shape != "full":
                continue
            if cand_traits.block_type != "solid":
                continue

            score = 0.0
            if cand_traits.family in {"concrete", "wool", "planks", "stone", "deepslate", "blackstone", "brick"}:
                score += 2.0
            if cand_traits.family == src_traits.family:
                score += 1.5

            cand_color = self._block_color(cand_base)
            ratio = self._color_mismatch_ratio(src_color, cand_color)
            score -= ratio * 10.0

            if best is None or score > best[0]:
                best = (score, cand_base)

        return best[1] if best else None

    def _version_token(self, version: str) -> str:
        return re.sub(r"[^0-9A-Za-z]+", "_", version.strip()).strip("_")

    def _build_auto_mapping(self, palette_blocks: set[str], target_blocks: set[str]) -> dict[str, dict[str, str]]:
        mapping: dict[str, dict[str, str]] = {}
        for block in sorted(palette_blocks):
            base_block = self._normalize_block(block)
            base_bare = base_block.replace("minecraft:", "")
            if base_block in target_blocks or base_bare in target_blocks:
                mapping[block] = {"target": block, "reason": "exists_in_target"}
                continue

            res = pick_best_match(block, target_blocks, gradient_map=self._current_gradient_map)
            if res.target == "minecraft:air" and "[" in block:
                base_res = pick_best_match(base_block, target_blocks, gradient_map=self._current_gradient_map)
                if base_res.target != "minecraft:air":
                    res = base_res

            if self._stairs_to_block_fallback_var.get():
                src_traits = categorize_block(block)
                tgt_traits = categorize_block(res.target)
                if src_traits.shape == "stairs" and tgt_traits.shape == "stairs":
                    mismatch = self._stairs_mismatch_ratio(block, res.target)
                    if mismatch > 0.3:
                        block_fallback = self._fallback_block_for_stair(block, target_blocks)
                        if block_fallback:
                            res = type(res)(
                                source=res.source,
                                target=block_fallback,
                                reason=f"stairs_color_to_block({mismatch:.2f})",
                                confidence=max(0.55, res.confidence - 0.2),
                            )
            mapping[block] = {"target": res.target, "reason": res.reason}
        return mapping

    def _batch_convert_selected_versions(self) -> None:
        try:
            source_version = self.source_version_var.get().strip()
            selected_targets = sorted(v for v in self._multi_target_versions if v != source_version)
            input_schem = self.input_schem_var.get().strip()
            output_schem = self.output_schem_var.get().strip()
            if not source_version:
                raise ValueError("Выберите исходную версию.")
            if not selected_targets:
                raise ValueError("Отметьте хотя бы одну target-версию (кнопка 'Выбрать версии для batch').")
            if not input_schem or not pathlib.Path(input_schem).exists():
                raise FileNotFoundError("Укажите существующий входной .schem файл.")
            if not output_schem:
                raise ValueError("Укажите базовый путь выходного .schem.")

            self._current_source_version = source_version
            self._pending_input_schem = input_schem

            manifest = fetch_version_manifest()
            self._prepare_version_registry(source_version, manifest, self._version_root)
            for target_version in selected_targets:
                self._prepare_version_registry(target_version, manifest, self._version_root)

            gradient_stats = refresh_gradient_maps_for_local_versions(
                self._version_root,
                pathlib.Path("data/gradients"),
            )
            if gradient_stats:
                self._log(
                    "Градиент-карты обновлены: "
                    + ", ".join(f"{ver}={count}" for ver, count in sorted(gradient_stats.items()))
                )

            source_registry = load_registry(self._version_root / source_version)
            source_blocks = set(source_registry.keys())
            input_palette = load_schematic(input_schem).palette
            palette_blocks = set(input_palette.keys())

            mapping_root = pathlib.Path("data/mappings")
            mapping_root.mkdir(parents=True, exist_ok=True)

            out_base = pathlib.Path(output_schem)
            done = 0
            for target_version in selected_targets:
                target_registry = load_registry(self._version_root / target_version)
                target_blocks = set(target_registry.keys())

                self._current_target_version = target_version
                self._current_target_blocks = target_blocks
                self._current_gradient_map = self._build_or_load_gradient_map(
                    source_version,
                    target_version,
                    source_blocks,
                    target_blocks,
                )

                mapping = self._build_auto_mapping(palette_blocks, target_blocks)
                mapping_path = mapping_root / f"{source_version}-to-{target_version}.json"
                mapping_path.write_text(json.dumps(mapping, indent=2), encoding="utf-8")

                src_token = self._version_token(source_version)
                dst_token = self._version_token(target_version)
                output_for_target = out_base.with_name(f"{out_base.stem}_{src_token}_to_{dst_token}{out_base.suffix}")
                flat_mapping = {k: v.get("target", "minecraft:air") for k, v in mapping.items()}
                report = convert_schematic(input_schem, str(output_for_target), flat_mapping, allowed_targets=target_blocks)
                report_path = output_for_target.with_suffix(".report.json")
                report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

                self._log(f"Batch OK: {source_version} -> {target_version}")
                self._log(f"  mapping: {mapping_path}")
                self._log(f"  schematic: {output_for_target}")
                self._log(f"  report: {report_path}")
                done += 1

            messagebox.showinfo("Batch завершён", f"Успешно сконвертировано версий: {done}")
        except Exception as exc:  # noqa: BLE001
            self._log(f"Ошибка batch-конвертации: {exc}")
            messagebox.showerror("Ошибка", str(exc))

    def _run_auto(self) -> None:
        try:
            source_version = self.source_version_var.get().strip()
            target_version = self.target_version_var.get().strip()
            input_schem = self.input_schem_var.get().strip()
            output_schem = self.output_schem_var.get().strip()
            if not source_version or not target_version:
                raise ValueError("Выберите обе версии.")
            if not input_schem or not pathlib.Path(input_schem).exists():
                raise FileNotFoundError("Укажите существующий входной .schem файл.")
            if not output_schem:
                raise ValueError("Укажите путь выходного .schem.")

            self._current_source_version = source_version
            self._current_target_version = target_version
            self._pending_output_schem = output_schem
            self._pending_input_schem = input_schem

            self._log(f"Старт: {source_version} -> {target_version}")
            version_root = self._version_root
            mapping_root = pathlib.Path("data/mappings")
            mapping_root.mkdir(parents=True, exist_ok=True)
            mapping_path = mapping_root / f"{source_version}-to-{target_version}.json"

            manifest = fetch_version_manifest()
            self._prepare_version_registry(source_version, manifest, version_root)
            self._prepare_version_registry(target_version, manifest, version_root)

            gradient_stats = refresh_gradient_maps_for_local_versions(
                version_root,
                pathlib.Path("data/gradients"),
            )
            if gradient_stats:
                self._log(
                    "Градиент-карты обновлены: "
                    + ", ".join(f"{ver}={count}" for ver, count in sorted(gradient_stats.items()))
                )

            source_registry = load_registry(version_root / source_version)
            target_registry = load_registry(version_root / target_version)
            source_blocks = set(source_registry.keys())
            target_blocks = set(target_registry.keys())
            self._current_target_blocks = target_blocks

            self._current_gradient_map = self._build_or_load_gradient_map(
                source_version, target_version, source_blocks, target_blocks
            )
            self._log(f"3D-градиент цветов загружен: {len(self._current_gradient_map)} блоков")

            input_palette = load_schematic(input_schem).palette
            palette_blocks = set(input_palette.keys())

            mapping = self._build_auto_mapping(palette_blocks, target_blocks)

            mapping_path.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
            self._pending_mapping = mapping
            self._log(f"Mapping сохранён: {mapping_path}")

            # Keep ONLY real replacements (source != target by base id)
            self._mapping_rows = []
            self._pair_icon_cache.clear()
            for src, meta in sorted(mapping.items()):
                tgt = meta.get("target", "minecraft:air")
                changed = self._normalize_block(src) != self._normalize_block(tgt)
                if not changed:
                    continue
                self._mapping_rows.append(
                    {
                        "source": src,
                        "target": tgt,
                        "reason": meta.get("reason", "mapped"),
                        "src_props": self._props(src),
                        "dst_props": self._props(tgt),
                        "src_color": str(self._block_color(src)),
                        "dst_color": str(self._block_color(tgt)),
                        "changed": "1",
                        "group": self._group_key_for_block(src),
                    }
                )
            self._refresh_tree()
            self._log(f"Реальных замен: {len(self._mapping_rows)}")
            messagebox.showinfo("Mapping готов", "Показаны только реальные замены, сгруппированные по типам.")
        except Exception as exc:  # noqa: BLE001
            self._log(f"Ошибка: {exc}")
            messagebox.showerror("Ошибка", str(exc))

    def _apply_mapping(self) -> None:
        try:
            if not self._pending_mapping:
                raise ValueError("Сначала постройте mapping (кнопка 1).")
            output_schem = self.output_schem_var.get().strip() or self._pending_output_schem
            input_schem = self.input_schem_var.get().strip() or self._pending_input_schem
            fawe_dir = self.fawe_dir_var.get().strip()
            fawe_name = self.fawe_name_var.get().strip()
            if not input_schem:
                raise ValueError("Не найден входной .schem путь.")
            if not output_schem:
                raise ValueError("Не указан выходной .schem путь.")

            flat_mapping = {k: v.get("target", "minecraft:air") for k, v in self._pending_mapping.items()}
            report = convert_schematic(input_schem, output_schem, flat_mapping, allowed_targets=self._current_target_blocks)
            report_path = pathlib.Path(output_schem).with_suffix(".report.json")
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            self._log(f"Схема конвертирована: {output_schem}")
            self._log(f"Отчёт: {report_path}")

            if fawe_dir:
                fawe_path = self._copy_to_fawe(output_schem, fawe_dir, fawe_name)
                cmd_name = fawe_path.stem
                self._log(f"FAWE файл: {fawe_path}")
                self._log(f"Команда в игре: //schem load {cmd_name}")

            messagebox.showinfo("Готово", "Конвертация успешно завершена.")
        except Exception as exc:  # noqa: BLE001
            self._log(f"Ошибка: {exc}")
            messagebox.showerror("Ошибка", str(exc))

    def _selected_leaf_items(self) -> list[str]:
        selected = list(self.tree.selection())
        leaf_items: list[str] = []
        seen: set[str] = set()

        for item in selected:
            if self.tree.parent(item) == "":
                children = self.tree.get_children(item)
                for child in children:
                    if child not in seen:
                        leaf_items.append(child)
                        seen.add(child)
            elif item not in seen:
                leaf_items.append(item)
                seen.add(item)

        return leaf_items

    def _select_all_mapping_rows(self, _event: object | None = None) -> str:
        leaf_items: list[str] = []
        for group_item in self.tree.get_children(""):
            leaf_items.extend(self.tree.get_children(group_item))
        if leaf_items:
            self.tree.selection_set(leaf_items)
            self.tree.focus(leaf_items[0])
        return "break"

    def _edit_selected_mapping(self) -> None:
        leaf_items = self._selected_leaf_items()
        if not leaf_items:
            messagebox.showwarning("Нет выбора", "Выберите один или несколько блоков в mapping для редактирования.")
            return

        selected_rows: list[tuple[str, str]] = []
        for item in leaf_items:
            values = self.tree.item(item, "values")
            if not values:
                continue
            selected_rows.append((values[0], values[1]))

        if not selected_rows:
            messagebox.showwarning("Нет выбора", "Выбраны только группы без блоков в текущем фильтре.")
            return

        current_target = selected_rows[0][1]
        title = "Изменение замены"
        prompt = "Введите целевой блок (например minecraft:red_wool):"
        if len(selected_rows) > 1:
            title = "Массовое изменение"
            prompt = f"Введите целевой блок для {len(selected_rows)} выбранных блоков:"

        new_target = simpledialog.askstring(
            title,
            prompt,
            initialvalue=current_target,
            parent=self,
        )
        if new_target is None:
            return

        new_target = new_target.strip()
        if not new_target:
            return
        if ":" not in new_target:
            new_target = f"minecraft:{new_target}"

        base_target = self._normalize_block(new_target)
        base_target_bare = base_target.replace("minecraft:", "")
        if base_target not in self._current_target_blocks and base_target_bare not in self._current_target_blocks:
            messagebox.showerror("Некорректная цель", f"Блок отсутствует в target версии: {base_target}")
            return

        selected_sources = {src for src, _ in selected_rows}
        rows_by_source = {row["source"]: row for row in self._mapping_rows}
        reason = "manual_override" if len(selected_rows) == 1 else "manual_bulk_override"

        for source_block in selected_sources:
            if source_block not in self._pending_mapping:
                self._pending_mapping[source_block] = {}
            self._pending_mapping[source_block]["target"] = new_target
            self._pending_mapping[source_block]["reason"] = reason

            row = rows_by_source.get(source_block)
            if row is not None:
                row["target"] = new_target
                row["reason"] = reason
                row["dst_props"] = self._props(new_target)
                row["dst_color"] = str(self._block_color(new_target))

        self._refresh_tree()
        if len(selected_rows) == 1:
            self._log(f"Manual override: {selected_rows[0][0]} -> {new_target}")
        else:
            self._log(f"Bulk override: {len(selected_rows)} блоков -> {new_target}")

    def _edit_selected_group_mapping(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Нет выбора", "Выберите группу в mapping дереве.")
            return

        group_item = selected[0]
        if self.tree.parent(group_item) != "":
            group_item = self.tree.parent(group_item)

        group_name = self.tree.item(group_item, "text")
        rows = self._group_children.get(group_item, [])
        if not rows:
            messagebox.showwarning("Пустая группа", "В выбранной группе нет блоков для редактирования.")
            return

        new_target = simpledialog.askstring(
            "Изменение группы",
            f"Введите целевой блок для всей группы '{group_name}':",
            initialvalue=rows[0]["target"],
            parent=self,
        )
        if new_target is None:
            return
        new_target = new_target.strip()
        if not new_target:
            return
        if ":" not in new_target:
            new_target = f"minecraft:{new_target}"

        base_target = self._normalize_block(new_target)
        base_target_bare = base_target.replace("minecraft:", "")
        if base_target not in self._current_target_blocks and base_target_bare not in self._current_target_blocks:
            messagebox.showerror("Некорректная цель", f"Блок отсутствует в target версии: {base_target}")
            return

        changed_count = 0
        for row in rows:
            src = row["source"]
            if src not in self._pending_mapping:
                self._pending_mapping[src] = {}
            self._pending_mapping[src]["target"] = new_target
            self._pending_mapping[src]["reason"] = "manual_group_override"

            row["target"] = new_target
            row["reason"] = "manual_group_override"
            row["dst_props"] = self._props(new_target)
            row["dst_color"] = str(self._block_color(new_target))
            changed_count += 1

        self._refresh_tree()
        self._log(f"Group override ({group_name}): {changed_count} блоков -> {new_target}")

    def _export_color_log(self) -> None:
        if not self._mapping_rows:
            messagebox.showwarning("Пусто", "Сначала постройте mapping.")
            return

        lines = ["source_block\tsource_color\ttarget_block\ttarget_color\treason\tgroup"]
        for row in self._mapping_rows:
            lines.append(
                "\t".join(
                    [
                        row["source"],
                        row.get("src_color", ""),
                        row["target"],
                        row.get("dst_color", ""),
                        row["reason"],
                        row.get("group", ""),
                    ]
                )
            )
        payload = "\n".join(lines)

        out_path = pathlib.Path(self.output_schem_var.get().strip() or "mapping").with_suffix(".color-log.tsv")
        out_path.write_text(payload, encoding="utf-8")

        self.clipboard_clear()
        self.clipboard_append(payload)
        self._log(f"Лог цветов сохранён: {out_path} (и скопирован в буфер)")
        messagebox.showinfo("Готово", f"Лог цветов сохранён:\n{out_path}\n\nТакже скопирован в буфер обмена.")

    def _prepare_version_registry(self, version: str, manifest: dict, version_root: pathlib.Path) -> None:
        version_dir = version_root / version
        version_dir.mkdir(parents=True, exist_ok=True)

        info = resolve_version_info(version, manifest)
        version_json = fetch_version_json(info)

        jar_path = version_dir / f"{version}.jar"
        if not jar_path.exists():
            download_server_jar(version_json, jar_path)

        _paths, source = ensure_registry_reports(version, jar_path, version_dir, version_json=version_json)
        self._log(f"Реестр {version} обновлён (source={source})")

        client_jar = version_dir / f"{version}.client.jar"
        if not client_jar.exists():
            try:
                download_client_jar(version_json, client_jar)
                self._log(f"Client jar загружен для текстур: {client_jar.name}")
            except Exception:
                self._log(f"Client jar для версии {version} недоступен, будет fallback-цвет.")

    def _build_or_load_gradient_map(
        self,
        source_version: str,
        target_version: str,
        source_blocks: set[str],
        target_blocks: set[str],
    ) -> dict[str, tuple[int, int, int]]:
        gradients_dir = pathlib.Path("data/gradients")
        source_file = gradients_dir / f"{source_version}.json"
        target_file = gradients_dir / f"{target_version}.json"
        source_grad = load_gradient_map(source_file)
        target_grad = load_gradient_map(target_file)

        source_client = self._version_root / source_version / f"{source_version}.client.jar"
        target_client = self._version_root / target_version / f"{target_version}.client.jar"

        if source_client.exists() and len(source_grad) < max(32, len(source_blocks) // 3):
            source_grad = build_gradient_map(source_client, source_blocks)
            save_gradient_map(source_file, source_grad)
            self._log(f"Карта градиента source обновлена: {len(source_grad)} текстур")

        if target_client.exists() and len(target_grad) < max(32, len(target_blocks) // 3):
            target_grad = build_gradient_map(target_client, target_blocks)
            save_gradient_map(target_file, target_grad)
            self._log(f"Карта градиента target обновлена: {len(target_grad)} текстур")

        return {**source_grad, **target_grad}

    def _normalize_fawe_name(self, raw: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_\-]", "_", raw).strip("_")
        if not cleaned:
            cleaned = "converted"
        return cleaned.lower()

    def _copy_to_fawe(self, output_schem: str, fawe_dir: str, fawe_name: str) -> pathlib.Path:
        out_path = pathlib.Path(output_schem)
        if not out_path.exists():
            raise FileNotFoundError(f"Выходной файл не найден: {out_path}")
        target_dir = pathlib.Path(fawe_dir)
        if not target_dir.exists():
            raise FileNotFoundError(f"Папка FAWE не найдена: {target_dir}")
        name = self._normalize_fawe_name(fawe_name or out_path.stem)

        export_fawe_compatible(str(out_path), sponge_version=2)
        target = target_dir / f"{name}.schem"
        shutil.copy2(out_path, target)

        v3_source = out_path.with_name(f"{out_path.stem}.v3.schem")
        shutil.copy2(out_path, v3_source)
        export_fawe_compatible(str(v3_source), sponge_version=3)
        target_v3 = target_dir / f"{name}_v3.schem"
        shutil.copy2(v3_source, target_v3)
        try:
            v3_source.unlink()
        except Exception:
            pass
        self._log(f"FAWE fallback v3 файл: {target_v3}")
        self._log(f"Команда в игре (v3): //schem load {target_v3.stem}")

        return target

    def _get_jar_members(self, version: str) -> set[str]:
        cached = self._jar_member_index.get(version)
        if cached is not None:
            return cached

        client_jar = self._version_root / version / f"{version}.client.jar"
        if not client_jar.exists():
            self._jar_member_index[version] = set()
            return set()

        try:
            with zipfile.ZipFile(client_jar) as jar:
                members = set(jar.namelist())
            self._jar_member_index[version] = members
            return members
        except Exception:
            self._jar_member_index[version] = set()
            return set()

    def _load_json_from_client_jar(self, version: str, member: str) -> dict[str, Any] | None:
        client_jar = self._version_root / version / f"{version}.client.jar"
        if not client_jar.exists():
            return None
        try:
            with zipfile.ZipFile(client_jar) as jar:
                return json.loads(jar.read(member).decode("utf-8"))
        except Exception:
            return None

    def _collect_model_textures(self, version: str, model_name: str, merged: dict[str, str], visited: set[str]) -> dict[str, str]:
        model_clean = model_name.replace("minecraft:", "")
        if model_clean.startswith("blocks/"):
            model_clean = f"block/{model_clean.split('/', 1)[1]}"
        if not model_clean.startswith("block/"):
            model_clean = f"block/{model_clean}"
        if model_clean in visited:
            return merged
        visited.add(model_clean)

        model_file = f"assets/minecraft/models/{model_clean}.json"
        payload = self._load_json_from_client_jar(version, model_file)
        if not payload:
            return merged

        parent = payload.get("parent")
        if isinstance(parent, str) and parent:
            merged = self._collect_model_textures(version, parent, merged, visited)

        textures = payload.get("textures")
        if isinstance(textures, dict):
            for k, v in textures.items():
                if isinstance(v, str):
                    merged[k] = v

        return merged

    def _texture_member_candidates(self, texture_ref: str) -> list[str]:
        ref = texture_ref.replace("minecraft:", "")
        if ref.startswith("textures/"):
            ref = ref[len("textures/") :]

        candidates: list[str] = []
        seen: set[str] = set()

        def add(path: str) -> None:
            if path not in seen:
                seen.add(path)
                candidates.append(path)

        if ref.endswith(".png"):
            add(f"assets/minecraft/{ref}")
            add(f"assets/minecraft/textures/{ref}")
            return candidates

        base = ref
        if base.startswith("block/"):
            tail = base.split("/", 1)[1]
            add(f"assets/minecraft/textures/block/{tail}.png")
            add(f"assets/minecraft/textures/blocks/{tail}.png")
            add(f"assets/minecraft/textures/items/{tail}.png")
            return candidates

        if base.startswith("blocks/"):
            tail = base.split("/", 1)[1]
            add(f"assets/minecraft/textures/blocks/{tail}.png")
            add(f"assets/minecraft/textures/block/{tail}.png")
            add(f"assets/minecraft/textures/items/{tail}.png")
            return candidates

        if base.startswith("item/"):
            tail = base.split("/", 1)[1]
            add(f"assets/minecraft/textures/item/{tail}.png")
            add(f"assets/minecraft/textures/items/{tail}.png")
            return candidates

        if base.startswith("items/"):
            tail = base.split("/", 1)[1]
            add(f"assets/minecraft/textures/items/{tail}.png")
            add(f"assets/minecraft/textures/item/{tail}.png")
            return candidates

        # Unknown prefix / plain texture id - try common folders for new+old versions.
        add(f"assets/minecraft/textures/block/{base}.png")
        add(f"assets/minecraft/textures/blocks/{base}.png")
        add(f"assets/minecraft/textures/item/{base}.png")
        add(f"assets/minecraft/textures/items/{base}.png")
        return candidates

    def _resolve_model_texture_member(self, version: str, model_name: str, visited: set[str]) -> str | None:
        members = self._get_jar_members(version)
        merged = self._collect_model_textures(version, model_name, {}, visited)
        if not merged:
            return None

        preferred = ["all", "side", "front", "top", "end", "particle", "north", "south", "east", "west", "bottom"]

        def resolve_ref(value: str) -> str | None:
            current = value
            guard = 0
            while current.startswith("#") and guard < 12:
                guard += 1
                current = merged.get(current[1:], "")
                if not current:
                    return None
            return current or None

        for key in preferred + list(merged.keys()):
            value = merged.get(key)
            if not isinstance(value, str):
                continue
            resolved = resolve_ref(value)
            if not resolved:
                continue
            for tex_member in self._texture_member_candidates(resolved):
                if tex_member in members:
                    return tex_member
        return None

    def _find_texture_member(self, version: str, block_name: str) -> str | None:
        members = self._get_jar_members(version)
        if not members:
            return None

        base = self._normalize_block(block_name).replace("minecraft:", "")

        candidates = [base, f"{base}_side", f"{base}_front", f"{base}_top", f"{base}_end"]
        for candidate in candidates:
            for member in self._texture_member_candidates(candidate):
                if member in members:
                    return member

        blockstate_member = f"assets/minecraft/blockstates/{base}.json"
        blockstate = self._load_json_from_client_jar(version, blockstate_member)
        if blockstate:
            variants = blockstate.get("variants")
            if isinstance(variants, dict) and variants:
                for variant in variants.values():
                    if isinstance(variant, list):
                        items = variant
                    else:
                        items = [variant]
                    for item in items:
                        if isinstance(item, dict) and isinstance(item.get("model"), str):
                            tex = self._resolve_model_texture_member(version, item["model"], set())
                            if tex:
                                return tex

            multipart = blockstate.get("multipart")
            if isinstance(multipart, list):
                for part in multipart:
                    if not isinstance(part, dict):
                        continue
                    apply = part.get("apply")
                    applies = apply if isinstance(apply, list) else [apply]
                    for ap in applies:
                        if isinstance(ap, dict) and isinstance(ap.get("model"), str):
                            tex = self._resolve_model_texture_member(version, ap["model"], set())
                            if tex:
                                return tex

        return None

    def _extract_texture_file(self, version: str, member: str) -> pathlib.Path | None:
        cache_dir = pathlib.Path("data/texture_cache") / version
        cache_dir.mkdir(parents=True, exist_ok=True)
        target_file = cache_dir / pathlib.Path(member).name
        if target_file.exists():
            return target_file

        client_jar = self._version_root / version / f"{version}.client.jar"
        if not client_jar.exists():
            return None
        try:
            with zipfile.ZipFile(client_jar) as jar:
                target_file.write_bytes(jar.read(member))
            return target_file
        except Exception:
            return None

    def _solid_icon(self, color: tuple[int, int, int]) -> tk.PhotoImage:
        key = f"solid:{color}"
        cached = self._block_icon_cache.get(key)
        if cached:
            return cached

        img = tk.PhotoImage(width=16, height=16)
        fill = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
        img.put(fill, to=(0, 0, 16, 16))
        img.put("#1f1f1f", to=(0, 0, 16, 1))
        img.put("#1f1f1f", to=(0, 0, 1, 16))
        img.put("#d9d9d9", to=(15, 0, 16, 16))
        img.put("#d9d9d9", to=(0, 15, 16, 16))
        self._block_icon_cache[key] = img
        return img

    def _texture_icon(self, version: str, block_name: str) -> tk.PhotoImage:
        cache_key = f"{version}:{self._normalize_block(block_name)}"
        cached = self._block_icon_cache.get(cache_key)
        if cached:
            return cached

        member = self._find_texture_member(version, block_name)
        if member:
            texture = self._extract_texture_file(version, member)
            if texture:
                try:
                    img = tk.PhotoImage(file=str(texture))
                    if img.width() > 16 or img.height() > 16:
                        sx = max(1, img.width() // 16)
                        sy = max(1, img.height() // 16)
                        img = img.subsample(sx, sy)
                    self._block_icon_cache[cache_key] = img
                    return img
                except Exception:
                    pass

        fallback = self._solid_icon(self._block_color(block_name))
        self._block_icon_cache[cache_key] = fallback
        return fallback

    def _pair_icon(self, source_block: str, target_block: str) -> tk.PhotoImage:
        key = f"{self._current_source_version}:{source_block}|{self._current_target_version}:{target_block}"
        cached = self._pair_icon_cache.get(key)
        if cached:
            return cached

        src_img = self._texture_icon(self._current_source_version, source_block)
        tgt_img = self._texture_icon(self._current_target_version, target_block)

        pair = tk.PhotoImage(width=36, height=16)
        pair.put("#f0f0f0", to=(0, 0, 36, 16))
        pair.tk.call(pair, "copy", src_img, "-to", 0, 0)
        pair.put("#555555", to=(17, 0, 19, 16))
        pair.tk.call(pair, "copy", tgt_img, "-to", 20, 0)
        self._pair_icon_cache[key] = pair
        return pair

    def _refresh_tree(self) -> None:
        query = self.filter_var.get().strip().lower()
        for item in self.tree.get_children():
            self.tree.delete(item)

        grouped: dict[str, list[dict[str, str]]] = {}
        for row in self._mapping_rows:
            if query and query not in row["source"].lower() and query not in row["target"].lower() and query not in row.get("group", "").lower():
                continue
            grouped.setdefault(row.get("group", "прочее"), []).append(row)

        self._group_children = {}
        for group_name, rows in sorted(grouped.items(), key=lambda kv: kv[0]):
            parent = self.tree.insert(
                "",
                tk.END,
                text=f"{group_name} ({len(rows)})",
                values=("", "", "group", "", ""),
                tags=("group",),
                open=True,
            )
            self._group_children[parent] = rows

            for idx, row in enumerate(rows):
                icon = self._pair_icon(row["source"], row["target"])
                icon_key = f"row-{group_name}-{idx}"
                self._photo_refs[icon_key] = icon
                self.tree.insert(
                    parent,
                    tk.END,
                    text="",
                    image=icon,
                    values=(
                        row["source"],
                        row["target"],
                        row["reason"],
                        row["src_props"],
                        row["dst_props"],
                    ),
                    tags=("changed",),
                )


def launch_gui() -> None:
    root = tk.Tk()
    root.title("Schemcon")
    root.geometry("1550x940")
    SchemconApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
