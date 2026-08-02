import os
import re
import sys
import json
import time
import queue
import shutil
import threading
import webbrowser
import subprocess
from pathlib import Path
from datetime import datetime
from tkinter import ttk, messagebox

from PIL import Image
import customtkinter as ctk
import requests
from rapidfuzz import process, fuzz


# ============================================================
# APLICATIVO
# ============================================================

APP_NAME = "Steam Wishlist × Playnite"
APP_VERSION = "1.3.0"


# ============================================================
# CONFIGURAÇÕES GERAIS
# ============================================================

FUZZY_SCORE_CUTOFF = 85

IGNORE_STEAM_SOURCE = True

STEAM_APP_REQUEST_DELAY = 0.08


# ============================================================
# CAMINHOS BASE
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


# ============================================================
# DIRETÓRIO DO PROGRAMA / RECURSOS
# ============================================================

def get_resource_base_dir():
    """
    Retorna a pasta base dos recursos.

    Funciona:
    - rodando como .py;
    - futuramente empacotado com PyInstaller.
    """

    if getattr(
        sys,
        "frozen",
        False
    ):

        temp_dir = getattr(
            sys,
            "_MEIPASS",
            None
        )

        if temp_dir:
            return Path(
                temp_dir
            )

        return Path(
            sys.executable
        ).resolve().parent

    return Path(
        __file__
    ).resolve().parent


RESOURCE_BASE_DIR = (
    get_resource_base_dir()
)

LOCALES_DIR = (
    RESOURCE_BASE_DIR
    /
    "locales"
)

ASSETS_DIR = (
    RESOURCE_BASE_DIR
    /
    "assets"
)

APP_ICON = (
    ASSETS_DIR
    /
    "app.ico"
)

APP_LOGO = (
    ASSETS_DIR
    /
    "app.png"
)

BUNDLED_PLUGIN_DIR = (
    RESOURCE_BASE_DIR
    /
    "resources"
    /
    "PlaynitePlugin"
)

BUNDLED_PLUGIN_DLL = (
    BUNDLED_PLUGIN_DIR
    /
    "SteamWishlistExporter.dll"
)

BUNDLED_PLUGIN_MANIFEST = (
    BUNDLED_PLUGIN_DIR
    /
    "extension.yaml"
)

TRANSLATIONS = {}


def load_translations(
    language_code
):
    global TRANSLATIONS

    language_file = (
        LOCALES_DIR
        /
        f"{language_code}.json"
    )

    if not language_file.exists():
        raise FileNotFoundError(
            f"Arquivo de idioma não encontrado: {language_file}"
        )

    with language_file.open(
        "r",
        encoding="utf-8"
    ) as f:
        TRANSLATIONS = json.load(f)


def t(
    key,
    **kwargs
):
    text = TRANSLATIONS.get(
        key,
        key
    )

    if kwargs:
        try:
            return text.format(
                **kwargs
            )
        except Exception:
            return text

    return text


LANGUAGE_LABELS = {
    "pt_BR": "Português (Brasil)",
    "en_US": "English"
}

LANGUAGE_CODES = {
    label: code
    for code, label
    in LANGUAGE_LABELS.items()
}

# ============================================================
# CONFIGURAÇÃO DO NOSSO APP
# ============================================================

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


# ============================================================
# PLAYNITE
# ============================================================

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

PLAYNITE_EXTENSIONS_DIR = (
    PLAYNITE_DATA_DIR
    /
    "Extensions"
)

PLAYNITE_PLUGIN_DIR = (
    PLAYNITE_EXTENSIONS_DIR
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

ctk.set_appearance_mode(
    "dark"
)

ctk.set_default_color_theme(
    "blue"
)


# ============================================================
# IDENTIDADE VISUAL
# ============================================================

COLOR_BG = "#15171C"
COLOR_SIDEBAR = "#1B1E24"
COLOR_SURFACE = "#20242B"
COLOR_SURFACE_ALT = "#242933"
COLOR_SURFACE_HOVER = "#2A303A"
COLOR_TABLE = "#1C2026"
COLOR_TABLE_ALT = "#20252D"
COLOR_TABLE_HEADER = "#2B313B"
COLOR_BORDER = "#323A47"

COLOR_BLUE = "#258DFF"
COLOR_BLUE_HOVER = "#1677D2"
COLOR_CYAN = "#31C8FF"
COLOR_ORANGE = "#FF7A18"
COLOR_ORANGE_DARK = "#C85A0A"

COLOR_TEXT = "#F5F7FA"
COLOR_TEXT_SECONDARY = "#A7B0BD"
COLOR_TEXT_MUTED = "#6F7988"
COLOR_SUCCESS = "#45C486"
COLOR_WARNING = "#F2B84B"
COLOR_DANGER = "#E46C6C"


# ============================================================
# CONFIGURAÇÃO DO APP
# ============================================================

def load_config():
    default_config = {
        "steam_id_64": "",
        "language": "en_US"
    }

    if not APP_CONFIG_FILE.exists():
        return default_config

    try:

        with APP_CONFIG_FILE.open(
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(
                f
            )

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
                ).strip(),

            "language":
                str(
                    data.get(
                        "language",
                        "en_US"
                    )
                    or
                    "en_US"
                ).strip()
        }

    except Exception:

        return default_config


def save_config(
    config
):
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
# STEAM ID
# ============================================================

def is_valid_steam_id_64(
    value
):
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

