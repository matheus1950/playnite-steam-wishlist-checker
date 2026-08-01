import os
import re
import json
import time
import queue
import threading
import webbrowser
from pathlib import Path
from tkinter import ttk, messagebox

import customtkinter as ctk
import requests
from rapidfuzz import process, fuzz


# ============================================================
# CONFIGURAÇÕES
# ============================================================

STEAM_ID_64 = "76561198349875986"

FUZZY_SCORE_CUTOFF = 85

# Mantemos a regra atual:
# jogos da própria Steam não entram na comparação.
IGNORE_STEAM_SOURCE = True

STEAM_APP_REQUEST_DELAY = 0.08


PLAYNITE_EXPORT_FILE = Path(
    os.path.expandvars(
        r"%APPDATA%\Playnite\steam_wishlist_checker_library.json"
    )
)


# ============================================================
# COMANDO PARA EXPORTAÇÃO MANUAL DO PLAYNITE
# ============================================================

PLAYNITE_EXPORT_COMMAND = (
    '$PlayniteApi.Database.Games | '
    'ForEach-Object { '
    '[PSCustomObject]@{ '
    'Name=$_.Name; '
    'Source=if ($_.Source) {$_.Source.Name} else {""}; '
    'PluginId="$($_.PluginId)"; '
    'GameId="$($_.GameId)"; '
    'IsInstalled=$_.IsInstalled; '
    'Hidden=$_.Hidden '
    '} } | '
    'ConvertTo-Json -Depth 4 | '
    'Set-Content '
    '"$env:APPDATA\\Playnite\\'
    'steam_wishlist_checker_library.json" '
    '-Encoding UTF8'
)


# ============================================================
# APARÊNCIA
# ============================================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ============================================================
# NORMALIZAÇÃO DOS NOMES
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

    title = title.replace("&", " and ")

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
# PLAYNITE
# ============================================================

def read_playnite_export():
    """
    Lê o JSON previamente criado pelo SDK Interativo
    PowerShell do Playnite.
    """

    if not PLAYNITE_EXPORT_FILE.exists():
        raise FileNotFoundError(
            "O arquivo exportado pelo Playnite não foi encontrado."
        )

    try:
        with PLAYNITE_EXPORT_FILE.open(
            "r",
            encoding="utf-8-sig"
        ) as f:
            data = json.load(f)

    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"O JSON exportado pelo Playnite é inválido:\n{e}"
        )

    except Exception as e:
        raise RuntimeError(
            f"Não foi possível ler o arquivo do Playnite:\n{e}"
        )

    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list):
        raise RuntimeError(
            "Formato inesperado no arquivo exportado pelo Playnite."
        )

    games = []

    for item in data:
        if not isinstance(item, dict):
            continue

        name = str(
            item.get("Name", "")
            or ""
        ).strip()

        if not name:
            continue

        games.append({
            "name": name,

            "source": str(
                item.get("Source", "")
                or ""
            ).strip(),

            "plugin_id": str(
                item.get("PluginId", "")
                or ""
            ).strip(),

            "game_id": str(
                item.get("GameId", "")
                or ""
            ).strip(),

            "installed": bool(
                item.get(
                    "IsInstalled",
                    False
                )
            ),

            "hidden": bool(
                item.get(
                    "Hidden",
                    False
                )
            ),
        })

    return games


# ============================================================
# FONTES DO PLAYNITE
# ============================================================

def get_source_counts(games):
    counts = {}

    for game in games:
        source = (
            game.get("source")
            or
            "Sem fonte"
        )

        counts[source] = (
            counts.get(source, 0)
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
            game.get("source")
            or
            ""
        ).strip().lower()

        if source == "steam":
            continue

        filtered.append(game)

    return filtered


# ============================================================
# STEAM
# ============================================================

def create_steam_session():
    session = requests.Session()

    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0.0.0 "
            "Safari/537.36"
        ),

        "Accept": (
            "application/json,"
            "text/plain,"
            "*/*"
        ),
    })

    return session


