#!/usr/bin/env python3
# ============================================================================
# App Analyzer Installer — GUI (Tkinter)
# ============================================================================

import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import threading
import os
import re
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Colori & stile
# ---------------------------------------------------------------------------
C_BG        = "#ffffd2"   # sfondo finestra
C_BORDER    = "#640e0e"   # bordo esterno
C_TITLE     = "#640e0e"   # titolo "Analyzer Installer"
C_SEP       = "#640e0e"   # linee orizzontali
C_TEXT      = "#0303a6"   # testo normale
C_BTN_BG    = "#0303a6"   # sfondo pulsanti
C_BTN_FG    = "#ffffd2"   # testo pulsanti
C_WARN      = "#000000"   # avvertimento piccolo
C_ENTRY_BG  = "#0d0aaa"   # sfondo entry/campo
C_ENTRY_FG  = "#eaff00"   # testo entry

FONT_TITLE  = ("DejaVu Sans", 16, "bold")
FONT_NORMAL = ("DejaVu Sans", 12)
FONT_WARN   = ("DejaVu Sans", 8)
FONT_BTN    = ("DejaVu Sans", 11, "bold")

BORDER_PX   = 5
RADIUS      = 12   # angoli arrotondati (canvas trick)

# ---------------------------------------------------------------------------
# Logica bash (APT cleaning — stessa euristica dello script originale)
# ---------------------------------------------------------------------------
DANGER_REGEX = [
    r'^linux-(image|headers|modules|modules-extra|firmware|tools|cloud-tools|source|kbuild|signatures)',
    r'^linux-(generic|virtual|oem|aws|azure|gcp|oracle|raspi|lowlatency|rt|hwe)(-|$)',
    r'^linux-[0-9]',
    r'^nvidia-kernel-',
    r'^dkms$',
    r'^initramfs-tools',
    r'^grub-',
    r'^shim-',
]
SAFE_REMOVE_REGEX = [
    r'^lib.+',
    r'.+-dev$',
    r'.+-dbg$',
    r'.+-dbgsym$',
    r'^gir1\.2-',
    r'^fonts-',
    r'^locale-',
    r'^language-pack',
    r'^(man-db|manpages.*)$',
    r'^(gcc.*|g\+\+.*|make|cmake)$',
    r'^python3-',
    r'^(perl.*|ruby.*|nodejs|npm)$',
]
_DANGER  = [re.compile(r) for r in DANGER_REGEX]
_SAFE_RM = [re.compile(r) for r in SAFE_REMOVE_REGEX]

def apt_should_remove(pkg):
    for pat in _DANGER + _SAFE_RM:
        if pat.search(pkg):
            return True
    return False

def run(cmd, **kw):
    """Esegue un comando e ritorna (stdout, stderr, returncode)."""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)
    return r.stdout.strip(), r.stderr.strip(), r.returncode

def collect_apt_clean_manual():
    """Pacchetti APT: manuali e installati, filtrati."""
    installed_out, _, _ = run(
        "dpkg-query -W -f='${db:Status-Abbrev}\\t${binary:Package}\\n' 2>/dev/null "
        "| awk '$1 ~ /^ii/ {print $2}' | sort -u"
    )
    installed = set(installed_out.splitlines())
    manual_out, _, _ = run("apt-mark showmanual 2>/dev/null | sort -u")
    manual = set(manual_out.splitlines())
    pkgs = sorted(manual & installed)
    cleaned = [p for p in pkgs if not apt_should_remove(p)]
    return cleaned

def collect_flatpak():
    if not shutil.which("flatpak"):
        return []
    out, _, _ = run("flatpak list --app --columns=application 2>/dev/null")
    return sorted([l for l in out.splitlines() if l.strip()])

def collect_snap():
    if not shutil.which("snap"):
        return []
    out, _, _ = run("snap list 2>/dev/null | awk 'NR>1 {print $1}' | sort -u")
    return sorted([l for l in out.splitlines() if l.strip()])

