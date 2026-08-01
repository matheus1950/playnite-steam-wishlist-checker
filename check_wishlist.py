import os
import re
import json
import time
import queue
import threading
import webbrowser
import subprocess
from pathlib import Path
from datetime import datetime
from tkinter import ttk, messagebox

import customtkinter as ctk
import requests
from rapidfuzz import process, fuzz


# ============================================================
# APLICATIVO
# ============================================================

APP_NAME = "Steam Wishlist × Playnite"
APP_VERSION = "1.1.0"


# ============================================================
# CONFIGURAÇÕES GERAIS
# ============================================================

FUZZY_SCORE_CUTOFF = 85

IGNORE_STEAM_SOURCE = True

STEAM_APP_REQUEST_DELAY = 0.08


# ============================================================
# CAMINHOS
# ============================================================

APPDATA = Path(
    os.path.expandvars(
        r"%APPDATA%"
    )
)

LOCALAPPDATA = Path(
    os.path.expandvars(
        r"%LOCALAPPDATA%"
    )
)


# ------------------------------------------------------------
# CONFIG DO NOSSO APP
# ------------------------------------------------------------

APP_CONFIG_DIR = (
    APPDATA
    /
    "WishlistSteamCheck"
)

APP_CONFIG_FILE = (
    APP_CONFIG_DIR
    /
    "config.json"
)


# ------------------------------------------------------------
# PLAYNITE
# ------------------------------------------------------------

PLAYNITE_DATA_DIR = (
    APPDATA
    /
    "Playnite"
)

PLAYNITE_EXPORT_FILE = (
    PLAYNITE_DATA_DIR
    /
    "steam_wishlist_checker_library.json"
)

PLAYNITE_PLUGIN_DIR = (
    PLAYNITE_DATA_DIR
    /
    "Extensions"
    /
    "SteamWishlistExporter"
)

PLAYNITE_PLUGIN_DLL = (
    PLAYNITE_PLUGIN_DIR
    /
    "SteamWishlistExporter.dll"
)

PLAYNITE_PLUGIN_MANIFEST = (
    PLAYNITE_PLUGIN_DIR
    /
    "extension.yaml"
)

PLAYNITE_EXE = (
    LOCALAPPDATA
    /
    "Playnite"
    /
    "Playnite.DesktopApp.exe"
)


# ============================================================
# APARÊNCIA
# ============================================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ============================================================
# CONFIGURAÇÃO DO APP
# ============================================================

