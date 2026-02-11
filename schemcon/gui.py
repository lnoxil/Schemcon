from __future__ import annotations

import json
import pathlib
import re
import shutil
import zipfile
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .categories import categorize_block
from .convert import convert_schematic
from .gradient import (
    build_gradient_map,
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
from .schem import export_fawe_compatible, load_schematic


class SchemconApp(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master)
        self.pack(fill=tk.BOTH, expand=True)
        self._mapping_rows: list[dict[str, str]] = []
        self._texture_index: dict[str, set[str]] = {}
        self._photo_refs: dict[str, tk.PhotoImage] = {}
        self._version_root = pathlib.Path("data/versions")
        self._current_source_version = ""
        self._current_target_version = ""
        self._current_target_blocks: set[str] = set()
        self._pending_mapping: dict[str, dict[str, str]] = {}
        self._pending_output_schem = ""
        self._pending_input_schem = ""
        self._build_style()
        self._build_layout()
        self._preload_local_gradient_maps()

    def _preload_local_gradient_maps(self) -> None:
        """Autonomous local gradient synchronization at GUI startup."""
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
        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"))

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=1)

        header = ttk.Label(self, text="Schemcon — авто-конвертация схем", style="Header.TLabel")
        header.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))

        form = ttk.LabelFrame(self, text="Параметры")
        form.grid(row=1, column=0, sticky="ew", padx=12, pady=6)
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Из версии").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        self.source_version_var = tk.StringVar(value="1.21")
        ttk.Entry(form, textvariable=self.source_version_var, width=16).grid(row=0, column=1, sticky="w", padx=8, pady=6)

        ttk.Label(form, text="В версию").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        self.target_version_var = tk.StringVar(value="1.16.5")
        ttk.Entry(form, textvariable=self.target_version_var, width=16).grid(row=1, column=1, sticky="w", padx=8, pady=6)

        ttk.Label(form, text="Входной .schem").grid(row=2, column=0, sticky="w", padx=8, pady=6)
        self.input_schem_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.input_schem_var).grid(row=2, column=1, sticky="ew", padx=8, pady=6)
        ttk.Button(form, text="Выбрать", command=self._pick_input).grid(row=2, column=2, padx=8, pady=6)

        ttk.Label(form, text="Выходной .schem").grid(row=3, column=0, sticky="w", padx=8, pady=6)
        self.output_schem_var = tk.StringVar(value="converted_output.schem")
        ttk.Entry(form, textvariable=self.output_schem_var).grid(row=3, column=1, sticky="ew", padx=8, pady=6)
        ttk.Button(form, text="Выбрать", command=self._pick_output).grid(row=3, column=2, padx=8, pady=6)

        ttk.Label(form, text="FAWE папка schematics (необязательно)").grid(row=4, column=0, sticky="w", padx=8, pady=6)
        self.fawe_dir_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.fawe_dir_var).grid(row=4, column=1, sticky="ew", padx=8, pady=6)
        ttk.Button(form, text="Выбрать", command=self._pick_fawe_dir).grid(row=4, column=2, padx=8, pady=6)

        ttk.Label(form, text="Имя файла в FAWE").grid(row=5, column=0, sticky="w", padx=8, pady=6)
        self.fawe_name_var = tk.StringVar(value="converted")
        ttk.Entry(form, textvariable=self.fawe_name_var).grid(row=5, column=1, sticky="ew", padx=8, pady=6)

        ttk.Button(
            form,
            text="1) Построить mapping и показать заменяемые блоки",
            style="Primary.TButton",
            command=self._run_auto,
        ).grid(row=6, column=0, columnspan=3, sticky="ew", padx=8, pady=(10, 6))

        ttk.Button(
            form,
            text="2) Подтвердить mapping и конвертировать",
            style="Primary.TButton",
            command=self._apply_mapping,
        ).grid(row=7, column=0, columnspan=3, sticky="ew", padx=8, pady=(0, 8))

        preview = ttk.LabelFrame(self, text="Лог mapping (подсветка замен + ручная правка цели)")
        preview.grid(row=2, column=0, sticky="nsew", padx=12, pady=6)
        preview.columnconfigure(0, weight=1)
        preview.rowconfigure(1, weight=1)

        top_controls = ttk.Frame(preview)
        top_controls.grid(row=0, column=0, sticky="ew", padx=8, pady=6)
        top_controls.columnconfigure(0, weight=1)

        self.filter_var = tk.StringVar()
        filter_entry = ttk.Entry(top_controls, textvariable=self.filter_var)
        filter_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        filter_entry.bind("<KeyRelease>", lambda _e: self._refresh_tree())

        ttk.Button(top_controls, text="Изменить цель", command=self._edit_selected_mapping).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(top_controls, text="Экспорт лога цветов", command=self._export_color_log).grid(row=0, column=2)

        cols = ("source", "target", "reason", "src_props", "dst_props")
        self.tree = ttk.Treeview(preview, columns=cols, show="headings", height=12)
        self.tree.heading("source", text="Исходный")
        self.tree.heading("target", text="Замена")
        self.tree.heading("reason", text="Причина")
        self.tree.heading("src_props", text="Свойства исходного")
        self.tree.heading("dst_props", text="Свойства замены")
        self.tree.column("source", width=220)
        self.tree.column("target", width=220)
        self.tree.column("reason", width=120, anchor="center")
        self.tree.column("src_props", width=250)
        self.tree.column("dst_props", width=250)
        self.tree.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Motion>", self._on_hover)
        self.tree.bind("<Leave>", lambda _e: None)
        self.tree.tag_configure("changed", background="#fff5cc")
        self.tree.tag_configure("same", background="#eaf7ea")

        ybar = ttk.Scrollbar(preview, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ybar.set)
        ybar.grid(row=1, column=1, sticky="ns", padx=(0, 8), pady=8)

        texture = ttk.Frame(preview)
        texture.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
        self.source_canvas = tk.Canvas(texture, width=24, height=24, highlightthickness=1)
        self.source_canvas.grid(row=0, column=0, padx=(0, 6))
        self.source_image = ttk.Label(texture)
        self.source_image.grid(row=0, column=1, padx=(0, 6))
        self.source_txt = ttk.Label(texture, text="Исходный")
        self.source_txt.grid(row=0, column=2, sticky="w", padx=(0, 16))

        self.target_canvas = tk.Canvas(texture, width=24, height=24, highlightthickness=1)
        self.target_canvas.grid(row=0, column=3, padx=(0, 6))
        self.target_image = ttk.Label(texture)
        self.target_image.grid(row=0, column=4, padx=(0, 6))
        self.target_txt = ttk.Label(texture, text="Замена")
        self.target_txt.grid(row=0, column=5, sticky="w")

        log_frame = ttk.LabelFrame(self, text="Системный лог")
        log_frame.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 12))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log = tk.Text(log_frame, height=8, wrap="word", state="disabled")
        self.log.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        self.rowconfigure(2, weight=1)
        self.rowconfigure(3, weight=1)

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

    def _pick_fawe_dir(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.fawe_dir_var.set(path)

    def _log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert(tk.END, text + "\n")
        self.log.configure(state="disabled")
        self.log.see(tk.END)

    def _block_color(self, block_name: str) -> tuple[int, int, int]:
        tr = categorize_block(block_name)
        return tr.color or (120, 120, 120)

    def _props(self, block_name: str) -> str:
        tr = categorize_block(block_name)
        color = tr.color or (120, 120, 120)
        return f"shape={tr.shape}, family={tr.family}, color={color}"

    def _run_auto(self) -> None:
        try:
            source_version = self.source_version_var.get().strip()
            target_version = self.target_version_var.get().strip()
            input_schem = self.input_schem_var.get().strip()
            output_schem = self.output_schem_var.get().strip()
            if not source_version or not target_version:
                raise ValueError("Укажите обе версии.")
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

            gradient_map = self._build_or_load_gradient_map(source_version, target_version, source_blocks, target_blocks)
            self._log(f"3D-градиент цветов загружен: {len(gradient_map)} блоков")

            input_palette = load_schematic(input_schem).palette
            palette_blocks = set(input_palette.keys())

            mapping: dict[str, dict[str, str]] = {}
            for block in sorted(palette_blocks):
                base_block = block.split("[", 1)[0]
                if base_block in target_blocks:
                    mapping[block] = {"target": block, "reason": "exists_in_target"}
                    continue

                res = pick_best_match(block, target_blocks, gradient_map=gradient_map)
                if res.target == "minecraft:air" and "[" in block:
                    base_res = pick_best_match(base_block, target_blocks, gradient_map=gradient_map)
                    if base_res.target != "minecraft:air":
                        res = base_res
                mapping[block] = {"target": res.target, "reason": res.reason}

            mapping_path.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
            self._pending_mapping = mapping
            self._log(f"Mapping сохранён: {mapping_path}")

            self._mapping_rows = []
            for src, meta in sorted(mapping.items()):
                tgt = meta.get("target", "minecraft:air")
                src_color = self._block_color(src)
                tgt_color = self._block_color(tgt)
                changed = src.split("[", 1)[0] != tgt.split("[", 1)[0]
                self._mapping_rows.append(
                    {
                        "source": src,
                        "target": tgt,
                        "reason": meta.get("reason", "mapped"),
                        "src_props": self._props(src),
                        "dst_props": self._props(tgt),
                        "src_color": str(src_color),
                        "dst_color": str(tgt_color),
                        "changed": "1" if changed else "0",
                    }
                )
            self._refresh_tree()
            self._log("Проверьте подсвеченные строки, при необходимости измените цель и нажмите подтверждение конвертации.")
            messagebox.showinfo("Mapping готов", "Проверьте замену блоков в таблице и нажмите 'Подтвердить mapping и конвертировать'.")
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

    def _edit_selected_mapping(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Нет выбора", "Выберите строку mapping для редактирования.")
            return
        values = self.tree.item(selected[0], "values")
        if not values:
            return
        source_block = values[0]
        current_target = values[1]

        new_target = simpledialog.askstring(
            "Изменение замены",
            "Введите целевой блок (например minecraft:red_wool):",
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

        base_target = new_target.split("[", 1)[0]
        if base_target not in self._current_target_blocks:
            messagebox.showerror("Некорректная цель", f"Блок отсутствует в target версии: {base_target}")
            return

        if source_block not in self._pending_mapping:
            self._pending_mapping[source_block] = {}
        self._pending_mapping[source_block]["target"] = new_target
        self._pending_mapping[source_block]["reason"] = "manual_override"

        for row in self._mapping_rows:
            if row["source"] != source_block:
                continue
            row["target"] = new_target
            row["reason"] = "manual_override"
            row["dst_props"] = self._props(new_target)
            row["dst_color"] = str(self._block_color(new_target))
            row["changed"] = "1" if source_block.split("[", 1)[0] != new_target.split("[", 1)[0] else "0"
            break

        self._refresh_tree()
        self._log(f"Manual override: {source_block} -> {new_target}")

    def _export_color_log(self) -> None:
        if not self._mapping_rows:
            messagebox.showwarning("Пусто", "Сначала постройте mapping.")
            return

        lines = ["source_block\tsource_color\ttarget_block\ttarget_color\treason"]
        for row in self._mapping_rows:
            lines.append(
                "\t".join(
                    [
                        row["source"],
                        row.get("src_color", ""),
                        row["target"],
                        row.get("dst_color", ""),
                        row["reason"],
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

    def _refresh_tree(self) -> None:
        query = self.filter_var.get().strip().lower()
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in self._mapping_rows:
            if query and query not in row["source"].lower() and query not in row["target"].lower():
                continue
            tag = "changed" if row.get("changed") == "1" else "same"
            self.tree.insert(
                "",
                tk.END,
                values=(
                    row["source"],
                    row["target"],
                    row["reason"],
                    row["src_props"],
                    row["dst_props"],
                ),
                tags=(tag,),
            )

    def _update_preview(self, src: str, tgt: str) -> None:
        self.source_txt.configure(text=src)
        self.target_txt.configure(text=tgt)
        self._draw_preview(self.source_canvas, self.source_image, src, self._current_source_version, "source")
        self._draw_preview(self.target_canvas, self.target_image, tgt, self._current_target_version, "target")

    def _on_select(self, _event: tk.Event) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        vals = self.tree.item(selected[0], "values")
        if not vals:
            return
        self._update_preview(vals[0], vals[1])

    def _on_hover(self, event: tk.Event) -> None:
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        vals = self.tree.item(row_id, "values")
        if not vals:
            return
        self._update_preview(vals[0], vals[1])

    def _draw_preview(
        self,
        canvas: tk.Canvas,
        image_label: ttk.Label,
        block_name: str,
        version: str,
        slot: str,
    ) -> None:
        texture_file = self._find_texture_file(version, block_name)
        if texture_file is not None:
            img = tk.PhotoImage(file=str(texture_file))
            self._photo_refs[slot] = img
            image_label.configure(image=img)
            canvas.delete("all")
            return

        image_label.configure(image="")
        color = self._block_color(block_name)
        c = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
        canvas.delete("all")
        canvas.create_rectangle(2, 2, 22, 22, fill=c, outline="#222")
        canvas.create_line(2, 2, 22, 22, fill="#000")
        canvas.create_line(22, 2, 2, 22, fill="#fff")

    def _find_texture_file(self, version: str, block_name: str) -> pathlib.Path | None:
        if not version:
            return None

        version_dir = self._version_root / version
        client_jar = version_dir / f"{version}.client.jar"
        if not client_jar.exists():
            return None

        names = self._texture_index.get(version)
        if names is None:
            try:
                with zipfile.ZipFile(client_jar) as jar:
                    names = set(jar.namelist())
                self._texture_index[version] = names
            except Exception:
                return None

        base = block_name.split("[", 1)[0]
        if ":" in base:
            base = base.split(":", 1)[1]
        candidates = [base, f"{base}_side", f"{base}_front", f"{base}_top"]

        texture_member = None
        for candidate in candidates:
            path = f"assets/minecraft/textures/block/{candidate}.png"
            if path in names:
                texture_member = path
                break

        if texture_member is None:
            return None

        cache_dir = pathlib.Path("data/texture_cache") / version
        cache_dir.mkdir(parents=True, exist_ok=True)
        target_file = cache_dir / pathlib.Path(texture_member).name
        if target_file.exists():
            return target_file

        try:
            with zipfile.ZipFile(client_jar) as jar:
                target_file.write_bytes(jar.read(texture_member))
            return target_file
        except Exception:
            return None


def launch_gui() -> None:
    root = tk.Tk()
    root.title("Schemcon")
    root.geometry("1300x900")
    SchemconApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