def save_combined(dest_dir):
    """Analizza, pulisce e salva apps-DATA_ORA.manifest + flatpak-DATA_ORA."""
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    apt_pkgs  = collect_apt_clean_manual()
    fp_apps   = collect_flatpak()
    sn_apps   = collect_snap()

    # --- manifest unificato ---
    manifest_path = os.path.join(dest_dir, f"apps-{ts}.manifest")
    with open(manifest_path, "w") as f:
        f.write(f"# App Analyzer Installer manifest\n")
        f.write(f"# created: {datetime.now().isoformat()}\n")
        f.write(f"# host: {os.uname().nodename}\n\n")
        f.write("[APT]\n")
        f.write("\n".join(apt_pkgs) + "\n\n")
        f.write("[FLATPAK]\n")
        f.write("\n".join(fp_apps) + "\n\n")
        f.write("[SNAP]\n")
        f.write("\n".join(sn_apps) + "\n")

    # --- file flatpak separato ---
    flatpak_path = os.path.join(dest_dir, f"flatpak-{ts}")
    with open(flatpak_path, "w") as f:
        f.write(f"# App Analyzer Installer - Lista Flatpak\n")
        f.write(f"# created: {datetime.now().isoformat()}\n")
        f.write(f"# host: {os.uname().nodename}\n\n")
        f.write("\n".join(fp_apps) + "\n")

    return manifest_path, flatpak_path, len(apt_pkgs), len(fp_apps), len(sn_apps)


def load_manifest(path):
    """Legge un .manifest e ritorna dict {apt, flatpak, snap} di liste."""
    result = {"apt": [], "flatpak": [], "snap": []}
    sec = None
    with open(path) as f:
        for line in f:
            line = line.rstrip()
            if line.startswith("#") or not line:
                continue
            if line == "[APT]":     sec = "apt";     continue
            if line == "[FLATPAK]": sec = "flatpak"; continue
            if line == "[SNAP]":    sec = "snap";    continue
            if line.startswith("["):sec = None;      continue
            if sec:
                result[sec].append(line.strip())
    return result

def load_flatpak_file(path):
    """Legge un file flatpak-* (una app per riga, # = commento)."""
    apps = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                apps.append(line)
    return apps


# ---------------------------------------------------------------------------
# Finestra di log (terminale interno)
# ---------------------------------------------------------------------------
class LogWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Log — App Analyzer Installer")
        self.configure(bg=C_BG)
        self.geometry("700x400")
        self.resizable(True, True)

        self._text = tk.Text(
            self, bg="#000", fg="#00ff88",
            font=("Monospace", 9), wrap="word",
            state="disabled", relief="flat", bd=0
        )
        sb = tk.Scrollbar(self, command=self._text.yview, bg=C_BG)
        self._text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._text.pack(fill="both", expand=True, padx=6, pady=6)

    def append(self, line):
        self._text.configure(state="normal")
        self._text.insert("end", line + "\n")
        self._text.see("end")
        self._text.configure(state="disabled")
        self.update_idletasks()


# ---------------------------------------------------------------------------
# Widget helpers
# ---------------------------------------------------------------------------
def sep(parent):
    c = tk.Canvas(parent, height=2, bg=C_BG, highlightthickness=0)
    c.pack(fill="x", padx=10, pady=4)
    c.bind("<Configure>", lambda e: (
        c.delete("all"),
        c.create_line(0, 1, e.width, 1, fill=C_SEP, width=2)
    ))
    return c

def label(parent, text, font=FONT_NORMAL, color=C_TEXT, **kw):
    return tk.Label(parent, text=text, bg=C_BG, fg=color, font=font, **kw)

def btn(parent, text, cmd, state="normal"):
    b = tk.Button(
        parent, text=text, command=cmd,
        bg=C_BTN_BG, fg=C_BTN_FG, font=FONT_BTN,
        relief="flat", bd=0, cursor="hand2",
        padx=12, pady=4,
        activebackground=C_BORDER, activeforeground=C_BTN_FG,
        state=state,
        disabledforeground="#aaaaaa"
    )
    return b