def clean_title(
    title
):
    if not title:
        return ""

    title = (
        title.lower()
    )

    title = (
        title
        .replace(
            "™",
            ""
        )
        .replace(
            "®",
            ""
        )
        .replace(
            "©",
            ""
        )
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
# RECURSOS DO PLUGIN
# ============================================================

def bundled_plugin_available():
    return (
        BUNDLED_PLUGIN_DIR.is_dir()
        and
        BUNDLED_PLUGIN_DLL.is_file()
        and
        BUNDLED_PLUGIN_MANIFEST.is_file()
    )


# ============================================================
# INSTALAÇÃO DO PLUGIN
# ============================================================

def install_playnite_plugin():
    """
    Copia a versão distribuída do plugin para a pasta
    oficial de extensões do Playnite.
    """

    if not bundled_plugin_available():

        raise FileNotFoundError(
            t(
                "plugin_files_missing",
                path=BUNDLED_PLUGIN_DIR
            )
        )

    PLAYNITE_EXTENSIONS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # REMOVE INSTALAÇÃO EXISTENTE
    # --------------------------------------------------------

    if PLAYNITE_PLUGIN_DIR.exists():

        try:

            shutil.rmtree(
                PLAYNITE_PLUGIN_DIR
            )

        except Exception as e:

            raise RuntimeError(
                t(
                    "plugin_replace_error",
                    details=e
                )
            )

    # --------------------------------------------------------
    # COPIA RECURSOS
    # --------------------------------------------------------

    try:

        shutil.copytree(
            BUNDLED_PLUGIN_DIR,
            PLAYNITE_PLUGIN_DIR
        )

    except Exception as e:

        raise RuntimeError(
            t(
                "plugin_install_error",
                details=e
            )
        )

    # --------------------------------------------------------
    # VALIDA RESULTADO
    # --------------------------------------------------------

    if not (
        PLAYNITE_PLUGIN_DLL.is_file()
        and
        PLAYNITE_PLUGIN_MANIFEST.is_file()
    ):

        raise RuntimeError(
            t(
                "plugin_validation_error"
            )
        )

    return True


# ============================================================
# PLAYNITE - STATUS
# ============================================================

def get_playnite_integration_status():

    playnite_installed = (
        PLAYNITE_EXE.exists()
    )

    plugin_installed = (
        PLAYNITE_PLUGIN_DIR.is_dir()
        and
        PLAYNITE_PLUGIN_DLL.is_file()
        and
        PLAYNITE_PLUGIN_MANIFEST.is_file()
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

        "bundled_plugin_available":
            bundled_plugin_available(),

        "export_exists":
            export_exists,

        "export_size":
            export_size,

        "export_modified":
            export_modified
    }


# ============================================================
# DATA
# ============================================================

def format_datetime(
    value
):
    if not value:
        return "—"

    return value.strftime(
        t(
            "datetime_format"
        )
    )


def format_age(
    value
):
    if not value:
        return t(
            "never"
        )

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
        return t(
            "age_less_than_minute"
        )

    minutes = (
        seconds // 60
    )

    if minutes < 60:

        if minutes == 1:
            return t(
                "age_one_minute"
            )

        return t(
            "age_minutes",
            count=minutes
        )

    hours = (
        minutes // 60
    )

    if hours < 24:

        if hours == 1:
            return t(
                "age_one_hour"
            )

        return t(
            "age_hours",
            count=hours
        )

    days = (
        hours // 24
    )

    if days == 1:
        return t(
            "age_one_day"
        )

    return t(
        "age_days",
        count=days
    )


# ============================================================
# PLAYNITE - BIBLIOTECA
# ============================================================

def read_playnite_export():

    if not PLAYNITE_EXPORT_FILE.exists():

        raise FileNotFoundError(
            t(
                "playnite_export_not_found"
            )
        )

    try:

        with PLAYNITE_EXPORT_FILE.open(
            "r",
            encoding="utf-8-sig"
        ) as f:

            data = json.load(
                f
            )

    except json.JSONDecodeError as e:

        raise RuntimeError(
            t(
                "playnite_invalid_json",
                details=e
            )
        )

    except Exception as e:

        raise RuntimeError(
            t(
                "playnite_read_error",
                details=e
            )
        )

    if isinstance(
        data,
        dict
    ):

        data = [
            data
        ]

    if not isinstance(
        data,
        list
    ):

        raise RuntimeError(
            t(
                "playnite_unexpected_format"
            )
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
                )
        })

    return games


# ============================================================
# FONTES PLAYNITE
# ============================================================

