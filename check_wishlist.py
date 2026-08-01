import os
import re
import json
import time
from pathlib import Path

import requests
from rapidfuzz import process, fuzz


# ============================================================
# CONFIGURAÇÕES
# ============================================================

STEAM_ID_64 = "76561198349875986"

FUZZY_SCORE_CUTOFF = 85

# True = ignora jogos cuja fonte no Playnite é Steam.
# Assim encontramos jogos da wishlist Steam que você
# já possui em outras bibliotecas.
IGNORE_STEAM_SOURCE = True

STEAM_APP_REQUEST_DELAY = 0.08

PLAYNITE_EXPORT_FILE = Path(
    os.path.expandvars(
        r"%APPDATA%\Playnite\steam_wishlist_checker_library.json"
    )
)


# ============================================================
# NORMALIZAÇÃO DE TÍTULOS
# ============================================================

def clean_title(title: str) -> str:
    """
    Normaliza nomes para comparação.
    """

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
# LEITURA DA BIBLIOTECA DO PLAYNITE
# ============================================================

def read_playnite_export():
    """
    Lê o JSON criado através do SDK Interativo
    PowerShell do Playnite.
    """

    print("\n" + "=" * 70)
    print("PLAYNITE")
    print("=" * 70)

    print("\nArquivo de biblioteca:")

    print(
        PLAYNITE_EXPORT_FILE
    )

    if not PLAYNITE_EXPORT_FILE.exists():

        print("\n")
        print("=" * 70)
        print("ARQUIVO DO PLAYNITE NÃO ENCONTRADO")
        print("=" * 70)

        print(
            "\nO arquivo de exportação ainda não existe."
        )

        print(
            "\nNo Playnite, abra:"
        )

        print(
            "\nExtensões -> SDK Interativo PowerShell"
        )

        print(
            "\nE execute SOMENTE este comando:"
        )

        print()

        print(
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

        return None

    try:

        size = PLAYNITE_EXPORT_FILE.stat().st_size

        print(
            f"\nTamanho do arquivo: "
            f"{size / 1024:.1f} KB"
        )

    except Exception:
        pass

    try:

        with PLAYNITE_EXPORT_FILE.open(
            "r",
            encoding="utf-8-sig"
        ) as f:

            data = json.load(f)

    except json.JSONDecodeError as e:

        raise RuntimeError(
            "O arquivo do Playnite foi encontrado, "
            "mas o JSON está inválido.\n\n"
            f"Erro: {e}"
        )

    except Exception as e:

        raise RuntimeError(
            "Não consegui ler o arquivo exportado "
            "do Playnite.\n\n"
            f"Erro: {e}"
        )

    # PowerShell pode gerar objeto em vez de array
    # quando existe apenas um resultado.
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
            "O JSON do Playnite possui um formato inesperado."
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

        source = str(
            item.get(
                "Source",
                ""
            )
            or
            ""
        ).strip()

        plugin_id = str(
            item.get(
                "PluginId",
                ""
            )
            or
            ""
        ).strip()

        game_id = str(
            item.get(
                "GameId",
                ""
            )
            or
            ""
        ).strip()

        games.append({
            "name": name,
            "source": source,
            "plugin_id": plugin_id,
            "game_id": game_id,
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

    print(
        f"\nJogos carregados do Playnite: "
        f"{len(games)}"
    )

    return games


# ============================================================
# MOSTRA / FILTRA FONTES
# ============================================================

def filter_playnite_games(
    games
):
    """
    Exibe quantidade por biblioteca e,
    opcionalmente, remove a própria Steam.
    """

    print("\n" + "=" * 70)
    print("BIBLIOTECAS DO PLAYNITE")
    print("=" * 70)

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

    print()

    for source in sorted(
        counts,
        key=lambda x: x.lower()
    ):

        print(
            f"  {source}: "
            f"{counts[source]}"
        )

    if not IGNORE_STEAM_SOURCE:

        print(
            "\nA biblioteca Steam também será "
            "considerada na comparação."
        )

        return games

    filtered = []

    steam_ignored = 0

    for game in games:

        source = (
            game.get(
                "source"
            )
            or
            ""
        ).strip().lower()

        if source == "steam":

            steam_ignored += 1

            continue

        filtered.append(
            game
        )

    print(
        f"\nJogos da Steam ignorados: "
        f"{steam_ignored}"
    )

    print(
        f"Jogos de outras bibliotecas: "
        f"{len(filtered)}"
    )

    return filtered


# ============================================================
# SESSÃO HTTP DA STEAM
# ============================================================

def create_steam_session():
    """
    Cria uma sessão reutilizável.
    """

    session = requests.Session()

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
# APPIDS DA WISHLIST
# ============================================================

def get_steam_wishlist_appids(
    steam_id,
    session
):
    """
    Obtém os AppIDs da wishlist.
    """

    print("\n" + "=" * 70)
    print("STEAM WISHLIST")
    print("=" * 70)

    url = (
        "https://api.steampowered.com/"
        "IWishlistService/GetWishlist/v1/"
    )

    params = {
        "input_json": json.dumps({
            "steamid": steam_id
        })
    }

    print(
        "\nObtendo wishlist..."
    )

    response = session.get(
        url,
        params=params,
        timeout=30
    )

    print(
        f"HTTP: "
        f"{response.status_code}"
    )

    if response.status_code != 200:

        raise RuntimeError(
            f"A Steam retornou HTTP "
            f"{response.status_code}.\n\n"
            f"{response.text[:1000]}"
        )

    try:

        data = response.json()

    except requests.exceptions.JSONDecodeError:

        raise RuntimeError(
            "A Steam não retornou JSON válido.\n\n"
            f"{response.text[:1000]}"
        )

    response_data = (
        data.get(
            "response",
            {}
        )
    )

    items = (
        response_data.get(
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

        appid = item.get(
            "appid"
        )

        if appid is not None:

            appids.append(
                str(appid)
            )

    # Remove duplicados mantendo ordem
    appids = list(
        dict.fromkeys(
            appids
        )
    )

    print(
        f"AppIDs encontrados: "
        f"{len(appids)}"
    )

    return appids


# ============================================================
# APPID -> NOME
# ============================================================

def get_steam_app_name(
    appid,
    session
):
    """
    Obtém nome de um jogo da Steam.
    """

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

        game_data = (
            app_data.get(
                "data",
                {}
            )
        )

        name = (
            game_data.get(
                "name"
            )
        )

        if isinstance(
            name,
            str
        ):

            return name.strip()

    except Exception:

        pass

    return None


# ============================================================
# WISHLIST COM NOMES
# ============================================================

def get_steam_wishlist(
    steam_id
):
    """
    Retorna:
        {
            "Nome do jogo": "appid"
        }
    """

    session = (
        create_steam_session()
    )

    appids = (
        get_steam_wishlist_appids(
            steam_id,
            session
        )
    )

    wishlist = {}

    total = len(
        appids
    )

    if total == 0:

        return wishlist

    print(
        "\nObtendo nomes dos jogos..."
    )

    failures = 0

    for index, appid in enumerate(
        appids,
        start=1
    ):

        print(
            f"\r  {index}/{total}",
            end="",
            flush=True
        )

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

        time.sleep(
            STEAM_APP_REQUEST_DELAY
        )

    print()

    print(
        f"\nJogos identificados: "
        f"{len(wishlist)}"
    )

    if failures:

        print(
            f"AppIDs sem nome: "
            f"{failures}"
        )

    return wishlist


# ============================================================
# COMPARAÇÃO
# ============================================================

def compare_games(
    wishlist,
    playnite_games
):
    """
    Primeiro tenta igualdade após normalização.
    Depois tenta fuzzy matching.
    """

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

        # ====================================================
        # MATCH EXATO NORMALIZADO
        # ====================================================

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
                            "Sem fonte"
                        ),

                    "score":
                        100.0

                })

            continue

        # ====================================================
        # MATCH APROXIMADO
        # ====================================================

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
                        "Sem fonte"
                    ),

                "score":
                    score

            })

    exact_matches.sort(
        key=lambda x:
            x["wishlist"].lower()
    )

    fuzzy_matches.sort(
        key=lambda x:
            (
                -x["score"],
                x["wishlist"].lower()
            )
    )

    return (
        exact_matches,
        fuzzy_matches
    )