def entry_with_browse(parent, var, browse_fn, placeholder=""):
    frame = tk.Frame(parent, bg=C_BG)
    e = tk.Entry(
        frame, textvariable=var,
        bg=C_ENTRY_BG, fg=C_ENTRY_FG,
        insertbackground=C_TEXT,
        font=FONT_NORMAL, relief="flat", bd=2,
        width=32
    )
    e.pack(side="left", padx=(0, 4))
    b = tk.Button(
        frame, text="📂", command=browse_fn,
        bg=C_BTN_BG, fg=C_BTN_FG, font=("DejaVu Sans", 10),
        relief="flat", bd=0, cursor="hand2", padx=6
    )
    b.pack(side="left")
    return frame

# ---------------------------------------------------------------------------
# App principale
# ---------------------------------------------------------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Analyzer Installer")
        self.resizable(False, False)
        self.configure(bg=C_BORDER)   # bordo color oro

        # ---- variabili ----
        self.save_dir   = tk.StringVar()
        self.apt_file   = tk.StringVar()
        self.fp_file    = tk.StringVar()
        self._btn_avvia = None
        self._btn_inst  = None

        self._build_ui()
        self._center()
        self.save_dir.trace_add("write", self._on_save_dir_change)
        self.apt_file.trace_add("write",  self._on_install_files_change)
        self.fp_file.trace_add("write",   self._on_install_files_change)

    # ------------------------------------------------------------------
    def _build_ui(self):
        # Padding interno = bordo arrotondato simulato
        outer = tk.Frame(self, bg=C_BORDER, padx=BORDER_PX, pady=BORDER_PX)
        outer.pack(fill="both", expand=True)

        inner = tk.Frame(outer, bg=C_BG, padx=16, pady=12)
        inner.pack(fill="both", expand=True)

        # ---- TITOLO ----
        label(inner, "Analyzer Installer", font=FONT_TITLE, color=C_TITLE).pack(pady=(6, 4))
        sep(inner)

        # ---- SEZIONE SALVATAGGIO ----
        row_dest = tk.Frame(inner, bg=C_BG)
        row_dest.pack(fill="x", pady=(6, 2))
        label(row_dest, "Dove vuoi salvare?").pack(side="left", padx=(0, 8))

        dir_frame = entry_with_browse(row_dest, self.save_dir, self._browse_dest)
        dir_frame.pack(side="left")

        self._btn_avvia = btn(inner, "Avvia ricerca", self._do_save, state="disabled")
        self._btn_avvia.pack(pady=(8, 6))

        sep(inner)

        # ---- SEZIONE INSTALLAZIONE ----
        row_apt = tk.Frame(inner, bg=C_BG)
        row_apt.pack(fill="x", pady=(6, 2))
        label(row_apt, "Vuoi installare le App da file?").pack(side="left", padx=(0, 8))
        entry_with_browse(row_apt, self.apt_file, self._browse_apt).pack(side="left")

        row_fp = tk.Frame(inner, bg=C_BG)
        row_fp.pack(fill="x", pady=(2, 6))
        label(row_fp, "Vuoi installare le Flatpak?       ").pack(side="left", padx=(0, 8))
        entry_with_browse(row_fp, self.fp_file, self._browse_fp).pack(side="left")

        self._btn_inst = btn(inner, "Avvia installazione", self._do_install, state="disabled")
        self._btn_inst.pack(pady=(6, 6))

        sep(inner)

        # ---- AVVERTIMENTO ----
        warn = (
            "⚠  Il processo potrebbe durare diversi minuti. Non chiudere questa finestra, "
            "non interrompere il terminale di log e non spegnere il computer durante "
            "l'installazione. Operazioni interrotte potrebbero lasciare il sistema in uno "
            "stato inconsistente."
        )
        label(inner, warn, font=FONT_WARN, color=C_WARN, wraplength=420, justify="center").pack(pady=(2, 6))

    # ------------------------------------------------------------------
    def _center(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")

    # ------------------------------------------------------------------
    # Browse callbacks
    # ------------------------------------------------------------------
    def _browse_dest(self):
        d = filedialog.askdirectory(
            title="Scegli (o crea) la cartella di destinazione",
            mustexist=False
        )
        if d:
            Path(d).mkdir(parents=True, exist_ok=True)
            self.save_dir.set(d)

    def _browse_apt(self):
        f = filedialog.askopenfilename(
            title="Seleziona file manifest App (.manifest)",
            filetypes=[("Manifest", "*.manifest"), ("Tutti", "*")]
        )
        if f:
            self.apt_file.set(f)

    def _browse_fp(self):
        f = filedialog.askopenfilename(
            title="Seleziona file lista Flatpak",
            filetypes=[("Flatpak list", "flatpak-*"), ("Tutti", "*")]
        )
        if f:
            self.fp_file.set(f)

    # ------------------------------------------------------------------
    # Trace callbacks → abilita/disabilita pulsanti
    # ------------------------------------------------------------------
    def _on_save_dir_change(self, *_):
        state = "normal" if self.save_dir.get().strip() else "disabled"
        if self._btn_avvia:
            self._btn_avvia.configure(state=state)

    def _on_install_files_change(self, *_):
        has = self.apt_file.get().strip() or self.fp_file.get().strip()
        state = "normal" if has else "disabled"
        if self._btn_inst:
            self._btn_inst.configure(state=state)

    # ------------------------------------------------------------------
    # AZIONE: Salva
    # ------------------------------------------------------------------
    def _do_save(self):
        dest = self.save_dir.get().strip()
        if not dest:
            return

        self._btn_avvia.configure(state="disabled", text="Analisi in corso…")
        log_win = LogWindow(self)
        log_win.append("=== Avvio analisi ===")
        log_win.append(f"Destinazione: {dest}")

        def worker():
            try:
                log_win.append("Raccolta pacchetti APT (manuale + pulizia)…")
                m, f, na, nf, ns = save_combined(dest)
                log_win.append(f"APT:     {na} pacchetti")
                log_win.append(f"Flatpak: {nf} app")
                log_win.append(f"Snap:    {ns} app")
                log_win.append(f"Manifest: {m}")
                log_win.append(f"Flatpak:  {f}")
                log_win.append("=== Completato ===")
                self.after(0, lambda: messagebox.showinfo(
                    "Completato",
                    f"File salvati in:\n{dest}\n\n"
                    f"apps-*.manifest  →  APT ({na}), Flatpak ({nf}), Snap ({ns})\n"
                    f"flatpak-*         →  Flatpak ({nf})"
                ))
            except Exception as e:
                log_win.append(f"ERRORE: {e}")
                self.after(0, lambda: messagebox.showerror("Errore", str(e)))
            finally:
                self.after(0, lambda: self._btn_avvia.configure(
                    state="normal", text="Avvia ricerca"
                ))

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # AZIONE: Installa
    # ------------------------------------------------------------------
    def _do_install(self):
        apt_f = self.apt_file.get().strip()
        fp_f  = self.fp_file.get().strip()

        if not apt_f and not fp_f:
            return

        log_win = LogWindow(self)
        log_win.append("=== Avvio installazione ===")
        self._btn_inst.configure(state="disabled", text="Installazione…")

        def worker():
            try:
                # --- Installa APT (dal manifest) ---
                if apt_f:
                    try:
                        data   = load_manifest(apt_f)
                        pkgs   = data["apt"]
                        fp_man = data["flatpak"]
                        sn_man = data["snap"]
                    except Exception:
                        pkgs = fp_man = sn_man = []
                        log_win.append(f"[WARN] Impossibile leggere manifest APT: {apt_f}")

                    if pkgs:
                        log_win.append(f"APT: installo {len(pkgs)} pacchetti (uno alla volta)…")
                        self._run_log("sudo apt update", log_win)
                        log_win.append("APT: aggiornamento sistema in corso…")
                        self._run_log("sudo apt upgrade -y", log_win)
                        # Assicura flatpak installato se ci sono app flatpak nel manifest
                        if fp_man and not shutil.which("flatpak"):
                            log_win.append("APT: installo flatpak (richiesto dal manifest)…")
                            self._run_log("sudo apt install -y flatpak", log_win)
                        skipped = []
                        for i, pkg in enumerate(pkgs, 1):
                            log_win.append(f"  [{i}/{len(pkgs)}] {pkg}")
                            ok = self._run_log_tolerant(f"sudo apt install -y {pkg}", log_win)
                            if not ok:
                                skipped.append(pkg)
                        if skipped:
                            log_win.append(f"[SKIP APT] Non installati ({len(skipped)}): {', '.join(skipped)}")

                    # Flatpak dal manifest
                    if fp_man:
                        log_win.append(f"Flatpak (manifest): installo {len(fp_man)} app (una alla volta)…")
                        self._run_log(
                            "flatpak remote-add --if-not-exists flathub "
                            "https://flathub.org/repo/flathub.flatpakrepo", log_win
                        )
                        skipped = []
                        for i, app in enumerate(fp_man, 1):
                            log_win.append(f"  [{i}/{len(fp_man)}] {app}")
                            ok = self._run_log_tolerant(f"flatpak install -y flathub {app}", log_win)
                            if not ok:
                                skipped.append(app)
                        if skipped:
                            log_win.append(f"[SKIP Flatpak] Non installate ({len(skipped)}): {', '.join(skipped)}")

                    # Snap dal manifest
                    if sn_man:
                        log_win.append(f"Snap (manifest): installo {len(sn_man)} app (una alla volta)…")
                        skipped = []
                        for i, app in enumerate(sn_man, 1):
                            log_win.append(f"  [{i}/{len(sn_man)}] {app}")
                            ok = self._run_log_tolerant(f"sudo snap install {app}", log_win)
                            if not ok:
                                skipped.append(app)
                        if skipped:
                            log_win.append(f"[SKIP Snap] Non installate ({len(skipped)}): {', '.join(skipped)}")

                # --- Installa Flatpak (da file dedicato) ---
                if fp_f:
                    apps = load_flatpak_file(fp_f)
                    if apps:
                        log_win.append(f"Flatpak: installo {len(apps)} app da {fp_f} (una alla volta)…")
                        if not shutil.which("flatpak"):
                            log_win.append("Flatpak non trovato: lo installo via APT…")
                            self._run_log("sudo apt install -y flatpak", log_win)
                        self._run_log(
                            "flatpak remote-add --if-not-exists flathub "
                            "https://flathub.org/repo/flathub.flatpakrepo", log_win
                        )
                        skipped = []
                        for i, app in enumerate(apps, 1):
                            log_win.append(f"  [{i}/{len(apps)}] {app}")
                            ok = self._run_log_tolerant(f"flatpak install -y flathub {app}", log_win)
                            if not ok:
                                skipped.append(app)
                        if skipped:
                            log_win.append(f"[SKIP Flatpak] Non installate ({len(skipped)}): {', '.join(skipped)}")

                log_win.append("=== Installazione completata ===")
                self.after(0, lambda: messagebox.showinfo("Completato", "Installazione completata!"))

            except Exception as e:
                log_win.append(f"ERRORE: {e}")
                self.after(0, lambda: messagebox.showerror("Errore", str(e)))
            finally:
                self.after(0, lambda: self._btn_inst.configure(
                    state="normal", text="Avvia installazione"
                ))

        threading.Thread(target=worker, daemon=True).start()

    def _run_log(self, cmd, log_win):
        """Esegue cmd loggando l'output; lancia eccezione se fallisce."""
        log_win.append(f"$ {cmd}")
        proc = subprocess.Popen(
            cmd, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1
        )
        for line in proc.stdout:
            log_win.append(line.rstrip())
        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"Comando fallito (exit {proc.returncode}): {cmd}")

    def _run_log_tolerant(self, cmd, log_win):
        """Esegue cmd loggando l'output; in caso di errore logga [WARN] e ritorna False."""
        proc = subprocess.Popen(
            cmd, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1
        )
        for line in proc.stdout:
            log_win.append("    " + line.rstrip())
        proc.wait()
        if proc.returncode != 0:
            log_win.append(f"    [WARN] Fallito (exit {proc.returncode}), salto e continuo.")
            return False
        return True


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = App()
    app.mainloop()