def get_source_counts(
    games
):
    counts = {}

    for game in games:

        source = (
            game.get(
                "source"
            )
            or
            t("unknown_source")
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


def filter_playnite_games(
    games
):
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
# STEAM WISHLIST
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

    if (
        response.status_code
        !=
        200
    ):

        raise RuntimeError(
            t(
                "steam_http_error",
                status=response.status_code
            )
        )

    try:

        data = (
            response.json()
        )

    except requests.exceptions.JSONDecodeError:

        raise RuntimeError(
            t(
                "steam_invalid_json"
            )
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
                str(
                    appid
                )
            )

    return list(
        dict.fromkeys(
            appids
        )
    )


# ============================================================
# APP DETAILS
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
                str(
                    appid
                )
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
# MATCHING
# ============================================================

def compare_games(
    wishlist,
    playnite_games
):

    normalized_playnite = {}

    for game in playnite_games:

        normalized = (
            clean_title(
                game[
                    "name"
                ]
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

        if normalized in normalized_playnite:

            for game in normalized_playnite[
                normalized
            ]:

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
                            t("unknown_source")
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

        match = process.extractOne(
            normalized,
            normalized_playnite.keys(),
            scorer=
                fuzz.token_sort_ratio,
            score_cutoff=
                FUZZY_SCORE_CUTOFF
        )

        if not match:
            continue

        matched_key = (
            match[0]
        )

        score = (
            match[1]
        )

        for game in normalized_playnite[
            matched_key
        ]:

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
                        t("unknown_source")
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

    def __init__(
        self
    ):

        super().__init__()

        self.config_data = (
            load_config()
        )

        self.language_code = (
            self.config_data.get(
                "language",
                "en_US"
            )
        )

        if self.language_code not in LANGUAGE_LABELS:
            self.language_code = "en_US"

        load_translations(
            self.language_code
        )

        self.plugin_restart_required = (
            False
        )

        # ----------------------------------------------------
        # JANELA
        # ----------------------------------------------------

        self.title(
            APP_NAME
        )

        try:
            if APP_ICON.exists():
                self.iconbitmap(
                    str(APP_ICON)
                )
        except Exception:
            pass

        self.geometry(
            "1360x840"
        )

        self.minsize(
            1120,
            700
        )

        self.configure(
            fg_color=COLOR_BG
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

        self.wishlist_total = 0

        self.matches = []

        self.source_counts = {}

        self.failed_steam_names = 0

        self.integration_status = {}

        self.logo_image = None

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

    def create_sidebar(
        self
    ):

        self.sidebar = (
            ctk.CTkFrame(
                self,
                width=265,
                corner_radius=0,
                fg_color=COLOR_SIDEBAR
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
        # MARCA
        # ----------------------------------------------------

        brand = (
            ctk.CTkFrame(
                self.sidebar,
                fg_color="transparent"
            )
        )

        brand.pack(
            fill="x",
            padx=22,
            pady=(
                24,
                10
            )
        )

        if APP_LOGO.exists():

            try:

                logo_source = (
                    Image.open(
                        APP_LOGO
                    )
                )

                self.logo_image = (
                    ctk.CTkImage(
                        light_image=logo_source,
                        dark_image=logo_source,
                        size=(
                            56,
                            56
                        )
                    )
                )

                logo = (
                    ctk.CTkLabel(
                        brand,
                        text="",
                        image=self.logo_image
                    )
                )

                logo.grid(
                    row=0,
                    column=0,
                    rowspan=3,
                    sticky="nw",
                    padx=(
                        0,
                        12
                    )
                )

            except Exception:
                pass

        brand_text = (
            ctk.CTkFrame(
                brand,
                fg_color="transparent"
            )
        )

        brand_text.grid(
            row=0,
            column=1,
            sticky="nw"
        )

        title = (
            ctk.CTkLabel(
                brand_text,
                text="Wishlist\nChecker",
                font=ctk.CTkFont(
                    size=23,
                    weight="bold"
                ),
                text_color=COLOR_TEXT,
                justify="left",
                anchor="w"
            )
        )

        title.pack(
            anchor="w"
        )

        subtitle = (
            ctk.CTkLabel(
                brand_text,
                text="STEAM × PLAYNITE",
                font=ctk.CTkFont(
                    size=10,
                    weight="bold"
                ),
                text_color=COLOR_CYAN
            )
        )

        subtitle.pack(
            anchor="w",
            pady=(
                5,
                0
            )
        )

        version_badge = (
            ctk.CTkLabel(
                brand_text,
                text=f"  v{APP_VERSION}  ",
                height=22,
                corner_radius=6,
                fg_color=COLOR_SURFACE_ALT,
                text_color=COLOR_TEXT_SECONDARY,
                font=ctk.CTkFont(
                    size=10
                )
            )
        )

        version_badge.pack(
            anchor="w",
            pady=(
                7,
                0
            )
        )

        brand_accent = (
            ctk.CTkFrame(
                self.sidebar,
                height=3,
                corner_radius=2,
                fg_color=COLOR_ORANGE
            )
        )

        brand_accent.pack(
            fill="x",
            padx=22,
            pady=(
                4,
                18
            )
        )

        # ----------------------------------------------------
        # AÇÃO PRINCIPAL
        # ----------------------------------------------------

        self.refresh_button = (
            ctk.CTkButton(
                self.sidebar,
                text=f"↻  {t('refresh_library')}",
                height=46,
                corner_radius=9,
                fg_color=COLOR_BLUE,
                hover_color=COLOR_BLUE_HOVER,
                text_color="#FFFFFF",
                font=ctk.CTkFont(
                    size=13,
                    weight="bold"
                ),
                command=
                    self.start_refresh
            )
        )

        self.refresh_button.pack(
            fill="x",
            padx=18,
            pady=(
                0,
                10
            )
        )

        # ----------------------------------------------------
        # CONFIGURAÇÕES
        # ----------------------------------------------------

        steam_button = (
            ctk.CTkButton(
                self.sidebar,
                text=t("steam_account_button"),
                height=42,
                corner_radius=8,
                fg_color="transparent",
                hover_color=COLOR_SURFACE_HOVER,
                border_width=1,
                border_color=COLOR_BORDER,
                text_color=COLOR_TEXT,
                anchor="w",
                command=
                    self.show_steam_settings
            )
        )

        steam_button.pack(
            fill="x",
            padx=18,
            pady=5
        )

        integration_button = (
            ctk.CTkButton(
                self.sidebar,
                text=t("playnite_integration_button"),
                height=42,
                corner_radius=8,
                fg_color="transparent",
                hover_color=COLOR_SURFACE_HOVER,
                border_width=1,
                border_color=COLOR_BORDER,
                text_color=COLOR_TEXT,
                anchor="w",
                command=
                    self.show_integration_info
            )
        )

        integration_button.pack(
            fill="x",
            padx=18,
            pady=5
        )

        language_label = (
            ctk.CTkLabel(
                self.sidebar,
                text=t("language_label"),
                anchor="w",
                text_color=COLOR_TEXT_MUTED,
                font=ctk.CTkFont(
                    size=10,
                    weight="bold"
                )
            )
        )

        language_label.pack(
            fill="x",
            padx=22,
            pady=(
                14,
                5
            )
        )

        self.language_selector = (
            ctk.CTkOptionMenu(
                self.sidebar,
                values=list(
                    LANGUAGE_CODES.keys()
                ),
                height=38,
                corner_radius=8,
                fg_color=COLOR_SURFACE_ALT,
                button_color=COLOR_SURFACE_HOVER,
                button_hover_color=COLOR_BLUE,
                text_color=COLOR_TEXT,
                dropdown_fg_color=COLOR_SURFACE_ALT,
                dropdown_hover_color=COLOR_SURFACE_HOVER,
                dropdown_text_color=COLOR_TEXT,
                command=
                    self.change_language
            )
        )

        self.language_selector.pack(
            fill="x",
            padx=18,
            pady=(
                0,
                5
            )
        )

        self.language_selector.set(
            LANGUAGE_LABELS[
                self.language_code
            ]
        )

        separator = (
            ctk.CTkFrame(
                self.sidebar,
                height=1,
                fg_color=COLOR_BORDER
            )
        )

        separator.pack(
            fill="x",
            padx=22,
            pady=20
        )

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        status_title = (
            ctk.CTkLabel(
                self.sidebar,
                text="STATUS",
                font=ctk.CTkFont(
                    size=11,
                    weight="bold"
                ),
                text_color=COLOR_TEXT_MUTED
            )
        )

        status_title.pack(
            anchor="w",
            padx=24,
            pady=(
                0,
                7
            )
        )

        status_font = (
            ctk.CTkFont(
                size=12
            )
        )

        self.playnite_status_label = (
            ctk.CTkLabel(
                self.sidebar,
                text=t("status_playnite_checking"),
                anchor="w",
                justify="left",
                wraplength=205,
                font=status_font,
                text_color=COLOR_TEXT_SECONDARY
            )
        )

        self.playnite_status_label.pack(
            fill="x",
            padx=24,
            pady=5
        )

        self.plugin_status_label = (
            ctk.CTkLabel(
                self.sidebar,
                text=t("status_plugin_checking"),
                anchor="w",
                justify="left",
                wraplength=205,
                font=status_font,
                text_color=COLOR_TEXT_SECONDARY
            )
        )

        self.plugin_status_label.pack(
            fill="x",
            padx=24,
            pady=5
        )

        self.sync_status_label = (
            ctk.CTkLabel(
                self.sidebar,
                text=t("status_library_checking"),
                anchor="w",
                justify="left",
                wraplength=205,
                font=status_font,
                text_color=COLOR_TEXT_SECONDARY
            )
        )

        self.sync_status_label.pack(
            fill="x",
            padx=24,
            pady=5
        )

        self.steam_status_label = (
            ctk.CTkLabel(
                self.sidebar,
                text="●  Steam\n    —",
                anchor="w",
                justify="left",
                wraplength=205,
                font=status_font,
                text_color=COLOR_TEXT_SECONDARY
            )
        )

        self.steam_status_label.pack(
            fill="x",
            padx=24,
            pady=5
        )

        self.file_status_label = (
            ctk.CTkLabel(
                self.sidebar,
                text="",
                anchor="w",
                justify="left",
                wraplength=205,
                text_color=COLOR_TEXT_MUTED,
                font=ctk.CTkFont(
                    size=10
                )
            )
        )

        self.file_status_label.pack(
            fill="x",
            padx=24,
            pady=(
                16,
                0
            )
        )

    def change_language(
        self,
        selected_label
    ):

        language_code = (
            LANGUAGE_CODES.get(
                selected_label
            )
        )

        if not language_code:
            return

        if language_code == self.language_code:
            return

        if self.loading:
            self.language_selector.set(
                LANGUAGE_LABELS[
                    self.language_code
                ]
            )

            messagebox.showinfo(
                t("language_change_title"),
                t("language_change_during_update")
            )

            return

        self.language_code = (
            language_code
        )

        self.config_data[
            "language"
        ] = language_code

        save_config(
            self.config_data
        )

        load_translations(
            language_code
        )

        self.rebuild_interface()


    def rebuild_interface(
        self
    ):

        for widget in (
            self.winfo_children()
        ):

            try:
                widget.destroy()
            except Exception:
                pass

        self.logo_image = None

        self.create_sidebar()

        self.create_main_area()

        self.configure_treeview_style()

        self.update_integration_status_ui()

        self.update_steam_account_status()

        self.card_playnite.configure(
            text=str(
                len(
                    self.playnite_games
                )
            )
            if self.playnite_games
            else "—"
        )

        self.card_wishlist.configure(
            text=str(
                self.wishlist_total
            )
            if self.wishlist_total
            else "—"
        )

        self.card_matches.configure(
            text=str(
                len(
                    self.matches
                )
            )
            if self.wishlist_total
            else "—"
        )

        self.card_unresolved.configure(
            text=str(
                self.failed_steam_names
            )
            if self.wishlist_total
            else "—"
        )

        if self.matches:
            self.update_source_filter()
            self.apply_filters()

        elif self.wishlist_total:
            self.result_count_label.configure(
                text=t(
                    "result_count",
                    shown=0,
                    found=0
                )
            )

        steam_id = (
            self.config_data.get(
                "steam_id_64",
                ""
            )
        )

        if not PLAYNITE_EXPORT_FILE.exists():
            self.status_label.configure(
                text=t(
                    "playnite_not_synced_status"
                )
            )

        elif not is_valid_steam_id_64(
            steam_id
        ):
            self.status_label.configure(
                text=t(
                    "configure_steam_to_continue"
                )
            )

        else:
            self.status_label.configure(
                text=t(
                    "ready_refresh"
                )
            )


    def create_main_area(
        self
    ):

        self.main_frame = (
            ctk.CTkFrame(
                self,
                corner_radius=0,
                fg_color=COLOR_BG
            )
        )

        self.main_frame.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=28,
            pady=24
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
        # CABEÇALHO
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
                20
            )
        )

        title = (
            ctk.CTkLabel(
                header,
                text=t("main_title"),
                font=ctk.CTkFont(
                    size=27,
                    weight="bold"
                ),
                text_color=COLOR_TEXT
            )
        )

        title.pack(
            anchor="w"
        )

        subtitle = (
            ctk.CTkLabel(
                header,
                text=t("main_subtitle"),
                font=ctk.CTkFont(
                    size=13
                ),
                text_color=COLOR_TEXT_SECONDARY
            )
        )

        subtitle.pack(
            anchor="w",
            pady=(
                2,
                0
            )
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

        for col in range(
            4
        ):

            cards.grid_columnconfigure(
                col,
                weight=1
            )

        self.card_playnite = (
            self.create_card(
                cards,
                0,
                "PLAYNITE",
                "—",
                t("card_playnite_subtitle"),
                COLOR_ORANGE,
                "P"
            )
        )

        self.card_wishlist = (
            self.create_card(
                cards,
                1,
                "WISHLIST",
                "—",
                t("card_wishlist_subtitle"),
                COLOR_CYAN,
                "W"
            )
        )

        self.card_matches = (
            self.create_card(
                cards,
                2,
                "MATCHES",
                "—",
                t("card_matches_subtitle"),
                COLOR_BLUE,
                "✓"
            )
        )

        self.card_unresolved = (
            self.create_card(
                cards,
                3,
                t("card_pending_title"),
                "—",
                t("card_pending_subtitle"),
                COLOR_TEXT_MUTED,
                "?"
            )
        )

        # ----------------------------------------------------
        # TOOLBAR / FILTROS
        # ----------------------------------------------------

        filters = (
            ctk.CTkFrame(
                self.main_frame,
                corner_radius=10,
                fg_color=COLOR_SURFACE,
                border_width=1,
                border_color=COLOR_BORDER
            )
        )

        filters.grid(
            row=2,
            column=0,
            sticky="ew",
            pady=(
                0,
                16
            )
        )

        filters.grid_columnconfigure(
            0,
            weight=1
        )

        self.search_entry = (
            ctk.CTkEntry(
                filters,
                placeholder_text=t("search_placeholder"),
                height=42,
                corner_radius=8,
                fg_color=COLOR_SURFACE_ALT,
                border_color=COLOR_BORDER,
                text_color=COLOR_TEXT,
                placeholder_text_color=COLOR_TEXT_MUTED
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
                    t("all_libraries")
                ],
                width=190,
                height=42,
                corner_radius=8,
                fg_color=COLOR_SURFACE_ALT,
                button_color=COLOR_SURFACE_HOVER,
                button_hover_color=COLOR_BLUE,
                text_color=COLOR_TEXT,
                dynamic_resizing=False,
                dropdown_fg_color=COLOR_SURFACE_ALT,
                dropdown_hover_color=COLOR_SURFACE_HOVER,
                dropdown_text_color=COLOR_TEXT,
                command=lambda _:
                    self.apply_filters()
            )
        )

        self.source_filter.grid(
            row=0,
            column=1,
            padx=(
                0,
                8
            ),
            pady=12
        )

        self.match_filter = (
            ctk.CTkOptionMenu(
                filters,
                values=[
                    t("all_matches"),
                    t("exact_match"),
                    t("approximate_match")
                ],
                width=150,
                height=42,
                corner_radius=8,
                fg_color=COLOR_SURFACE_ALT,
                button_color=COLOR_SURFACE_HOVER,
                button_hover_color=COLOR_ORANGE,
                text_color=COLOR_TEXT,
                dynamic_resizing=False,
                dropdown_fg_color=COLOR_SURFACE_ALT,
                dropdown_hover_color=COLOR_SURFACE_HOVER,
                dropdown_text_color=COLOR_TEXT,
                command=lambda _:
                    self.apply_filters()
            )
        )

        self.match_filter.grid(
            row=0,
            column=2,
            padx=(
                0,
                12
            ),
            pady=12
        )

        # ----------------------------------------------------
        # RESULTADOS
        # ----------------------------------------------------

        result_header = (
            ctk.CTkFrame(
                self.main_frame,
                fg_color="transparent"
            )
        )

        result_header.grid(
            row=3,
            column=0,
            sticky="ew",
            pady=(
                0,
                9
            )
        )

        result_title = (
            ctk.CTkLabel(
                result_header,
                text=t("results_title"),
                font=ctk.CTkFont(
                    size=15,
                    weight="bold"
                ),
                text_color=COLOR_TEXT
            )
        )

        result_title.pack(
            side="left"
        )

        self.result_count_label = (
            ctk.CTkLabel(
                result_header,
                text=t("no_results_loaded"),
                font=ctk.CTkFont(
                    size=12
                ),
                text_color=COLOR_TEXT_MUTED
            )
        )

        self.result_count_label.pack(
            side="left",
            padx=(
                12,
                0
            )
        )

        # ----------------------------------------------------
        # TABELA
        # ----------------------------------------------------

        table_frame = (
            ctk.CTkFrame(
                self.main_frame,
                corner_radius=10,
                fg_color=COLOR_SURFACE,
                border_width=1,
                border_color=COLOR_BORDER
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
                selectmode="browse",
                style="Wishlist.Treeview"
            )
        )

        self.tree.heading(
            "wishlist",
            text="STEAM WISHLIST"
        )

        self.tree.heading(
            "playnite",
            text=t("column_playnite")
        )

        self.tree.heading(
            "source",
            text=t("column_library")
        )

        self.tree.heading(
            "type",
            text="MATCH"
        )

        self.tree.heading(
            "score",
            text=t("column_similarity")
        )

        self.tree.column(
            "wishlist",
            width=290,
            minwidth=180
        )

        self.tree.column(
            "playnite",
            width=290,
            minwidth=180
        )

        self.tree.column(
            "source",
            width=140,
            minwidth=90
        )

        self.tree.column(
            "type",
            width=120,
            minwidth=90,
            anchor="center"
        )

        self.tree.column(
            "score",
            width=110,
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
        # RODAPÉ / STATUS BAR
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
                text=t("ready_to_check"),
                anchor="w",
                text_color=COLOR_TEXT_SECONDARY,
                font=ctk.CTkFont(
                    size=12
                )
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
                width=250,
                height=8,
                corner_radius=4,
                fg_color=COLOR_SURFACE_ALT,
                progress_color=COLOR_BLUE
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

    def create_card(
        self,
        parent,
        column,
        title,
        value,
        subtitle,
        accent_color,
        symbol
    ):

        left_pad = (
            0
            if column == 0
            else 6
        )

        right_pad = (
            0
            if column == 3
            else 6
        )

        frame = (
            ctk.CTkFrame(
                parent,
                corner_radius=10,
                fg_color=COLOR_SURFACE,
                border_width=1,
                border_color=COLOR_BORDER
            )
        )

        frame.grid(
            row=0,
            column=column,
            sticky="ew",
            padx=(
                left_pad,
                right_pad
            )
        )

        accent = (
            ctk.CTkFrame(
                frame,
                height=3,
                corner_radius=2,
                fg_color=accent_color
            )
        )

        accent.pack(
            fill="x",
            padx=12,
            pady=(
                8,
                6
            )
        )

        header = (
            ctk.CTkFrame(
                frame,
                fg_color="transparent"
            )
        )

        header.pack(
            fill="x",
            padx=16
        )

        title_label = (
            ctk.CTkLabel(
                header,
                text=title,
                text_color=COLOR_TEXT_SECONDARY,
                font=ctk.CTkFont(
                    size=10,
                    weight="bold"
                )
            )
        )

        title_label.pack(
            side="left"
        )

        symbol_label = (
            ctk.CTkLabel(
                header,
                text=symbol,
                text_color=accent_color,
                font=ctk.CTkFont(
                    size=13,
                    weight="bold"
                )
            )
        )

        symbol_label.pack(
            side="right"
        )

        value_label = (
            ctk.CTkLabel(
                frame,
                text=value,
                font=ctk.CTkFont(
                    size=27,
                    weight="bold"
                ),
                text_color=COLOR_TEXT
            )
        )

        value_label.pack(
            anchor="w",
            padx=16,
            pady=(
                2,
                0
            )
        )

        subtitle_label = (
            ctk.CTkLabel(
                frame,
                text=subtitle,
                font=ctk.CTkFont(
                    size=11
                ),
                text_color=COLOR_TEXT_MUTED
            )
        )

        subtitle_label.pack(
            anchor="w",
            padx=16,
            pady=(
                0,
                10
            )
        )

        return value_label

    def configure_treeview_style(
        self
    ):

        style = (
            ttk.Style()
        )

        try:

            style.theme_use(
                "clam"
            )

        except Exception:
            pass

        style.configure(
            "Wishlist.Treeview",
            background=COLOR_TABLE,
            fieldbackground=COLOR_TABLE,
            foreground=COLOR_TEXT,
            rowheight=38,
            borderwidth=0,
            relief="flat",
            font=(
                "Segoe UI",
                10
            )
        )

        style.configure(
            "Wishlist.Treeview.Heading",
            background=COLOR_TABLE_HEADER,
            foreground=COLOR_TEXT,
            relief="flat",
            borderwidth=0,
            font=(
                "Segoe UI",
                9,
                "bold"
            )
        )

        style.map(
            "Wishlist.Treeview",
            background=[
                (
                    "selected",
                    "#263E57"
                )
            ],
            foreground=[
                (
                    "selected",
                    "#FFFFFF"
                )
            ]
        )

        style.map(
            "Wishlist.Treeview.Heading",
            background=[
                (
                    "active",
                    COLOR_SURFACE_HOVER
                )
            ]
        )

        self.tree.tag_configure(
            "row_even",
            background=COLOR_TABLE
        )

        self.tree.tag_configure(
            "row_odd",
            background=COLOR_TABLE_ALT
        )

    def update_steam_account_status(
        self
    ):

        steam_id = (
            self.config_data.get(
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
                    t(
                        "status_steam_configured",
                        steam_id=masked
                    )
                ),
                text_color=COLOR_BLUE
            )

        else:

            self.steam_status_label.configure(
                text=(
                    t(
                        "status_steam_not_configured"
                    )
                ),
                text_color=COLOR_DANGER
            )

    def update_integration_status_ui(
        self
    ):

        status = (
            get_playnite_integration_status()
        )

        self.integration_status = (
            status
        )

        # ----------------------------------------------------
        # PLAYNITE
        # ----------------------------------------------------

        if not status[
            "playnite_installed"
        ]:

            self.playnite_status_label.configure(
                text=(
                    t(
                        "status_playnite_not_found"
                    )
                ),
                text_color=COLOR_DANGER
            )

        elif status[
            "playnite_running"
        ]:

            self.playnite_status_label.configure(
                text=(
                    t(
                        "status_playnite_running"
                    )
                ),
                text_color=COLOR_ORANGE
            )

        else:

            self.playnite_status_label.configure(
                text=(
                    t(
                        "status_playnite_installed"
                    )
                ),
                text_color=COLOR_ORANGE
            )

        # ----------------------------------------------------
        # PLUGIN
        # ----------------------------------------------------

        if status[
            "plugin_installed"
        ]:

            if self.plugin_restart_required:

                self.plugin_status_label.configure(
                    text=(
                        t(
                            "status_plugin_restart"
                        )
                    ),
                    text_color=COLOR_WARNING
                )

            else:

                self.plugin_status_label.configure(
                    text=(
                        t(
                            "status_plugin_installed"
                        )
                    ),
                    text_color=COLOR_SUCCESS
                )

        else:

            self.plugin_status_label.configure(
                text=(
                    t(
                        "status_plugin_not_installed"
                    )
                ),
                text_color=COLOR_DANGER
            )

        # ----------------------------------------------------
        # BIBLIOTECA
        # ----------------------------------------------------

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
                    t(
                        "status_library_synced",
                        age=format_age(
                            modified
                        )
                    )
                ),
                text_color=COLOR_CYAN
            )

            self.file_status_label.configure(
                text=(
                    t(
                        "last_sync",
                        datetime=format_datetime(
                            modified
                        )
                    )
                )
            )

        else:

            self.sync_status_label.configure(
                text=(
                    t(
                        "status_library_not_synced"
                    )
                ),
                text_color=COLOR_DANGER
            )

            self.file_status_label.configure(
                text=(
                    t(
                        "open_playnite_after_install"
                    )
                )
            )

    def initial_load(
        self
    ):

        self.update_integration_status_ui()

        self.update_steam_account_status()

        if not PLAYNITE_EXPORT_FILE.exists():

            self.status_label.configure(
                text=(
                    t(
                        "playnite_not_synced_status"
                    )
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
                    len(
                        games
                    )
                )
            )

            steam_id = (
                self.config_data.get(
                    "steam_id_64",
                    ""
                )
            )

            if not is_valid_steam_id_64(
                steam_id
            ):

                self.status_label.configure(
                    text=(
                        t(
                            "configure_steam_to_continue"
                        )
                    )
                )

            else:

                self.status_label.configure(
                    text=(
                        t(
                            "ready_refresh"
                        )
                    )
                )

        except Exception as e:

            messagebox.showerror(
                t("playnite_error_title"),
                str(
                    e
                )
            )


    # ========================================================
    # CONTA STEAM
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
            t("steam_account_title")
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
                text=t("steam_account_title"),
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
                text=t("steam_account_description"),
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

        label = (
            ctk.CTkLabel(
                dialog,
                text="SteamID64"
            )
        )

        label.pack(
            anchor="w",
            padx=25,
            pady=(
                0,
                5
            )
        )

        entry = (
            ctk.CTkEntry(
                dialog,
                height=40,
                placeholder_text=
                    "7656119XXXXXXXXXX"
            )
        )

        entry.pack(
            fill="x",
            padx=25
        )

        current = (
            self.config_data.get(
                "steam_id_64",
                ""
            )
        )

        if current:

            entry.insert(
                0,
                current
            )

        help_label = (
            ctk.CTkLabel(
                dialog,
                text=(
                    t("steam_id_example")
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

        buttons = (
            ctk.CTkFrame(
                dialog,
                fg_color="transparent"
            )
        )

        buttons.pack(
            fill="x",
            padx=25,
            pady=25
        )

        save_button = (
            ctk.CTkButton(
                buttons,
                text=t("save"),
                command=lambda:
                    self.save_steam_settings(
                        dialog,
                        entry
                    )
            )
        )

        save_button.pack(
            side="left"
        )

        cancel_button = (
            ctk.CTkButton(
                buttons,
                text=t("cancel"),
                fg_color="transparent",
                border_width=1,
                command=
                    dialog.destroy
            )
        )

        cancel_button.pack(
            side="right"
        )


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
                t("invalid_steam_id_title"),
                (
                    t("invalid_steam_id_message")
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
                t("error_title"),
                (
                    t(
                        "save_config_error",
                        details=e
                    )
                ),
                parent=dialog
            )

            return

        self.update_steam_account_status()

        self.status_label.configure(
            text=(
                t(
                    "steam_account_saved"
                )
            )
        )

        dialog.destroy()


    # ========================================================
    # JANELA INTEGRAÇÃO PLAYNITE
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
            t("playnite_integration_title")
        )

        dialog.geometry(
            "720x560"
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
                text=(
                    t("playnite_integration_title")
                ),
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

        # ----------------------------------------------------
        # PLAYNITE
        # ----------------------------------------------------

        if status[
            "playnite_installed"
        ]:

            playnite_text = (
                t("integration_playnite_found")
            )

        else:

            playnite_text = (
                t("integration_playnite_not_found")
            )

        # ----------------------------------------------------
        # PLUGIN
        # ----------------------------------------------------

        if status[
            "plugin_installed"
        ]:

            plugin_text = (
                t("integration_plugin_installed")
            )

        else:

            plugin_text = (
                t("integration_plugin_not_installed")
            )

        # ----------------------------------------------------
        # BIBLIOTECA
        # ----------------------------------------------------

        if status[
            "export_exists"
        ]:

            library_text = (
                t("integration_library_synced")
            )

        else:

            library_text = (
                t("integration_library_not_synced")
            )

        info = (
            ctk.CTkLabel(
                dialog,
                text=(
                    f"{playnite_text}\n\n"
                    f"{plugin_text}\n\n"
                    f"{library_text}\n\n"
                    f"{t('integration_last_sync')}"
                    f"{format_datetime(status['export_modified'])}"
                ),
                justify="left",
                anchor="w"
            )
        )

        info.pack(
            fill="x",
            padx=25,
            pady=5
        )

        # ----------------------------------------------------
        # AVISO RECURSO
        # ----------------------------------------------------

        if not status[
            "bundled_plugin_available"
        ]:

            resource_warning = (
                ctk.CTkLabel(
                    dialog,
                    text=(
                        t(
                            "integration_plugin_files_missing"
                        )
                    ),
                    text_color="#e6b450",
                    justify="left"
                )
            )

            resource_warning.pack(
                anchor="w",
                padx=25,
                pady=(
                    15,
                    0
                )
            )

        # ----------------------------------------------------
        # RESTART REQUIRED
        # ----------------------------------------------------

        if self.plugin_restart_required:

            restart_label = (
                ctk.CTkLabel(
                    dialog,
                    text=(
                        t(
                            "integration_restart_required"
                        )
                    ),
                    text_color="#e6b450",
                    justify="left"
                )
            )

            restart_label.pack(
                anchor="w",
                padx=25,
                pady=(
                    15,
                    0
                )
            )

        # ----------------------------------------------------
        # BOTÕES
        # ----------------------------------------------------

        buttons = (
            ctk.CTkFrame(
                dialog,
                fg_color="transparent"
            )
        )

        buttons.pack(
            fill="x",
            side="bottom",
            padx=25,
            pady=25
        )

        if status[
            "plugin_installed"
        ]:

            install_text = (
                t("reinstall_plugin")
            )

        else:

            install_text = (
                t("install_plugin")
            )

        install_button = (
            ctk.CTkButton(
                buttons,
                text=install_text,
                command=lambda:
                    self.install_plugin_from_gui(
                        dialog
                    )
            )
        )

        install_button.pack(
            side="left"
        )

        if (
            not status[
                "playnite_installed"
            ]
            or
            not status[
                "bundled_plugin_available"
            ]
        ):

            install_button.configure(
                state="disabled"
            )

        verify_button = (
            ctk.CTkButton(
                buttons,
                text=t("check_again"),
                fg_color="transparent",
                border_width=1,
                command=lambda:
                    self.refresh_integration_dialog(
                        dialog
                    )
            )
        )

        verify_button.pack(
            side="left",
            padx=10
        )

        close_button = (
            ctk.CTkButton(
                buttons,
                text=t("close"),
                fg_color="transparent",
                border_width=1,
                command=
                    dialog.destroy
            )
        )

        close_button.pack(
            side="right"
        )


    # ========================================================
    # INSTALAÇÃO PELA GUI
    # ========================================================

    def install_plugin_from_gui(
        self,
        dialog
    ):

        running = (
            is_playnite_running()
        )

        if running:

            proceed = (
                messagebox.askyesno(
                    t("playnite_running_title"),
                    (
                        t("playnite_running_install_message")
                    ),
                    parent=dialog
                )
            )

            if not proceed:
                return

        else:

            proceed = (
                messagebox.askyesno(
                    t("install_integration_title"),
                    (
                        t("install_integration_message")
                    ),
                    parent=dialog
                )
            )

            if not proceed:
                return

        try:

            install_playnite_plugin()

        except Exception as e:

            messagebox.showerror(
                t("install_error_title"),
                str(
                    e
                ),
                parent=dialog
            )

            return

        self.plugin_restart_required = (
            True
        )

        self.update_integration_status_ui()

        messagebox.showinfo(
            t("plugin_installed_title"),
            (
                t("plugin_installed_message")
            ),
            parent=dialog
        )

        dialog.destroy()

        self.show_integration_info()


    # ========================================================
    # REFRESH DIALOG
    # ========================================================

    def refresh_integration_dialog(
        self,
        dialog
    ):

        self.update_integration_status_ui()

        dialog.destroy()

        self.show_integration_info()


    # ========================================================
    # ATUALIZAÇÃO
    # ========================================================

    def start_refresh(
        self
    ):

        if self.loading:
            return

        self.update_integration_status_ui()

        steam_id = (
            self.config_data.get(
                "steam_id_64",
                ""
            )
        )

        if not is_valid_steam_id_64(
            steam_id
        ):

            messagebox.showwarning(
                t("steam_account_title"),
                t("configure_steam_before_refresh")
            )

            self.show_steam_settings()

            return

        status = (
            self.integration_status
        )

        if not status[
            "plugin_installed"
        ]:

            messagebox.showwarning(
                t("playnite_integration_button"),
                t("plugin_not_installed_warning")
            )

            self.show_integration_info()

            return

        if not PLAYNITE_EXPORT_FILE.exists():

            messagebox.showwarning(
                "Playnite",
                t("library_not_synced_warning")
            )

            return

        self.loading = (
            True
        )

        self.refresh_button.configure(
            state="disabled",
            text=t("updating")
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

            self.event_queue.put(
                (
                    "status",
                    t("reading_playnite_library")
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

            self.event_queue.put(
                (
                    "status",
                    t("getting_steam_wishlist")
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
                len(
                    appids
                )
            )

            self.event_queue.put(
                (
                    "wishlist_total",
                    total
                )
            )

            wishlist = {}

            failures = 0

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
                    ] = (
                        appid
                    )

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

            self.event_queue.put(
                (
                    "status",
                    t("comparing_libraries")
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
                            matches
                    }
                )
            )

        except Exception as e:

            self.event_queue.put(
                (
                    "error",
                    str(
                        e
                    )
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
                            t(
                                "getting_steam_names",
                                current=data["current"],
                                total=data["total"]
                            )
                        )
                    )

                elif event == "wishlist_total":

                    self.wishlist_total = (
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

                    self.wishlist_total = (
                        data[
                            "wishlist_total"
                        ]
                    )

                    self.card_wishlist.configure(
                        text=str(
                            self.wishlist_total
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
                            t(
                                "status_steam_games_identified",
                                count=len(
                                    self.wishlist
                                )
                            )
                        ),
                        text_color=COLOR_SUCCESS
                    )

                    self.update_source_filter()

                    self.apply_filters()

                    self.progress_bar.set(
                        1
                    )

                    self.status_label.configure(
                        text=(
                            t(
                                "refresh_complete",
                                count=len(
                                    self.matches
                                )
                            )
                        )
                    )

                    self.loading = (
                        False
                    )

                    self.refresh_button.configure(
                        state="normal",
                        text=f"↻  {t('refresh_library')}"
                    )

                    self.update_integration_status_ui()

                elif event == "error":

                    self.loading = (
                        False
                    )

                    self.refresh_button.configure(
                        state="normal",
                        text=f"↻  {t('refresh_library')}"
                    )

                    self.progress_bar.set(
                        0
                    )

                    self.status_label.configure(
                        text=(
                            t(
                                "refresh_error"
                            )
                        )
                    )

                    messagebox.showerror(
                        t("error_title"),
                        data
                    )

        except queue.Empty:
            pass

        self.after(
            100,
            self.process_event_queue
        )


    # ========================================================
    # FILTRO DE SOURCE
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
                t("all_libraries")
            ]
            +
            sources
        )

        self.source_filter.configure(
            values=values
        )

        self.source_filter.set(
            t("all_libraries")
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

                if search not in haystack:
                    continue

            if (
                source_filter
                !=
                t("all_libraries")
            ):

                if (
                    item[
                        "source"
                    ]
                    !=
                    source_filter
                ):

                    continue

            if (
                match_filter
                !=
                t("all_matches")
            ):

                expected_type = (
                    "Exato"
                    if match_filter
                    ==
                    t("exact_match")
                    else
                    "Aproximado"
                )

                if (
                    item[
                        "type"
                    ]
                    !=
                    expected_type
                ):

                    continue

            filtered.append(
                item
            )

        self.populate_table(
            filtered
        )

        self.result_count_label.configure(
            text=t(
                "result_count",
                shown=len(
                    filtered
                ),
                found=len(
                    self.matches
                )
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

        for index, item in enumerate(
            matches
        ):

            row_tag = (
                "row_even"
                if index % 2 == 0
                else
                "row_odd"
            )

            match_text = (
                t("match_exact_short")
                if item[
                    "type"
                ] == "Exato"
                else
                t("match_approx_short")
            )

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

                    match_text,

                    f"{item['score']:.1f}%"
                ),
                tags=(
                    item[
                        "appid"
                    ],
                    row_tag
                )
            )

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
            selected[
                0
            ]
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
            tags[
                0
            ]
        )

        webbrowser.open(
            "https://store.steampowered.com/"
            f"app/{appid}/"
        )


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":

    app = (
        WishlistApp()
    )

    app.mainloop()