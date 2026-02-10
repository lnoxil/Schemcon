from __future__ import annotations

import json
import pathlib
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .categories import categorize_block
from .convert import convert_schematic
from .matcher import pick_best_match
from .registry import (
    download_server_jar,
    ensure_registry_reports,
    fetch_version_json,
    fetch_version_manifest,
    load_registry,
    resolve_version_info,
)


class SchemconApp(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master)
        self.pack(fill=tk.BOTH, expand=True)
        self._mapping_rows: list[dict[str, str]] = []
        self._build_style()
        self._build_layout()

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

        ttk.Button(
            form,
            text="Авто: скачать реестры → построить mapping → конвертировать",
            style="Primary.TButton",
            command=self._run_auto,
        ).grid(row=4, column=0, columnspan=3, sticky="ew", padx=8, pady=(10, 8))

        preview = ttk.LabelFrame(self, text="Лог mapping (фактически использованные блоки из схемы)")
        preview.grid(row=2, column=0, sticky="nsew", padx=12, pady=6)
        preview.columnconfigure(0, weight=1)
        preview.rowconfigure(1, weight=1)

        self.filter_var = tk.StringVar()
        filter_entry = ttk.Entry(preview, textvariable=self.filter_var)
        filter_entry.grid(row=0, column=0, sticky="ew", padx=8, pady=6)
        filter_entry.bind("<KeyRelease>", lambda _e: self._refresh_tree())

        cols = ("source", "target", "reason", "src_props", "dst_props")
        self.tree = ttk.Treeview(preview, columns=cols, show="headings", height=12)
        self.tree.heading("source", text="Исходный")
        self.tree.heading("target", text="Замена")
        self.tree.heading("reason", text="Причина")
        self.tree.heading("src_props", text="Свойства исходного")
        self.tree.heading("dst_props", text="Свойства замены")
        self.tree.column("source", width=220)
        self.tree.column("target", width=220)
        self.tree.column("reason", width=90, anchor="center")
        self.tree.column("src_props", width=230)
        self.tree.column("dst_props", width=230)
        self.tree.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        ybar = ttk.Scrollbar(preview, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ybar.set)
        ybar.grid(row=1, column=1, sticky="ns", padx=(0, 8), pady=8)

        swatch = ttk.Frame(preview)
        swatch.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
        self.source_canvas = tk.Canvas(swatch, width=24, height=24, highlightthickness=1)
        self.source_canvas.grid(row=0, column=0, padx=(0, 6))
        self.source_txt = ttk.Label(swatch, text="Исходный")
        self.source_txt.grid(row=0, column=1, sticky="w", padx=(0, 16))
        self.target_canvas = tk.Canvas(swatch, width=24, height=24, highlightthickness=1)
        self.target_canvas.grid(row=0, column=2, padx=(0, 6))
        self.target_txt = ttk.Label(swatch, text="Замена")
        self.target_txt.grid(row=0, column=3, sticky="w")

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

    def _log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert(tk.END, text + "\n")
        self.log.configure(state="disabled")
        self.log.see(tk.END)

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

            self._log(f"Старт: {source_version} -> {target_version}")
            version_root = pathlib.Path("data/versions")
            mapping_root = pathlib.Path("data/mappings")
            mapping_root.mkdir(parents=True, exist_ok=True)
            mapping_path = mapping_root / f"{source_version}-to-{target_version}.json"

            manifest = fetch_version_manifest()
            self._prepare_version_registry(source_version, manifest, version_root)
            self._prepare_version_registry(target_version, manifest, version_root)

            source_registry = load_registry(version_root / source_version)
            target_registry = load_registry(version_root / target_version)
            target_blocks = set(target_registry.keys())

            mapping: dict[str, dict[str, str]] = {}
            for block in sorted(source_registry.keys()):
                res = pick_best_match(block, target_blocks)
                mapping[block] = {"target": res.target, "reason": res.reason}

            mapping_path.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
            self._log(f"Mapping сохранён: {mapping_path}")

            flat_mapping = {k: v["target"] for k, v in mapping.items()}
            report = convert_schematic(input_schem, output_schem, flat_mapping)
            report_path = pathlib.Path(output_schem).with_suffix(".report.json")
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            self._log(f"Схема конвертирована: {output_schem}")
            self._log(f"Отчёт: {report_path}")

            palette_mapping = report.get("palette_mapping", [])
            self._mapping_rows = []
            for row in palette_mapping:
                src = row["source"]
                tgt = row["target"]
                base_src = src.split("[", 1)[0]
                reason = mapping.get(src, {}).get("reason") if isinstance(mapping.get(src), dict) else None
                if reason is None:
                    reason = mapping.get(base_src, {}).get("reason") if isinstance(mapping.get(base_src), dict) else "used"
                self._mapping_rows.append(
                    {
                        "source": src,
                        "target": tgt,
                        "reason": reason,
                        "src_props": self._props(src),
                        "dst_props": self._props(tgt),
                    }
                )
            self._refresh_tree()
            messagebox.showinfo("Готово", "Конвертация успешно завершена.")
        except Exception as exc:  # noqa: BLE001
            self._log(f"Ошибка: {exc}")
            messagebox.showerror("Ошибка", str(exc))

    def _prepare_version_registry(self, version: str, manifest: dict, version_root: pathlib.Path) -> None:
        version_dir = version_root / version
        blocks_path = version_dir / "blocks.json"
        if blocks_path.exists():
            self._log(f"Реестр уже есть: {version_dir}")
            return

        info = resolve_version_info(version, manifest)
        version_json = fetch_version_json(info)
        jar_path = version_dir / f"{version}.jar"
        download_server_jar(version_json, jar_path)
        _paths, source = ensure_registry_reports(version, jar_path, version_dir, version_json=version_json)
        self._log(f"Реестр {version} подготовлен (source={source})")

    def _refresh_tree(self) -> None:
        query = self.filter_var.get().strip().lower()
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in self._mapping_rows:
            if query and query not in row["source"].lower() and query not in row["target"].lower():
                continue
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
            )

    def _on_select(self, _event: tk.Event) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        vals = self.tree.item(selected[0], "values")
        if not vals:
            return
        src, tgt = vals[0], vals[1]
        self.source_txt.configure(text=src)
        self.target_txt.configure(text=tgt)
        self._draw_preview(self.source_canvas, src)
        self._draw_preview(self.target_canvas, tgt)

    def _draw_preview(self, canvas: tk.Canvas, block_name: str) -> None:
        tr = categorize_block(block_name)
        color = tr.color or (120, 120, 120)
        c = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
        canvas.delete("all")
        canvas.create_rectangle(2, 2, 22, 22, fill=c, outline="#222")
        canvas.create_line(2, 2, 22, 22, fill="#000")
        canvas.create_line(22, 2, 2, 22, fill="#fff")


def launch_gui() -> None:
    root = tk.Tk()
    root.title("Schemcon")
    root.geometry("1200x860")
    SchemconApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