def load_config():
    """
    Lê configurações persistentes do usuário.
    """

    default_config = {
        "steam_id_64": ""
    }

    if not APP_CONFIG_FILE.exists():
        return default_config

    try:
        with APP_CONFIG_FILE.open(
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if not isinstance(
            data,
            dict
        ):
            return default_config

        return {
            "steam_id_64":
                str(
                    data.get(
                        "steam_id_64",
                        ""
                    )
                    or
                    ""
                ).strip()
        }

    except Exception:
        return default_config


def save_config(config):
    """
    Salva configurações em AppData.
    """

    APP_CONFIG_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    with APP_CONFIG_FILE.open(
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            config,
            f,
            ensure_ascii=False,
            indent=4
        )


# ============================================================
# VALIDAÇÃO DO STEAMID64
# ============================================================

def is_valid_steam_id_64(value):
    """
    Validação básica de SteamID64.

    SteamID64 é um número inteiro normalmente
    com 17 dígitos e começa com 7656119.
    """

    value = str(
        value
    ).strip()

    if not value.isdigit():
        return False

    if len(value) != 17:
        return False

    if not value.startswith(
        "7656119"
    ):
        return False

    return True


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def clean_title(title: str) -> str:
    if not title:
        return ""

    title = title.lower()

    title = (
        title
        .replace("™", "")
        .replace("®", "")
        .replace("©", "")
    )

    title = title.replace(
        "&",
        " and "
    )

    title = re.sub(
        r"[^\w\s]",
        " ",
        title,
        flags=re.UNICODE
    )

    return " ".join(
        title.split()
    )


# ============================================================
# PLAYNITE - PROCESSO
# ============================================================

def is_playnite_running():
    try:
        result = subprocess.run(
            [
                "tasklist",
                "/FI",
                "IMAGENAME eq Playnite.DesktopApp.exe"
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=(
                subprocess.CREATE_NO_WINDOW
                if os.name == "nt"
                else 0
            )
        )

        return (
            "Playnite.DesktopApp.exe"
            in result.stdout
        )

    except Exception:
        return False


# ============================================================
# PLAYNITE - STATUS
# ============================================================

def get_playnite_integration_status():

    playnite_installed = (
        PLAYNITE_EXE.exists()
    )

    plugin_dir_exists = (
        PLAYNITE_PLUGIN_DIR.is_dir()
    )

    plugin_dll_exists = (
        PLAYNITE_PLUGIN_DLL.is_file()
    )

    plugin_manifest_exists = (
        PLAYNITE_PLUGIN_MANIFEST.is_file()
    )

    plugin_installed = (
        plugin_dir_exists
        and
        plugin_dll_exists
        and
        plugin_manifest_exists
    )

    export_exists = (
        PLAYNITE_EXPORT_FILE.is_file()
    )

    export_size = 0
    export_modified = None

    if export_exists:

        try:
            stat = (
                PLAYNITE_EXPORT_FILE.stat()
            )

            export_size = (
                stat.st_size
            )

            export_modified = (
                datetime.fromtimestamp(
                    stat.st_mtime
                )
            )

        except Exception:
            pass

    return {
        "playnite_installed":
            playnite_installed,

        "playnite_running":
            is_playnite_running(),

        "plugin_installed":
            plugin_installed,

        "plugin_dir_exists":
            plugin_dir_exists,

        "plugin_dll_exists":
            plugin_dll_exists,

        "plugin_manifest_exists":
            plugin_manifest_exists,

        "export_exists":
            export_exists,

        "export_size":
            export_size,

        "export_modified":
            export_modified,
    }


# ============================================================
# DATA
# ============================================================

def format_datetime(value):

    if not value:
        return "—"

    return value.strftime(
        "%d/%m/%Y às %H:%M:%S"
    )


def format_age(value):

    if not value:
        return "Nunca"

    delta = (
        datetime.now()
        -
        value
    )

    seconds = max(
        0,
        int(
            delta.total_seconds()
        )
    )

    if seconds < 60:
        return "há menos de 1 minuto"

    minutes = (
        seconds // 60
    )

    if minutes < 60:

        if minutes == 1:
            return "há 1 minuto"

        return (
            f"há {minutes} minutos"
        )

    hours = (
        minutes // 60
    )

    if hours < 24:

        if hours == 1:
            return "há 1 hora"

        return (
            f"há {hours} horas"
        )

    days = (
        hours // 24
    )

    if days == 1:
        return "há 1 dia"

    return (
        f"há {days} dias"
    )


# ============================================================
# PLAYNITE - LEITURA
# ============================================================

def read_playnite_export():

    if not PLAYNITE_EXPORT_FILE.exists():

        raise FileNotFoundError(
            "A biblioteca exportada pelo Playnite "
            "ainda não foi encontrada."
        )

    try:

        with PLAYNITE_EXPORT_FILE.open(
            "r",
            encoding="utf-8-sig"
        ) as f:

            data = json.load(f)

    except json.JSONDecodeError as e:

        raise RuntimeError(
            "O arquivo exportado pelo Playnite "
            "não contém JSON válido.\n\n"
            f"{e}"
        )

    except Exception as e:

        raise RuntimeError(
            "Não foi possível ler a biblioteca "
            "exportada pelo Playnite.\n\n"
            f"{e}"
        )

    if isinstance(
        data,
        dict
    ):
        data = [data]

    if not isinstance(
        data,
        list
    ):

        raise RuntimeError(
            "Formato inesperado na biblioteca "
            "exportada pelo Playnite."
        )

    games = []

    for item in data:

        if not isinstance(
            item,
            dict
        ):
            continue

        name = str(
            item.get(
                "Name",
                ""
            )
            or
            ""
        ).strip()

        if not name:
            continue

        games.append({

            "name":
                name,

            "source":
                str(
                    item.get(
                        "Source",
                        ""
                    )
                    or
                    ""
                ).strip(),

            "plugin_id":
                str(
                    item.get(
                        "PluginId",
                        ""
                    )
                    or
                    ""
                ).strip(),

            "game_id":
                str(
                    item.get(
                        "GameId",
                        ""
                    )
                    or
                    ""
                ).strip(),

            "installed":
                bool(
                    item.get(
                        "IsInstalled",
                        False
                    )
                ),

            "hidden":
                bool(
                    item.get(
                        "Hidden",
                        False
                    )
                ),
        })

    return games


# ============================================================
# PLAYNITE - FONTES
# ============================================================

def get_source_counts(games):

    counts = {}

    for game in games:

        source = (
            game.get(
                "source"
            )
            or
            "Sem fonte"
        )

        counts[source] = (
            counts.get(
                source,
                0
            )
            +
            1
        )

    return counts


def filter_playnite_games(games):

    if not IGNORE_STEAM_SOURCE:
        return games

    filtered = []

    for game in games:

        source = (
            game.get(
                "source"
            )
            or
            ""
        ).strip().lower()

        if source == "steam":
            continue

        filtered.append(
            game
        )

    return filtered


# ============================================================
# STEAM
# ============================================================

def create_steam_session():

    session = (
        requests.Session()
    )

    session.headers.update({

        "User-Agent":
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0.0.0 "
            "Safari/537.36",

        "Accept":
            "application/json,"
            "text/plain,"
            "*/*"
    })

    return session


# ============================================================
# STEAM - WISHLIST
# ============================================================

def get_steam_wishlist_appids(
    steam_id,
    session
):

    url = (
        "https://api.steampowered.com/"
        "IWishlistService/GetWishlist/v1/"
    )

    params = {
        "input_json":
            json.dumps({
                "steamid":
                    steam_id
            })
    }

    response = session.get(
        url,
        params=params,
        timeout=30
    )

    if response.status_code != 200:

        raise RuntimeError(
            "A Steam respondeu com HTTP "
            f"{response.status_code}."
        )

    try:

        data = (
            response.json()
        )

    except requests.exceptions.JSONDecodeError:

        raise RuntimeError(
            "A Steam não retornou JSON válido."
        )

    items = (
        data
        .get(
            "response",
            {}
        )
        .get(
            "items",
            []
        )
    )

    appids = []

    for item in items:

        if not isinstance(
            item,
            dict
        ):
            continue

        appid = (
            item.get(
                "appid"
            )
        )

        if appid is not None:

            appids.append(
                str(appid)
            )

    return list(
        dict.fromkeys(
            appids
        )
    )


# ============================================================
# STEAM - APP DETAILS
# ============================================================

def get_steam_app_name(
    appid,
    session
):

    url = (
        "https://store.steampowered.com/"
        "api/appdetails"
    )

    params = {
        "appids":
            appid,

        "l":
            "english",

        "cc":
            "br"
    }

    try:

        response = session.get(
            url,
            params=params,
            timeout=20
        )

        if (
            response.status_code
            !=
            200
        ):
            return None

        data = (
            response.json()
        )

        app_data = (
            data.get(
                str(appid)
            )
        )

        if not isinstance(
            app_data,
            dict
        ):
            return None

        if not app_data.get(
            "success"
        ):
            return None

        name = (
            app_data
            .get(
                "data",
                {}
            )
            .get(
                "name"
            )
        )

        if isinstance(
            name,
            str
        ):

            return (
                name.strip()
            )

    except Exception:
        pass

    return None


# ============================================================
# COMPARAÇÃO
# ============================================================

def compare_games(
    wishlist,
    playnite_games
):

    normalized_playnite = {}

    for game in playnite_games:

        normalized = (
            clean_title(
                game["name"]
            )
        )

        if not normalized:
            continue

        normalized_playnite.setdefault(
            normalized,
            []
        )

        normalized_playnite[
            normalized
        ].append(
            game
        )

    exact_matches = []
    fuzzy_matches = []

    for (
        wishlist_name,
        appid
    ) in wishlist.items():

        normalized = (
            clean_title(
                wishlist_name
            )
        )

        # ----------------------------------------------------
        # EXATO
        # ----------------------------------------------------

        if (
            normalized
            in
            normalized_playnite
        ):

            for game in (
                normalized_playnite[
                    normalized
                ]
            ):

                exact_matches.append({

                    "wishlist":
                        wishlist_name,

                    "appid":
                        appid,

                    "playnite":
                        game["name"],

                    "source":
                        (
                            game["source"]
                            or
                            "Sem fonte"
                        ),

                    "score":
                        100.0,

                    "type":
                        "Exato"
                })

            continue

        # ----------------------------------------------------
        # FUZZY
        # ----------------------------------------------------

        if not normalized_playnite:
            continue

        match = (
            process.extractOne(
                normalized,
                normalized_playnite.keys(),
                scorer=
                    fuzz.token_sort_ratio,
                score_cutoff=
                    FUZZY_SCORE_CUTOFF
            )
        )

        if not match:
            continue

        matched_key = (
            match[0]
        )

        score = (
            match[1]
        )

        for game in (
            normalized_playnite[
                matched_key
            ]
        ):

            fuzzy_matches.append({

                "wishlist":
                    wishlist_name,

                "appid":
                    appid,

                "playnite":
                    game["name"],

                "source":
                    (
                        game["source"]
                        or
                        "Sem fonte"
                    ),

                "score":
                    score,

                "type":
                    "Aproximado"
            })

    exact_matches.sort(
        key=lambda x:
            x["wishlist"].lower()
    )

    fuzzy_matches.sort(
        key=lambda x: (
            -x["score"],
            x["wishlist"].lower()
        )
    )

    return (
        exact_matches,
        fuzzy_matches
    )


# ============================================================
# GUI
# ============================================================

class WishlistApp(
    ctk.CTk
):

    def __init__(self):

        super().__init__()

        # ----------------------------------------------------
        # CONFIG
        # ----------------------------------------------------

        self.config_data = (
            load_config()
        )

        # ----------------------------------------------------
        # JANELA
        # ----------------------------------------------------

        self.title(
            APP_NAME
        )

        self.geometry(
            "1280x800"
        )

        self.minsize(
            1050,
            650
        )

        # ----------------------------------------------------
        # ESTADO
        # ----------------------------------------------------

        self.event_queue = (
            queue.Queue()
        )

        self.loading = False

        self.playnite_games = []

        self.filtered_playnite_games = []

        self.wishlist = {}

        self.matches = []

        self.source_counts = {}

        self.total_wishlist_appids = 0

        self.failed_steam_names = 0

        self.integration_status = {}

        # ----------------------------------------------------
        # GRID
        # ----------------------------------------------------

        self.grid_columnconfigure(
            0,
            weight=0
        )

        self.grid_columnconfigure(
            1,
            weight=1
        )

        self.grid_rowconfigure(
            0,
            weight=1
        )

        # ----------------------------------------------------
        # GUI
        # ----------------------------------------------------

        self.create_sidebar()

        self.create_main_area()

        self.configure_treeview_style()

        self.after(
            100,
            self.process_event_queue
        )

        self.after(
            300,
            self.initial_load
        )


    # ========================================================
    # SIDEBAR
    # ========================================================

    def create_sidebar(
        self
    ):

        self.sidebar = (
            ctk.CTkFrame(
                self,
                width=240,
                corner_radius=0
            )
        )

        self.sidebar.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        self.sidebar.grid_propagate(
            False
        )

        # ----------------------------------------------------
        # TÍTULO
        # ----------------------------------------------------

        title = (
            ctk.CTkLabel(
                self.sidebar,
                text="Wishlist\nChecker",
                font=ctk.CTkFont(
                    size=27,
                    weight="bold"
                ),
                justify="left"
            )
        )

        title.pack(
            anchor="w",
            padx=25,
            pady=(
                30,
                5
            )
        )

        subtitle = (
            ctk.CTkLabel(
                self.sidebar,
                text="Steam × Playnite",
                font=ctk.CTkFont(
                    size=14
                ),
                text_color="gray70"
            )
        )

        subtitle.pack(
            anchor="w",
            padx=25,
            pady=(
                0,
                5
            )
        )

        version_label = (
            ctk.CTkLabel(
                self.sidebar,
                text=(
                    f"v{APP_VERSION}"
                ),
                font=ctk.CTkFont(
                    size=11
                ),
                text_color="gray55"
            )
        )

        version_label.pack(
            anchor="w",
            padx=25,
            pady=(
                0,
                25
            )
        )

        # ----------------------------------------------------
        # ATUALIZAR
        # ----------------------------------------------------

        self.refresh_button = (
            ctk.CTkButton(
                self.sidebar,
                text="Atualizar dados",
                height=42,
                command=
                    self.start_refresh
            )
        )

        self.refresh_button.pack(
            fill="x",
            padx=20,
            pady=8
        )

        # ----------------------------------------------------
        # CONTA STEAM
        # ----------------------------------------------------

        steam_button = (
            ctk.CTkButton(
                self.sidebar,
                text="Conta Steam",
                height=40,
                fg_color="transparent",
                border_width=1,
                command=
                    self.show_steam_settings
            )
        )

        steam_button.pack(
            fill="x",
            padx=20,
            pady=8
        )

        # ----------------------------------------------------
        # INTEGRAÇÃO
        # ----------------------------------------------------

        integration_button = (
            ctk.CTkButton(
                self.sidebar,
                text="Integração Playnite",
                height=40,
                fg_color="transparent",
                border_width=1,
                command=
                    self.show_integration_info
            )
        )

        integration_button.pack(
            fill="x",
            padx=20,
            pady=8
        )

        separator = (
            ctk.CTkFrame(
                self.sidebar,
                height=1
            )
        )

        separator.pack(
            fill="x",
            padx=20,
            pady=20
        )

        status_title = (
            ctk.CTkLabel(
                self.sidebar,
                text="Status",
                font=ctk.CTkFont(
                    size=15,
                    weight="bold"
                )
            )
        )

        status_title.pack(
            anchor="w",
            padx=25
        )

        # ----------------------------------------------------
        # PLAYNITE
        # ----------------------------------------------------

        self.playnite_status_label = (
            ctk.CTkLabel(
                self.sidebar,
                text="Playnite: verificando...",
                anchor="w",
                justify="left",
                wraplength=190
            )
        )

        self.playnite_status_label.pack(
            fill="x",
            padx=25,
            pady=(
                10,
                2
            )
        )

        # ----------------------------------------------------
        # PLUGIN
        # ----------------------------------------------------

        self.plugin_status_label = (
            ctk.CTkLabel(
                self.sidebar,
                text="Plugin: verificando...",
                anchor="w",
                justify="left",
                wraplength=190
            )
        )

        self.plugin_status_label.pack(
            fill="x",
            padx=25,
            pady=2
        )

        # ----------------------------------------------------
        # BIBLIOTECA
        # ----------------------------------------------------

        self.sync_status_label = (
            ctk.CTkLabel(
                self.sidebar,
                text="Sincronização: verificando...",
                anchor="w",
                justify="left",
                wraplength=190
            )
        )

        self.sync_status_label.pack(
            fill="x",
            padx=25,
            pady=2
        )

        # ----------------------------------------------------
        # STEAM
        # ----------------------------------------------------

        self.steam_status_label = (
            ctk.CTkLabel(
                self.sidebar,
                text="Steam: —",
                anchor="w",
                justify="left",
                wraplength=190
            )
        )

        self.steam_status_label.pack(
            fill="x",
            padx=25,
            pady=(
                15,
                2
            )
        )

        # ----------------------------------------------------
        # JSON
        # ----------------------------------------------------

        self.file_status_label = (
            ctk.CTkLabel(
                self.sidebar,
                text="",
                anchor="w",
                justify="left",
                wraplength=190,
                text_color="gray60",
                font=ctk.CTkFont(
                    size=11
                )
            )
        )

        self.file_status_label.pack(
            fill="x",
            padx=25,
            pady=(
                20,
                0
            )
        )


    # ========================================================
    # CONTEÚDO PRINCIPAL
    # ========================================================

    def create_main_area(
        self
    ):

        self.main_frame = (
            ctk.CTkFrame(
                self,
                corner_radius=0,
                fg_color="transparent"
            )
        )

        self.main_frame.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=25,
            pady=20
        )

        self.main_frame.grid_columnconfigure(
            0,
            weight=1
        )

        self.main_frame.grid_rowconfigure(
            4,
            weight=1
        )

        # ----------------------------------------------------
        # HEADER
        # ----------------------------------------------------

        header = (
            ctk.CTkFrame(
                self.main_frame,
                fg_color="transparent"
            )
        )

        header.grid(
            row=0,
            column=0,
            sticky="ew",
            pady=(
                0,
                18
            )
        )

        title = (
            ctk.CTkLabel(
                header,
                text=(
                    "Jogos da wishlist que "
                    "você já possui"
                ),
                font=ctk.CTkFont(
                    size=26,
                    weight="bold"
                )
            )
        )

        title.pack(
            side="left"
        )

        # ----------------------------------------------------
        # CARDS
        # ----------------------------------------------------

        cards = (
            ctk.CTkFrame(
                self.main_frame,
                fg_color="transparent"
            )
        )

        cards.grid(
            row=1,
            column=0,
            sticky="ew",
            pady=(
                0,
                18
            )
        )

        for col in range(4):

            cards.grid_columnconfigure(
                col,
                weight=1
            )

        self.card_playnite = (
            self.create_card(
                cards,
                0,
                "Playnite",
                "—"
            )
        )

        self.card_wishlist = (
            self.create_card(
                cards,
                1,
                "Wishlist Steam",
                "—"
            )
        )

        self.card_matches = (
            self.create_card(
                cards,
                2,
                "Já possui",
                "—"
            )
        )

        self.card_unresolved = (
            self.create_card(
                cards,
                3,
                "Não identificados",
                "—"
            )
        )

        # ----------------------------------------------------
        # FILTROS
        # ----------------------------------------------------

        filters = (
            ctk.CTkFrame(
                self.main_frame
            )
        )

        filters.grid(
            row=2,
            column=0,
            sticky="ew",
            pady=(
                0,
                12
            )
        )

        filters.grid_columnconfigure(
            0,
            weight=1
        )

        self.search_entry = (
            ctk.CTkEntry(
                filters,
                placeholder_text=
                    "Pesquisar jogo...",
                height=38
            )
        )

        self.search_entry.grid(
            row=0,
            column=0,
            padx=12,
            pady=12,
            sticky="ew"
        )

        self.search_entry.bind(
            "<KeyRelease>",
            lambda event:
                self.apply_filters()
        )

        self.source_filter = (
            ctk.CTkOptionMenu(
                filters,
                values=[
                    "Todas as bibliotecas"
                ],
                command=lambda _:
                    self.apply_filters()
            )
        )

        self.source_filter.grid(
            row=0,
            column=1,
            padx=6,
            pady=12
        )

        self.match_filter = (
            ctk.CTkOptionMenu(
                filters,
                values=[
                    "Todos",
                    "Exato",
                    "Aproximado"
                ],
                command=lambda _:
                    self.apply_filters()
            )
        )

        self.match_filter.grid(
            row=0,
            column=2,
            padx=(
                6,
                12
            ),
            pady=12
        )

        # ----------------------------------------------------
        # CONTAGEM
        # ----------------------------------------------------

        self.result_count_label = (
            ctk.CTkLabel(
                self.main_frame,
                text="Nenhum resultado carregado.",
                text_color="gray70"
            )
        )

        self.result_count_label.grid(
            row=3,
            column=0,
            sticky="w",
            pady=(
                0,
                8
            )
        )

        # ----------------------------------------------------
        # TABELA
        # ----------------------------------------------------

        table_frame = (
            ctk.CTkFrame(
                self.main_frame
            )
        )

        table_frame.grid(
            row=4,
            column=0,
            sticky="nsew"
        )

        table_frame.grid_columnconfigure(
            0,
            weight=1
        )

        table_frame.grid_rowconfigure(
            0,
            weight=1
        )

        columns = (
            "wishlist",
            "playnite",
            "source",
            "type",
            "score"
        )

        self.tree = (
            ttk.Treeview(
                table_frame,
                columns=columns,
                show="headings",
                selectmode="browse"
            )
        )

        self.tree.heading(
            "wishlist",
            text="Steam Wishlist"
        )

        self.tree.heading(
            "playnite",
            text="No Playnite"
        )

        self.tree.heading(
            "source",
            text="Biblioteca"
        )

        self.tree.heading(
            "type",
            text="Match"
        )

        self.tree.heading(
            "score",
            text="Similaridade"
        )

        self.tree.column(
            "wishlist",
            width=270,
            minwidth=180
        )

        self.tree.column(
            "playnite",
            width=270,
            minwidth=180
        )

        self.tree.column(
            "source",
            width=130,
            minwidth=90
        )

        self.tree.column(
            "type",
            width=110,
            minwidth=80
        )

        self.tree.column(
            "score",
            width=100,
            minwidth=90,
            anchor="center"
        )

        scrollbar = (
            ttk.Scrollbar(
                table_frame,
                orient="vertical",
                command=
                    self.tree.yview
            )
        )

        self.tree.configure(
            yscrollcommand=
                scrollbar.set
        )

        self.tree.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=10,
            pady=10
        )

        scrollbar.grid(
            row=0,
            column=1,
            sticky="ns",
            pady=10,
            padx=(
                0,
                10
            )
        )

        self.tree.bind(
            "<Double-1>",
            self.open_selected_steam_page
        )

        # ----------------------------------------------------
        # FOOTER
        # ----------------------------------------------------

        footer = (
            ctk.CTkFrame(
                self.main_frame,
                fg_color="transparent"
            )
        )

        footer.grid(
            row=5,
            column=0,
            sticky="ew",
            pady=(
                12,
                0
            )
        )

        footer.grid_columnconfigure(
            0,
            weight=1
        )

        self.status_label = (
            ctk.CTkLabel(
                footer,
                text="Pronto.",
                anchor="w"
            )
        )

        self.status_label.grid(
            row=0,
            column=0,
            sticky="ew"
        )

        self.progress_bar = (
            ctk.CTkProgressBar(
                footer,
                width=250
            )
        )

        self.progress_bar.grid(
            row=0,
            column=1,
            padx=(
                20,
                0
            )
        )

        self.progress_bar.set(
            0
        )


    # ========================================================
    # CARD
    # ========================================================

    def create_card(
        self,
        parent,
        column,
        title,
        value
    ):

        frame = (
            ctk.CTkFrame(
                parent
            )
        )

        frame.grid(
            row=0,
            column=column,
            sticky="ew",
            padx=(
                0
                if column == 0
                else 6,

                0
                if column == 3
                else 6
            )
        )

        title_label = (
            ctk.CTkLabel(
                frame,
                text=title,
                text_color="gray70",
                font=ctk.CTkFont(
                    size=13
                )
            )
        )

        title_label.pack(
            anchor="w",
            padx=18,
            pady=(
                15,
                2
            )
        )

        value_label = (
            ctk.CTkLabel(
                frame,
                text=value,
                font=ctk.CTkFont(
                    size=26,
                    weight="bold"
                )
            )
        )

        value_label.pack(
            anchor="w",
            padx=18,
            pady=(
                0,
                15
            )
        )

        return value_label


    # ========================================================
    # TREE STYLE
    # ========================================================

    def configure_treeview_style(
        self
    ):

        style = ttk.Style()

        try:
            style.theme_use(
                "clam"
            )
        except Exception:
            pass

        style.configure(
            "Treeview",
            background="#242424",
            fieldbackground="#242424",
            foreground="#ffffff",
            rowheight=34,
            borderwidth=0,
            font=(
                "Segoe UI",
                10
            )
        )

        style.configure(
            "Treeview.Heading",
            background="#333333",
            foreground="#ffffff",
            relief="flat",
            font=(
                "Segoe UI",
                10,
                "bold"
            )
        )

        style.map(
            "Treeview",
            background=[
                (
                    "selected",
                    "#1f6aa5"
                )
            ]
        )


    # ========================================================
    # STATUS STEAM
    # ========================================================

    def update_steam_account_status(
        self
    ):

        steam_id = (
            self.config_data
            .get(
                "steam_id_64",
                ""
            )
        )

        if is_valid_steam_id_64(
            steam_id
        ):

            masked = (
                steam_id[:7]
                +
                "••••••"
                +
                steam_id[-4:]
            )

            self.steam_status_label.configure(
                text=(
                    "Steam: ✓ configurada\n"
                    f"{masked}"
                )
            )

        else:

            self.steam_status_label.configure(
                text=(
                    "Steam: ✕ não configurada"
                )
            )


    # ========================================================
    # STATUS PLAYNITE
    # ========================================================

    def update_integration_status_ui(
        self
    ):

        status = (
            get_playnite_integration_status()
        )

        self.integration_status = (
            status
        )

        if not status[
            "playnite_installed"
        ]:

            self.playnite_status_label.configure(
                text="Playnite: ✕ não encontrado"
            )

        elif status[
            "playnite_running"
        ]:

            self.playnite_status_label.configure(
                text="Playnite: ✓ em execução"
            )

        else:

            self.playnite_status_label.configure(
                text="Playnite: ✓ instalado"
            )

        if status[
            "plugin_installed"
        ]:

            self.plugin_status_label.configure(
                text="Plugin: ✓ instalado"
            )

        else:

            self.plugin_status_label.configure(
                text="Plugin: ✕ não encontrado"
            )

        if status[
            "export_exists"
        ]:

            modified = (
                status[
                    "export_modified"
                ]
            )

            self.sync_status_label.configure(
                text=(
                    "Biblioteca: ✓ sincronizada\n"
                    +
                    format_age(
                        modified
                    )
                )
            )

            size_kb = (
                status[
                    "export_size"
                ]
                /
                1024
            )

            self.file_status_label.configure(
                text=(
                    "Última sincronização\n"
                    f"{format_datetime(modified)}\n"
                    f"{size_kb:.1f} KB"
                )
            )

        else:

            self.sync_status_label.configure(
                text=(
                    "Biblioteca: ✕ "
                    "não sincronizada"
                )
            )

            self.file_status_label.configure(
                text=(
                    "O plugin ainda não criou "
                    "a biblioteca exportada."
                )
            )


    # ========================================================
    # INITIAL LOAD
    # ========================================================

    def initial_load(
        self
    ):

        self.update_integration_status_ui()

        self.update_steam_account_status()

        if not PLAYNITE_EXPORT_FILE.exists():

            self.status_label.configure(
                text=(
                    "Aguardando sincronização "
                    "com o Playnite."
                )
            )

            return

        try:

            games = (
                read_playnite_export()
            )

            self.playnite_games = (
                games
            )

            self.filtered_playnite_games = (
                filter_playnite_games(
                    games
                )
            )

            self.source_counts = (
                get_source_counts(
                    games
                )
            )

            self.card_playnite.configure(
                text=str(
                    len(games)
                )
            )

            if not is_valid_steam_id_64(
                self.config_data.get(
                    "steam_id_64",
                    ""
                )
            ):

                self.status_label.configure(
                    text=(
                        "Configure sua conta Steam "
                        "para continuar."
                    )
                )

            else:

                self.status_label.configure(
                    text=(
                        "Biblioteca do Playnite carregada. "
                        "Clique em Atualizar dados."
                    )
                )

        except Exception as e:

            messagebox.showerror(
                "Erro no Playnite",
                str(e)
            )


    # ========================================================
    # STEAM SETTINGS
    # ========================================================

    def show_steam_settings(
        self
    ):

        dialog = (
            ctk.CTkToplevel(
                self
            )
        )

        dialog.title(
            "Conta Steam"
        )

        dialog.geometry(
            "570x340"
        )

        dialog.resizable(
            False,
            False
        )

        dialog.transient(
            self
        )

        dialog.grab_set()

        title = (
            ctk.CTkLabel(
                dialog,
                text="Conta Steam",
                font=ctk.CTkFont(
                    size=22,
                    weight="bold"
                )
            )
        )

        title.pack(
            anchor="w",
            padx=25,
            pady=(
                25,
                5
            )
        )

        description = (
            ctk.CTkLabel(
                dialog,
                text=(
                    "Informe o seu SteamID64.\n"
                    "Ele será salvo somente neste computador."
                ),
                justify="left",
                text_color="gray70"
            )
        )

        description.pack(
            anchor="w",
            padx=25,
            pady=(
                0,
                20
            )
        )

        steam_id_label = (
            ctk.CTkLabel(
                dialog,
                text="SteamID64"
            )
        )

        steam_id_label.pack(
            anchor="w",
            padx=25,
            pady=(
                0,
                5
            )
        )

        steam_id_entry = (
            ctk.CTkEntry(
                dialog,
                height=40,
                placeholder_text=
                    "7656119XXXXXXXXXX"
            )
        )

        steam_id_entry.pack(
            fill="x",
            padx=25
        )

        current_steam_id = (
            self.config_data.get(
                "steam_id_64",
                ""
            )
        )

        if current_steam_id:

            steam_id_entry.insert(
                0,
                current_steam_id
            )

        help_label = (
            ctk.CTkLabel(
                dialog,
                text=(
                    "Exemplo: 76561198349875986"
                ),
                text_color="gray55",
                font=ctk.CTkFont(
                    size=11
                )
            )
        )

        help_label.pack(
            anchor="w",
            padx=25,
            pady=(
                6,
                0
            )
        )

        button_frame = (
            ctk.CTkFrame(
                dialog,
                fg_color="transparent"
            )
        )

        button_frame.pack(
            fill="x",
            padx=25,
            pady=25
        )

        save_button = (
            ctk.CTkButton(
                button_frame,
                text="Salvar",
                command=lambda:
                    self.save_steam_settings(
                        dialog,
                        steam_id_entry
                    )
            )
        )

        save_button.pack(
            side="left"
        )

        cancel_button = (
            ctk.CTkButton(
                button_frame,
                text="Cancelar",
                fg_color="transparent",
                border_width=1,
                command=
                    dialog.destroy
            )
        )

        cancel_button.pack(
            side="right"
        )


    # ========================================================
    # SAVE STEAM SETTINGS
    # ========================================================

    def save_steam_settings(
        self,
        dialog,
        entry
    ):

        steam_id = (
            entry
            .get()
            .strip()
        )

        if not is_valid_steam_id_64(
            steam_id
        ):

            messagebox.showerror(
                "SteamID64 inválido",
                (
                    "Informe um SteamID64 válido.\n\n"
                    "Ele deve conter 17 números."
                ),
                parent=dialog
            )

            return

        self.config_data[
            "steam_id_64"
        ] = steam_id

        try:

            save_config(
                self.config_data
            )

        except Exception as e:

            messagebox.showerror(
                "Erro",
                (
                    "Não foi possível salvar "
                    "a configuração.\n\n"
                    f"{e}"
                ),
                parent=dialog
            )

            return

        self.update_steam_account_status()

        self.status_label.configure(
            text=(
                "Conta Steam configurada. "
                "Clique em Atualizar dados."
            )
        )

        dialog.destroy()


    # ========================================================
    # REFRESH
    # ========================================================

    def start_refresh(
        self
    ):

        if self.loading:
            return

        self.update_integration_status_ui()

        steam_id = (
            self.config_data
            .get(
                "steam_id_64",
                ""
            )
        )

        # ----------------------------------------------------
        # CONTA STEAM
        # ----------------------------------------------------

        if not is_valid_steam_id_64(
            steam_id
        ):

            messagebox.showwarning(
                "Conta Steam",
                (
                    "Configure seu SteamID64 "
                    "antes de atualizar os dados."
                )
            )

            self.show_steam_settings()

            return

        # ----------------------------------------------------
        # PLAYNITE
        # ----------------------------------------------------

        if not PLAYNITE_EXPORT_FILE.exists():

            messagebox.showwarning(
                "Playnite",
                (
                    "A biblioteca do Playnite ainda "
                    "não foi sincronizada.\n\n"
                    "Abra ou reinicie o Playnite "
                    "com o plugin instalado."
                )
            )

            return

        # ----------------------------------------------------
        # INICIA
        # ----------------------------------------------------

        self.loading = True

        self.refresh_button.configure(
            state="disabled",
            text="Atualizando..."
        )

        self.progress_bar.set(
            0
        )

        thread = (
            threading.Thread(
                target=
                    self.refresh_worker,
                daemon=True
            )
        )

        thread.start()


    # ========================================================
    # WORKER
    # ========================================================

    def refresh_worker(
        self
    ):

        try:

            steam_id = (
                self.config_data[
                    "steam_id_64"
                ]
            )

            # ------------------------------------------------
            # PLAYNITE
            # ------------------------------------------------

            self.event_queue.put(
                (
                    "status",
                    "Lendo biblioteca do Playnite..."
                )
            )

            games = (
                read_playnite_export()
            )

            filtered_games = (
                filter_playnite_games(
                    games
                )
            )

            self.event_queue.put(
                (
                    "playnite_loaded",
                    {
                        "games":
                            games,

                        "filtered":
                            filtered_games,

                        "sources":
                            get_source_counts(
                                games
                            )
                    }
                )
            )

            # ------------------------------------------------
            # STEAM
            # ------------------------------------------------

            self.event_queue.put(
                (
                    "status",
                    "Obtendo wishlist da Steam..."
                )
            )

            session = (
                create_steam_session()
            )

            appids = (
                get_steam_wishlist_appids(
                    steam_id,
                    session
                )
            )

            total = (
                len(appids)
            )

            self.event_queue.put(
                (
                    "wishlist_total",
                    total
                )
            )

            wishlist = {}

            failures = 0

            # ------------------------------------------------
            # NOMES
            # ------------------------------------------------

            for (
                index,
                appid
            ) in enumerate(
                appids,
                start=1
            ):

                name = (
                    get_steam_app_name(
                        appid,
                        session
                    )
                )

                if name:

                    wishlist[
                        name
                    ] = appid

                else:

                    failures += 1

                progress = (
                    index / total
                    if total
                    else 0
                )

                self.event_queue.put(
                    (
                        "progress",
                        {
                            "value":
                                progress,

                            "current":
                                index,

                            "total":
                                total
                        }
                    )
                )

                time.sleep(
                    STEAM_APP_REQUEST_DELAY
                )

            # ------------------------------------------------
            # COMPARAÇÃO
            # ------------------------------------------------

            self.event_queue.put(
                (
                    "status",
                    "Comparando bibliotecas..."
                )
            )

            (
                exact,
                fuzzy
            ) = compare_games(
                wishlist,
                filtered_games
            )

            matches = (
                exact
                +
                fuzzy
            )

            self.event_queue.put(
                (
                    "complete",
                    {
                        "wishlist":
                            wishlist,

                        "wishlist_total":
                            total,

                        "failures":
                            failures,

                        "matches":
                            matches,

                        "exact":
                            exact,

                        "fuzzy":
                            fuzzy
                    }
                )
            )

        except Exception as e:

            self.event_queue.put(
                (
                    "error",
                    str(e)
                )
            )


    # ========================================================
    # EVENT QUEUE
    # ========================================================

    def process_event_queue(
        self
    ):

        try:

            while True:

                event, data = (
                    self.event_queue
                    .get_nowait()
                )

                if event == "status":

                    self.status_label.configure(
                        text=data
                    )

                elif event == "progress":

                    self.progress_bar.set(
                        data[
                            "value"
                        ]
                    )

                    self.status_label.configure(
                        text=(
                            "Obtendo nomes da Steam: "
                            f"{data['current']}/"
                            f"{data['total']}"
                        )
                    )

                elif event == "wishlist_total":

                    self.total_wishlist_appids = (
                        data
                    )

                    self.card_wishlist.configure(
                        text=str(
                            data
                        )
                    )

                elif event == "playnite_loaded":

                    self.playnite_games = (
                        data[
                            "games"
                        ]
                    )

                    self.filtered_playnite_games = (
                        data[
                            "filtered"
                        ]
                    )

                    self.source_counts = (
                        data[
                            "sources"
                        ]
                    )

                    self.card_playnite.configure(
                        text=str(
                            len(
                                self.playnite_games
                            )
                        )
                    )

                elif event == "complete":

                    self.wishlist = (
                        data[
                            "wishlist"
                        ]
                    )

                    self.failed_steam_names = (
                        data[
                            "failures"
                        ]
                    )

                    self.matches = (
                        data[
                            "matches"
                        ]
                    )

                    self.card_wishlist.configure(
                        text=str(
                            data[
                                "wishlist_total"
                            ]
                        )
                    )

                    self.card_matches.configure(
                        text=str(
                            len(
                                self.matches
                            )
                        )
                    )

                    self.card_unresolved.configure(
                        text=str(
                            self.failed_steam_names
                        )
                    )

                    self.steam_status_label.configure(
                        text=(
                            "Steam: ✓ "
                            f"{len(self.wishlist)} "
                            "nomes identificados"
                        )
                    )

                    self.update_source_filter()

                    self.apply_filters()

                    self.progress_bar.set(
                        1
                    )

                    self.status_label.configure(
                        text=(
                            "Concluído. "
                            f"{len(self.matches)} "
                            "correspondências encontradas."
                        )
                    )

                    self.loading = False

                    self.refresh_button.configure(
                        state="normal",
                        text="Atualizar dados"
                    )

                    self.update_integration_status_ui()

                elif event == "error":

                    self.loading = False

                    self.refresh_button.configure(
                        state="normal",
                        text="Atualizar dados"
                    )

                    self.progress_bar.set(
                        0
                    )

                    self.status_label.configure(
                        text=(
                            "Erro durante a atualização."
                        )
                    )

                    messagebox.showerror(
                        "Erro",
                        data
                    )

        except queue.Empty:
            pass

        self.after(
            100,
            self.process_event_queue
        )


    # ========================================================
    # FILTRO DE FONTES
    # ========================================================

    def update_source_filter(
        self
    ):

        sources = sorted({
            item[
                "source"
            ]
            for item
            in self.matches
        })

        values = (
            [
                "Todas as bibliotecas"
            ]
            +
            sources
        )

        self.source_filter.configure(
            values=values
        )

        self.source_filter.set(
            "Todas as bibliotecas"
        )


    # ========================================================
    # FILTROS
    # ========================================================

    def apply_filters(
        self
    ):

        search = (
            self.search_entry
            .get()
            .strip()
            .lower()
        )

        source_filter = (
            self.source_filter
            .get()
        )

        match_filter = (
            self.match_filter
            .get()
        )

        filtered = []

        for item in self.matches:

            if search:

                haystack = (
                    item["wishlist"]
                    +
                    " "
                    +
                    item["playnite"]
                    +
                    " "
                    +
                    item["source"]
                ).lower()

                if (
                    search
                    not in
                    haystack
                ):
                    continue

            if (
                source_filter
                !=
                "Todas as bibliotecas"
            ):

                if (
                    item["source"]
                    !=
                    source_filter
                ):
                    continue

            if (
                match_filter
                !=
                "Todos"
            ):

                if (
                    item["type"]
                    !=
                    match_filter
                ):
                    continue

            filtered.append(
                item
            )

        self.populate_table(
            filtered
        )

        self.result_count_label.configure(
            text=(
                f"{len(filtered)} resultado(s) "
                f"exibido(s) de "
                f"{len(self.matches)} encontrado(s)."
            )
        )


    # ========================================================
    # TABELA
    # ========================================================

    def populate_table(
        self,
        matches
    ):

        for row in (
            self.tree.get_children()
        ):

            self.tree.delete(
                row
            )

        for item in matches:

            self.tree.insert(
                "",
                "end",
                values=(
                    item[
                        "wishlist"
                    ],

                    item[
                        "playnite"
                    ],

                    item[
                        "source"
                    ],

                    item[
                        "type"
                    ],

                    (
                        f"{item['score']:.1f}%"
                    )
                ),
                tags=(
                    item[
                        "appid"
                    ],
                )
            )


    # ========================================================
    # PÁGINA STEAM
    # ========================================================

    def open_selected_steam_page(
        self,
        event=None
    ):

        selected = (
            self.tree.selection()
        )

        if not selected:
            return

        item_id = (
            selected[0]
        )

        tags = (
            self.tree.item(
                item_id,
                "tags"
            )
        )

        if not tags:
            return

        appid = (
            tags[0]
        )

        webbrowser.open(
            "https://store.steampowered.com/"
            f"app/{appid}/"
        )


    # ========================================================
    # INTEGRAÇÃO PLAYNITE
    # ========================================================

    def show_integration_info(
        self
    ):

        self.update_integration_status_ui()

        status = (
            self.integration_status
        )

        dialog = (
            ctk.CTkToplevel(
                self
            )
        )

        dialog.title(
            "Integração com Playnite"
        )

        dialog.geometry(
            "720x510"
        )

        dialog.transient(
            self
        )

        title = (
            ctk.CTkLabel(
                dialog,
                text="Integração com Playnite",
                font=ctk.CTkFont(
                    size=22,
                    weight="bold"
                )
            )
        )

        title.pack(
            anchor="w",
            padx=25,
            pady=(
                25,
                15
            )
        )

        if status[
            "plugin_installed"
        ]:

            plugin_text = (
                "✓ Plugin instalado"
            )

        else:

            plugin_text = (
                "✕ Plugin não encontrado"
            )

        if status[
            "export_exists"
        ]:

            export_text = (
                "✓ Biblioteca sincronizada"
            )

        else:

            export_text = (
                "✕ Biblioteca não sincronizada"
            )

        info = (
            ctk.CTkLabel(
                dialog,
                text=(
                    f"{plugin_text}\n"
                    f"{export_text}\n\n"
                    "Última sincronização:\n"
                    f"{format_datetime(status['export_modified'])}\n\n"
                    "Plugin esperado em:\n"
                    f"{PLAYNITE_PLUGIN_DIR}\n\n"
                    "Biblioteca exportada:\n"
                    f"{PLAYNITE_EXPORT_FILE}"
                ),
                justify="left",
                anchor="w",
                wraplength=650
            )
        )

        info.pack(
            fill="x",
            padx=25,
            pady=10
        )

        refresh_button = (
            ctk.CTkButton(
                dialog,
                text="Verificar novamente",
                command=lambda:
                    self.refresh_integration_dialog(
                        dialog
                    )
            )
        )

        refresh_button.pack(
            side="left",
            padx=25,
            pady=25
        )

        close_button = (
            ctk.CTkButton(
                dialog,
                text="Fechar",
                fg_color="transparent",
                border_width=1,
                command=
                    dialog.destroy
            )
        )

        close_button.pack(
            side="right",
            padx=25,
            pady=25
        )


    def refresh_integration_dialog(
        self,
        dialog
    ):

        self.update_integration_status_ui()

        dialog.destroy()

        self.show_integration_info()


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":

    app = WishlistApp()

    app.mainloop()