# ============================================================
# RESULTADOS
# ============================================================

def show_results(
    exact_matches,
    fuzzy_matches
):
    """
    Exibe os jogos encontrados.
    """

    total = (
        len(exact_matches)
        +
        len(fuzzy_matches)
    )

    print("\n")
    print("=" * 70)

    print(
        "JOGOS DA WISHLIST STEAM QUE VOCÊ "
        "JÁ POSSUI EM OUTRA BIBLIOTECA"
    )

    print("=" * 70)

    print(
        f"\nTotal encontrado: "
        f"{total}"
    )

    if total == 0:

        print(
            "\nNenhuma correspondência encontrada."
        )

        return

    # ========================================================
    # EXATOS
    # ========================================================

    if exact_matches:

        print("\n")
        print("=" * 70)

        print(
            f"MATCHES EXATOS "
            f"({len(exact_matches)})"
        )

        print("=" * 70)

        for item in exact_matches:

            print()

            print(
                f"[Steam Wishlist] "
                f"{item['wishlist']}"
            )

            print(
                f"[Playnite]       "
                f"{item['playnite']}"
            )

            print(
                f"[Biblioteca]     "
                f"{item['source']}"
            )

            print(
                "[Similaridade]    "
                "100%"
            )

    # ========================================================
    # FUZZY
    # ========================================================

    if fuzzy_matches:

        print("\n")
        print("=" * 70)

        print(
            f"MATCHES APROXIMADOS "
            f"({len(fuzzy_matches)})"
        )

        print("=" * 70)

        for item in fuzzy_matches:

            print()

            print(
                f"[Steam Wishlist] "
                f"{item['wishlist']}"
            )

            print(
                f"[Playnite]       "
                f"{item['playnite']}"
            )

            print(
                f"[Biblioteca]     "
                f"{item['source']}"
            )

            print(
                f"[Similaridade]   "
                f"{item['score']:.1f}%"
            )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("STEAM WISHLIST x PLAYNITE")
    print("=" * 70)

    try:

        # ====================================================
        # PLAYNITE
        # ====================================================

        games = (
            read_playnite_export()
        )

        if not games:

            return

        games = (
            filter_playnite_games(
                games
            )
        )

        if not games:

            print(
                "\nNenhum jogo de outra "
                "biblioteca disponível."
            )

            return

        # ====================================================
        # STEAM
        # ====================================================

        wishlist = (
            get_steam_wishlist(
                STEAM_ID_64
            )
        )

        if not wishlist:

            print(
                "\nWishlist vazia ou inacessível."
            )

            return

        # ====================================================
        # COMPARAÇÃO
        # ====================================================

        print("\n" + "=" * 70)
        print("COMPARANDO")
        print("=" * 70)

        print(
            f"\nWishlist Steam: "
            f"{len(wishlist)}"
        )

        print(
            f"Jogos Playnite considerados: "
            f"{len(games)}"
        )

        (
            exact_matches,
            fuzzy_matches
        ) = compare_games(
            wishlist,
            games
        )

        # ====================================================
        # RESULTADOS
        # ====================================================

        show_results(
            exact_matches,
            fuzzy_matches
        )

    except KeyboardInterrupt:

        print(
            "\n\nExecução cancelada."
        )

    except Exception as e:

        print("\n")
        print("=" * 70)
        print("ERRO")
        print("=" * 70)

        print(
            f"\n{type(e).__name__}: "
            f"{e}"
        )


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":
    main()