# ============================================================
# APPIDS DA WISHLIST
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
        "input_json": json.dumps({
            "steamid": steam_id
        })
    }

    response = session.get(
        url,
        params=params,
        timeout=30
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"A Steam respondeu com HTTP "
            f"{response.status_code}."
        )

    try:
        data = response.json()

    except requests.exceptions.JSONDecodeError:
        raise RuntimeError(
            "A Steam não retornou JSON válido."
        )

    items = (
        data
        .get("response", {})
        .get("items", [])
    )

    appids = []

    for item in items:
        if not isinstance(item, dict):
            continue

        appid = item.get("appid")

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
# APPID -> NOME
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
        "appids": appid,
        "l": "english",
        "cc": "br"
    }

    try:
        response = session.get(
            url,
            params=params,
            timeout=20
        )

        if response.status_code != 200:
            return None

        data = response.json()

        app_data = data.get(
            str(appid)
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
            .get("data", {})
            .get("name")
        )

        if isinstance(name, str):
            return name.strip()

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
        normalized = clean_title(
            game["name"]
        )

        if not normalized:
            continue

        normalized_playnite.setdefault(
            normalized,
            []
        )

        normalized_playnite[
            normalized
        ].append(game)

    exact_matches = []
    fuzzy_matches = []

    for wishlist_name, appid in wishlist.items():

        normalized = clean_title(
            wishlist_name
        )

        # ----------------------------------------------------
        # MATCH EXATO
        # ----------------------------------------------------

        if normalized in normalized_playnite:

            for game in normalized_playnite[
                normalized
            ]:

                exact_matches.append({
                    "wishlist": wishlist_name,
                    "appid": appid,
                    "playnite": game["name"],
                    "source": (
                        game["source"]
                        or
                        "Sem fonte"
                    ),
                    "score": 100.0,
                    "type": "Exato"
                })

            continue

        # ----------------------------------------------------
        # MATCH FUZZY
        # ----------------------------------------------------

        if not normalized_playnite:
            continue

        match = process.extractOne(
            normalized,
            normalized_playnite.keys(),
            scorer=fuzz.token_sort_ratio,
            score_cutoff=(
                FUZZY_SCORE_CUTOFF
            )
        )

        if not match:
            continue

        matched_key = match[0]
        score = match[1]

        for game in normalized_playnite[
            matched_key
        ]:

            fuzzy_matches.append({
                "wishlist": wishlist_name,
                "appid": appid,
                "playnite": game["name"],
                "source": (
                    game["source"]
                    or
                    "Sem fonte"
                ),
                "score": score,
                "type": "Aproximado"
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

    return exact_matches, fuzzy_matches


# ============================================================
# GUI
# ============================================================

class WishlistApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        # ----------------------------------------------------
        # JANELA
        # ----------------------------------------------------

        self.title(
            "Steam Wishlist × Playnite"
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

        self.event_queue = queue.Queue()

        self.loading = False

        self.playnite_games = []

        self.filtered_playnite_games = []

        self.wishlist = {}

        self.matches = []

        self.source_counts = {}

        self.total_wishlist_appids = 0

        self.failed_steam_names = 0

        # ----------------------------------------------------
        # GRID PRINCIPAL
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
        # SIDEBAR
        # ----------------------------------------------------

        self.create_sidebar()

        # ----------------------------------------------------
        # CONTEÚDO
        # ----------------------------------------------------

        self.create_main_area()

        # ----------------------------------------------------
        # TREEVIEW STYLE
        # ----------------------------------------------------

        self.configure_treeview_style()

        # ----------------------------------------------------
        # FILA THREAD
        # ----------------------------------------------------

        self.after(
            100,
            self.process_event_queue
        )

        # ----------------------------------------------------
        # CARREGA APENAS PLAYNITE AO ABRIR
        # ----------------------------------------------------

        self.after(
            300,
            self.initial_load
        )


    # ========================================================
    # SIDEBAR
    # ========================================================

    def create_sidebar(self):

        self.sidebar = ctk.CTkFrame(
            self,
            width=240,
            corner_radius=0
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

        title = ctk.CTkLabel(
            self.sidebar,
            text="Wishlist\nChecker",
            font=ctk.CTkFont(
                size=27,
                weight="bold"
            ),
            justify="left"
        )

        title.pack(
            anchor="w",
            padx=25,
            pady=(
                30,
                5
            )
        )

        subtitle = ctk.CTkLabel(
            self.sidebar,
            text="Steam × Playnite",
            font=ctk.CTkFont(
                size=14
            ),
            text_color="gray70"
        )

        subtitle.pack(
            anchor="w",
            padx=25,
            pady=(
                0,
                30
            )
        )

        # ----------------------------------------------------
        # BOTÃO ATUALIZAR
        # ----------------------------------------------------

        self.refresh_button = ctk.CTkButton(
            self.sidebar,
            text="Atualizar dados",
            height=42,
            command=self.start_refresh
        )

        self.refresh_button.pack(
            fill="x",
            padx=20,
            pady=8
        )

        # ----------------------------------------------------
        # SDK
        # ----------------------------------------------------

        sdk_button = ctk.CTkButton(
            self.sidebar,
            text="Como atualizar Playnite",
            height=40,
            fg_color="transparent",
            border_width=1,
            command=self.show_sdk_instructions
        )

        sdk_button.pack(
            fill="x",
            padx=20,
            pady=8
        )

        # ----------------------------------------------------
        # INFORMAÇÕES
        # ----------------------------------------------------

        separator = ctk.CTkFrame(
            self.sidebar,
            height=1
        )

        separator.pack(
            fill="x",
            padx=20,
            pady=20
        )

        info_title = ctk.CTkLabel(
            self.sidebar,
            text="Status",
            font=ctk.CTkFont(
                size=15,
                weight="bold"
            )
        )

        info_title.pack(
            anchor="w",
            padx=25
        )

        self.playnite_status_label = (
            ctk.CTkLabel(
                self.sidebar,
                text="Playnite: —",
                anchor="w",
                justify="left"
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

        self.steam_status_label = (
            ctk.CTkLabel(
                self.sidebar,
                text="Steam: —",
                anchor="w",
                justify="left"
            )
        )

        self.steam_status_label.pack(
            fill="x",
            padx=25,
            pady=2
        )

        # ----------------------------------------------------
        # ARQUIVO
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
    # MAIN AREA
    # ========================================================

    def create_main_area(self):

        self.main_frame = ctk.CTkFrame(
            self,
            corner_radius=0,
            fg_color="transparent"
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

        header = ctk.CTkFrame(
            self.main_frame,
            fg_color="transparent"
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

        title = ctk.CTkLabel(
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

        title.pack(
            side="left"
        )

        # ----------------------------------------------------
        # CARDS
        # ----------------------------------------------------

        cards = ctk.CTkFrame(
            self.main_frame,
            fg_color="transparent"
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

        self.card_playnite = self.create_card(
            cards,
            0,
            "Playnite",
            "—"
        )

        self.card_wishlist = self.create_card(
            cards,
            1,
            "Wishlist Steam",
            "—"
        )

        self.card_matches = self.create_card(
            cards,
            2,
            "Já possui",
            "—"
        )

        self.card_unresolved = self.create_card(
            cards,
            3,
            "Não identificados",
            "—"
        )

        # ----------------------------------------------------
        # FILTROS
        # ----------------------------------------------------

        filters = ctk.CTkFrame(
            self.main_frame
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

        self.search_entry = ctk.CTkEntry(
            filters,
            placeholder_text=(
                "Pesquisar jogo..."
            ),
            height=38
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

        table_frame = ctk.CTkFrame(
            self.main_frame
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

        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            selectmode="browse"
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

        scrollbar = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.tree.yview
        )

        self.tree.configure(
            yscrollcommand=(
                scrollbar.set
            )
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
        # BARRA INFERIOR
        # ----------------------------------------------------

        footer = ctk.CTkFrame(
            self.main_frame,
            fg_color="transparent"
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

        self.progress_bar.set(0)


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

        frame = ctk.CTkFrame(
            parent
        )

        frame.grid(
            row=0,
            column=column,
            sticky="ew",
            padx=(
                0 if column == 0 else 6,
                0 if column == 3 else 6
            )
        )

        label_title = (
            ctk.CTkLabel(
                frame,
                text=title,
                text_color="gray70",
                font=ctk.CTkFont(
                    size=13
                )
            )
        )

        label_title.pack(
            anchor="w",
            padx=18,
            pady=(
                15,
                2
            )
        )

        label_value = (
            ctk.CTkLabel(
                frame,
                text=value,
                font=ctk.CTkFont(
                    size=26,
                    weight="bold"
                )
            )
        )

        label_value.pack(
            anchor="w",
            padx=18,
            pady=(
                0,
                15
            )
        )

        return label_value


    # ========================================================
    # TREEVIEW STYLE
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

        style.map(
            "Treeview.Heading",
            background=[
                (
                    "active",
                    "#3b3b3b"
                )
            ]
        )


    # ========================================================
    # PRIMEIRO LOAD
    # ========================================================

    def initial_load(self):

        try:
            games = read_playnite_export()

            self.playnite_games = games

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

            self.playnite_status_label.configure(
                text=(
                    f"Playnite: ✓ "
                    f"{len(games)} jogos"
                )
            )

            try:
                size = (
                    PLAYNITE_EXPORT_FILE
                    .stat()
                    .st_size
                    /
                    1024
                )

                self.file_status_label.configure(
                    text=(
                        f"Exportação Playnite\n"
                        f"{size:.1f} KB"
                    )
                )

            except Exception:
                pass

            self.status_label.configure(
                text=(
                    "Playnite carregado. "
                    "Clique em Atualizar dados "
                    "para consultar a Steam."
                )
            )

        except FileNotFoundError:

            self.playnite_status_label.configure(
                text="Playnite: arquivo ausente"
            )

            self.show_sdk_instructions()

        except Exception as e:

            messagebox.showerror(
                "Erro no Playnite",
                str(e)
            )


    # ========================================================
    # ATUALIZAÇÃO
    # ========================================================

    def start_refresh(self):

        if self.loading:
            return

        self.loading = True

        self.refresh_button.configure(
            state="disabled",
            text="Atualizando..."
        )

        self.progress_bar.set(0)

        thread = threading.Thread(
            target=self.refresh_worker,
            daemon=True
        )

        thread.start()


    # ========================================================
    # WORKER
    # ========================================================

    def refresh_worker(self):

        try:
            # ------------------------------------------------
            # PLAYNITE
            # ------------------------------------------------

            self.event_queue.put(
                (
                    "status",
                    "Lendo biblioteca do Playnite..."
                )
            )

            games = read_playnite_export()

            filtered_games = (
                filter_playnite_games(
                    games
                )
            )

            source_counts = (
                get_source_counts(
                    games
                )
            )

            self.event_queue.put(
                (
                    "playnite_loaded",
                    {
                        "games": games,
                        "filtered": filtered_games,
                        "sources": source_counts
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
                    STEAM_ID_64,
                    session
                )
            )

            total = len(appids)

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

            for index, appid in enumerate(
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
                            "value": progress,
                            "current": index,
                            "total": total
                        }
                    )
                )

                time.sleep(
                    STEAM_APP_REQUEST_DELAY
                )

            # ------------------------------------------------
            # MATCHING
            # ------------------------------------------------

            self.event_queue.put(
                (
                    "status",
                    "Comparando bibliotecas..."
                )
            )

            exact, fuzzy = (
                compare_games(
                    wishlist,
                    filtered_games
                )
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
                        "wishlist": wishlist,
                        "wishlist_total": total,
                        "failures": failures,
                        "matches": matches,
                        "exact": exact,
                        "fuzzy": fuzzy
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
    # PROCESSA FILA
    # ========================================================

    def process_event_queue(self):

        try:
            while True:

                event, data = (
                    self.event_queue.get_nowait()
                )

                if event == "status":

                    self.status_label.configure(
                        text=data
                    )

                elif event == "progress":

                    self.progress_bar.set(
                        data["value"]
                    )

                    self.status_label.configure(
                        text=(
                            "Obtendo nomes da Steam: "
                            f"{data['current']}/"
                            f"{data['total']}"
                        )
                    )

                elif event == "wishlist_total":

                    self.total_wishlist_appids = data

                    self.card_wishlist.configure(
                        text=str(data)
                    )

                    self.steam_status_label.configure(
                        text=(
                            f"Steam: {data} AppIDs"
                        )
                    )

                elif event == "playnite_loaded":

                    self.playnite_games = (
                        data["games"]
                    )

                    self.filtered_playnite_games = (
                        data["filtered"]
                    )

                    self.source_counts = (
                        data["sources"]
                    )

                    self.card_playnite.configure(
                        text=str(
                            len(
                                self.playnite_games
                            )
                        )
                    )

                    self.playnite_status_label.configure(
                        text=(
                            "Playnite: ✓ "
                            f"{len(self.playnite_games)} jogos"
                        )
                    )

                elif event == "complete":

                    self.wishlist = (
                        data["wishlist"]
                    )

                    self.failed_steam_names = (
                        data["failures"]
                    )

                    self.matches = (
                        data["matches"]
                    )

                    self.card_wishlist.configure(
                        text=str(
                            data["wishlist_total"]
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

                    self.progress_bar.set(1)

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

                elif event == "error":

                    self.loading = False

                    self.refresh_button.configure(
                        state="normal",
                        text="Atualizar dados"
                    )

                    self.progress_bar.set(0)

                    self.status_label.configure(
                        text="Erro durante a atualização."
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
    # ATUALIZA FILTRO DE FONTES
    # ========================================================

    def update_source_filter(self):

        sources = sorted({
            item["source"]
            for item in self.matches
        })

        values = (
            ["Todas as bibliotecas"]
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

    def apply_filters(self):

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

            # ------------------------------------------------
            # PESQUISA
            # ------------------------------------------------

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

            # ------------------------------------------------
            # SOURCE
            # ------------------------------------------------

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

            # ------------------------------------------------
            # MATCH
            # ------------------------------------------------

            if match_filter != "Todos":

                if (
                    item["type"]
                    !=
                    match_filter
                ):
                    continue

            filtered.append(item)

        self.populate_table(
            filtered
        )

        self.result_count_label.configure(
            text=(
                f"{len(filtered)} resultado(s) exibido(s) "
                f"de {len(self.matches)} encontrado(s)."
            )
        )


    # ========================================================
    # POPULA TABELA
    # ========================================================

    def populate_table(
        self,
        matches
    ):

        for row in self.tree.get_children():

            self.tree.delete(
                row
            )

        for item in matches:

            self.tree.insert(
                "",
                "end",
                values=(
                    item["wishlist"],
                    item["playnite"],
                    item["source"],
                    item["type"],
                    f"{item['score']:.1f}%"
                ),
                tags=(
                    item["appid"],
                )
            )


    # ========================================================
    # ABRE PÁGINA STEAM
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

        item_id = selected[0]

        tags = self.tree.item(
            item_id,
            "tags"
        )

        if not tags:
            return

        appid = tags[0]

        url = (
            "https://store.steampowered.com/"
            f"app/{appid}/"
        )

        webbrowser.open(url)


    # ========================================================
    # INSTRUÇÕES SDK
    # ========================================================

    def show_sdk_instructions(self):

        dialog = ctk.CTkToplevel(
            self
        )

        dialog.title(
            "Atualizar biblioteca do Playnite"
        )

        dialog.geometry(
            "800x500"
        )

        dialog.transient(
            self
        )

        title = ctk.CTkLabel(
            dialog,
            text=(
                "Atualização manual do Playnite"
            ),
            font=ctk.CTkFont(
                size=22,
                weight="bold"
            )
        )

        title.pack(
            anchor="w",
            padx=25,
            pady=(
                25,
                10
            )
        )

        instructions = ctk.CTkLabel(
            dialog,
            text=(
                "1. Abra o Playnite.\n"
                "2. Vá em Extensões → SDK Interativo PowerShell.\n"
                "3. Use Ctrl+V e Enter para inicializar "
                "$PlayniteApi.\n"
                "4. Execute o comando abaixo.\n"
                "5. Volte ao aplicativo e clique em "
                "\"Atualizar dados\"."
            ),
            justify="left",
            anchor="w"
        )

        instructions.pack(
            fill="x",
            padx=25,
            pady=(
                0,
                15
            )
        )

        textbox = ctk.CTkTextbox(
            dialog,
            height=220,
            wrap="word"
        )

        textbox.pack(
            fill="both",
            expand=True,
            padx=25,
            pady=(
                0,
                15
            )
        )

        textbox.insert(
            "1.0",
            PLAYNITE_EXPORT_COMMAND
        )

        textbox.configure(
            state="disabled"
        )

        button_frame = ctk.CTkFrame(
            dialog,
            fg_color="transparent"
        )

        button_frame.pack(
            fill="x",
            padx=25,
            pady=(
                0,
                25
            )
        )

        copy_button = ctk.CTkButton(
            button_frame,
            text="Copiar comando",
            command=lambda:
                self.copy_sdk_command()
        )

        copy_button.pack(
            side="left"
        )

        close_button = ctk.CTkButton(
            button_frame,
            text="Fechar",
            fg_color="transparent",
            border_width=1,
            command=dialog.destroy
        )

        close_button.pack(
            side="right"
        )


    # ========================================================
    # COPIA COMANDO
    # ========================================================

    def copy_sdk_command(self):

        self.clipboard_clear()

        self.clipboard_append(
            PLAYNITE_EXPORT_COMMAND
        )

        self.update()

        messagebox.showinfo(
            "Copiado",
            "Comando copiado para a área de transferência."
        )


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":

    app = WishlistApp()

    app.mainloop()