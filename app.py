import streamlit as st
import pandas as pd
import altair as alt
from dataclasses import dataclass
from typing import List, Tuple, Dict
import math
from streamlit_mermaid_interactive import mermaid

st.set_page_config(
    page_title="Basket UGA - Tournament organizer",
    page_icon=":material/sports_basketball:",
    layout="wide",
)


@dataclass
class Game:
    team1: str
    team2: str
    tournament: str  # "men" or "women"
    pool: str  # "A", "B", etc.
    field: int
    start_time: int  # minutes from start

    @property
    def end_time(self) -> int:
        return self.start_time + 6


def calculate_optimal_pools(
    num_teams: int, num_fields: int, game_duration: int, total_time: int
) -> Tuple[int, int]:
    """Calculate optimal number of pools and pool size.
    
    Prefers pool sizes of 4-5 teams (ideal for basketball tournaments).
    """
    if num_teams <= 0:
        return 0, 0
    
    if num_teams <= 5:
        return 1, num_teams

    # Target pool size of 4-5 teams
    target_pool_size = 5
    num_pools = max(1, round(num_teams / target_pool_size))
    
    # Adjust to ensure pools are between 3-6 teams
    while num_pools > 1 and num_teams / num_pools > 6:
        num_pools += 1
    while num_pools > 1 and num_teams / num_pools < 3:
        num_pools -= 1
    
    base_size = num_teams // num_pools
    return num_pools, base_size


def distribute_teams_to_pools(teams: List[str], num_pools: int) -> Dict[str, List[str]]:
    """Distribute teams into pools as evenly as possible."""
    if num_pools <= 0 or not teams:
        return {}

    pools = {chr(ord("A") + i): [] for i in range(num_pools)}
    pool_names = list(pools.keys())

    for i, team in enumerate(teams):
        pool_name = pool_names[i % num_pools]
        pools[pool_name].append(team)

    return pools


def generate_pool_games(
    pools: Dict[str, List[str]], tournament: str
) -> List[Tuple[str, str, str, str]]:
    """Generate all games within each pool (round-robin per pool)."""
    games = []
    for pool_name, teams in pools.items():
        for i in range(len(teams)):
            for j in range(i + 1, len(teams)):
                games.append((teams[i], teams[j], tournament, pool_name))
    return games


def schedule_games(
    men_pools: Dict[str, List[str]],
    women_pools: Dict[str, List[str]],
    num_fields: int,
    game_duration: int = 6,
    total_time: int = 120,
) -> Tuple[List[Game], dict]:
    """Schedule all games across fields, maximizing parallel usage."""

    men_games = generate_pool_games(men_pools, "men") if men_pools else []
    women_games = generate_pool_games(women_pools, "women") if women_pools else []

    # Separate pending games by tournament
    pending_men = list(men_games)
    pending_women = list(women_games)

    scheduled = []
    all_teams = set()
    for pool_teams in list(men_pools.values()) + list(women_pools.values()):
        all_teams.update(pool_teams)
    
    # Track when each team is free
    team_free_at = {team: 0 for team in all_teams}

    # Process time slot by time slot
    current_time = 0
    while (pending_men or pending_women) and current_time + game_duration <= total_time:
        games_this_slot = []
        teams_used_this_slot = set()
        
        # Helper to find available games from a list
        def find_available(pending_list):
            return [
                g for g in pending_list
                if team_free_at.get(g[0], 0) <= current_time
                and team_free_at.get(g[1], 0) <= current_time
                and g[0] not in teams_used_this_slot
                and g[1] not in teams_used_this_slot
            ]
        
        # Fill fields with available games, prioritizing women first
        while len(games_this_slot) < num_fields:
            available_women = find_available(pending_women)
            available_men = find_available(pending_men)
            
            # Prioritize women if they have fewer games scheduled proportionally
            women_ratio = len([g for g in scheduled if g.tournament == "women"]) / max(len(women_games), 1) if women_games else 1
            men_ratio = len([g for g in scheduled if g.tournament == "men"]) / max(len(men_games), 1) if men_games else 1
            
            if available_women and (women_ratio <= men_ratio or not available_men):
                game = available_women[0]
                pending_women.remove(game)
            elif available_men:
                game = available_men[0]
                pending_men.remove(game)
            else:
                break
            
            games_this_slot.append(game)
            teams_used_this_slot.add(game[0])
            teams_used_this_slot.add(game[1])
        
        # Schedule the games
        for field_idx, game in enumerate(games_this_slot):
            team1, team2, tournament, pool = game
            scheduled.append(Game(
                team1=team1,
                team2=team2,
                tournament=tournament,
                pool=pool,
                field=field_idx + 1,
                start_time=current_time,
            ))
            team_free_at[team1] = current_time + game_duration
            team_free_at[team2] = current_time + game_duration
        
        current_time += game_duration

    stats = {
        "total_games": len(scheduled),
        "men_games": len([g for g in scheduled if g.tournament == "men"]),
        "women_games": len([g for g in scheduled if g.tournament == "women"]),
        "men_games_needed": len(men_games),
        "women_games_needed": len(women_games),
        "total_duration": max([g.end_time for g in scheduled]) if scheduled else 0,
    }

    return scheduled, stats


def generate_mermaid_diagram(
    men_pools: Dict[str, List[str]], women_pools: Dict[str, List[str]]
) -> str:
    """Generate a Mermaid flowchart showing the tournament structure."""
    lines = ["flowchart LR"]

    # Styling
    lines.append("    classDef menPool fill:#1B2838,stroke:#1B2838,color:#fff")
    lines.append("    classDef womenPool fill:#F47920,stroke:#F47920,color:#fff")
    lines.append("    classDef team fill:#f8f9fa,stroke:#1B2838,color:#1B2838")
    lines.append("    classDef teamW fill:#f8f9fa,stroke:#F47920,color:#1B2838")
    lines.append(
        "    classDef tournament fill:#2A3F5F,stroke:#1B2838,color:#fff,font-weight:bold"
    )

    # Men's tournament with subgraphs for each pool
    if men_pools:
        lines.append('    MEN["MASCULIN"]:::tournament')
        for pool_name, teams in men_pools.items():
            pool_id = f"M_{pool_name}"
            subgraph_id = f"subM{pool_name}"
            lines.append(f"    subgraph {subgraph_id}[Poule {pool_name}]")
            lines.append(f"    direction TB")
            for i, team in enumerate(teams):
                team_id = f"M_{pool_name}_{i}"
                safe_team = team.replace('"', "'").replace("Équipe ", "")
                lines.append(f'        {team_id}["{safe_team}"]:::team')
            lines.append("    end")
            lines.append(f"    MEN --> {subgraph_id}")

    # Women's tournament with subgraphs
    if women_pools:
        lines.append('    WOMEN["FEMININ"]:::womenPool')
        for pool_name, teams in women_pools.items():
            pool_id = f"W_{pool_name}"
            subgraph_id = f"subW{pool_name}"
            lines.append(f"    subgraph {subgraph_id}[Poule {pool_name}]")
            lines.append(f"    direction TB")
            for i, team in enumerate(teams):
                team_id = f"W_{pool_name}_{i}"
                safe_team = team.replace('"', "'").replace("Équipe ", "")
                lines.append(f'        {team_id}["{safe_team}"]:::teamW')
            lines.append("    end")
            lines.append(f"    WOMEN --> {subgraph_id}")

    return "\n".join(lines)


def format_time(minutes: int) -> str:
    """Convert minutes to HH:MM format."""
    h, m = divmod(minutes, 60)
    return f"{h}:{m:02d}"


@st.cache_data
def load_default_data():
    """Load player data from CSV."""
    import os
    csv_path = os.path.join(os.path.dirname(__file__), "data", "players.csv")
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        # Group by team
        teams_data = {}
        for team_name in df["equipe"].unique():
            team_df = df[df["equipe"] == team_name]
            genre = team_df["genre"].iloc[0]
            players = team_df["prenom"].fillna("").tolist()
            teams_data[team_name] = {
                "genre": genre,
                "players": players[:5]  # Max 5 players
            }
        return teams_data
    return {}


# Load default data
default_data = load_default_data()
default_men_teams = {k: v for k, v in default_data.items() if v["genre"] == "M"}
default_women_teams = {k: v for k, v in default_data.items() if v["genre"] == "F"}


# Header
st.title(":material/sports_basketball: Basket UGA tournament")
st.caption("Université Grenoble Alpes")

# Sidebar
with st.sidebar:
    st.subheader(":material/settings: Configuration")

    num_fields = st.number_input(
        "Nombre de terrains", min_value=1, max_value=10, value=6
    )
    game_duration = st.number_input(
        "Durée d'un match (min)", min_value=1, max_value=30, value=6
    )
    total_time = st.number_input(
        "Durée totale (min)", min_value=30, max_value=300, value=120
    )

    st.subheader(":material/male: Équipes masculines")
    num_men_teams = st.number_input(
        "Nombre d'équipes", min_value=0, max_value=30, value=len(default_men_teams), key="men"
    )

    st.subheader(":material/female: Équipes féminines")
    num_women_teams = st.number_input(
        "Nombre d'équipes", min_value=0, max_value=30, value=len(default_women_teams), key="women"
    )

# Calculate optimal pools
men_num_pools, men_pool_size = calculate_optimal_pools(
    num_men_teams, num_fields, game_duration, total_time
)
women_num_pools, women_pool_size = calculate_optimal_pools(
    num_women_teams, num_fields, game_duration, total_time
)

if num_men_teams > 0 or num_women_teams > 0:

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            ":material/tune: Structure des poules",
            ":material/groups: Équipes & joueurs",
            ":material/calendar_month: Planning",
            ":material/summarize: Résumé",
        ]
    )

    with tab1:
        st.header("Configuration des poules")

        with st.container(border=True):
            st.subheader(":material/lightbulb: Hypothèses de calcul")
            st.markdown("""
            - **Format:** Phase de poules avec matchs aller simple (round-robin)
            - **Objectif:** Maximiser le nombre de matchs par équipe tout en respectant le temps
            - **Contrainte:** Une équipe ne peut jouer qu'un match à la fois
            - **Équilibre:** Les poules sont équilibrées au maximum (±1 équipe)
            """)

        col1, col2 = st.columns(2)

        with col1:
            if num_men_teams > 0:
                with st.container(border=True):
                    st.subheader(":material/male: Tournoi masculin")

                    men_num_pools = st.slider(
                        "Nombre de poules",
                        min_value=1,
                        max_value=max(num_men_teams // 2, 1),
                        value=men_num_pools,
                        key="men_pools_slider",
                    )

                    base_size = num_men_teams // men_num_pools
                    remainder = num_men_teams % men_num_pools
                    games_per_small_pool = base_size * (base_size - 1) // 2
                    games_per_large_pool = (base_size + 1) * base_size // 2
                    total_men_games = (
                        men_num_pools - remainder
                    ) * games_per_small_pool + remainder * games_per_large_pool
                    games_per_team = base_size - 1 if remainder == 0 else base_size

                    pool_desc = f"{men_num_pools - remainder} poule(s) de {base_size} équipes"
                    if remainder > 0:
                        pool_desc += f", {remainder} poule(s) de {base_size + 1} équipes"

                    st.caption(pool_desc)
                    
                    with st.container(horizontal=True):
                        st.metric("Matchs total", total_men_games, border=True)
                        st.metric(
                            "Matchs/équipe",
                            f"{games_per_team}-{games_per_team + (1 if remainder > 0 else 0)}",
                            border=True,
                        )

        with col2:
            if num_women_teams > 0:
                with st.container(border=True):
                    st.subheader(":material/female: Tournoi féminin")

                    women_num_pools = st.slider(
                        "Nombre de poules",
                        min_value=1,
                        max_value=max(num_women_teams // 2, 1),
                        value=women_num_pools,
                        key="women_pools_slider",
                    )

                    base_size_w = num_women_teams // women_num_pools
                    remainder_w = num_women_teams % women_num_pools
                    games_per_small_pool_w = base_size_w * (base_size_w - 1) // 2
                    games_per_large_pool_w = (base_size_w + 1) * base_size_w // 2
                    total_women_games = (
                        women_num_pools - remainder_w
                    ) * games_per_small_pool_w + remainder_w * games_per_large_pool_w
                    games_per_team_w = (
                        base_size_w - 1 if remainder_w == 0 else base_size_w
                    )

                    pool_desc_w = f"{women_num_pools - remainder_w} poule(s) de {base_size_w} équipes"
                    if remainder_w > 0:
                        pool_desc_w += (
                            f", {remainder_w} poule(s) de {base_size_w + 1} équipes"
                        )

                    st.caption(pool_desc_w)
                    
                    with st.container(horizontal=True):
                        st.metric("Matchs total", total_women_games, border=True)
                        st.metric(
                            "Matchs/équipe",
                            f"{games_per_team_w}-{games_per_team_w + (1 if remainder_w > 0 else 0)}",
                            border=True,
                        )

        # Feasibility check
        total_games = (total_men_games if num_men_teams > 0 else 0) + (
            total_women_games if num_women_teams > 0 else 0
        )
        games_per_field = total_time // game_duration
        max_games = games_per_field * num_fields

        st.subheader(":material/query_stats: Faisabilité")

        with st.container(horizontal=True):
            st.metric("Matchs à jouer", total_games, border=True)
            st.metric("Capacité max", max_games, f"+{max_games - total_games} marge", border=True)
            
        if total_games <= max_games:
            st.success(":material/check_circle: Faisable!")
        else:
            st.error(":material/error: Trop de matchs pour le temps disponible!")

        st.session_state.men_num_pools = men_num_pools
        st.session_state.women_num_pools = women_num_pools

    with tab2:
        col1, col2 = st.columns(2)

        men_teams = []
        women_teams = []
        men_rosters = {}
        women_rosters = {}
        
        # Get default team names lists
        default_men_names = list(default_men_teams.keys())
        default_women_names = list(default_women_teams.keys())

        with col1:
            if num_men_teams > 0:
                st.subheader(":material/male: Équipes masculines")
                for i in range(num_men_teams):
                    # Get default values from CSV
                    default_team = default_men_names[i] if i < len(default_men_names) else f"Équipe M{i+1}"
                    default_players = default_men_teams.get(default_team, {}).get("players", [])
                    
                    with st.expander(default_team, expanded=(i == 0)):
                        team_name = st.text_input(
                            "Nom de l'équipe",
                            value=default_team,
                            key=f"men_team_{i}",
                        )
                        men_teams.append(team_name)

                        players = []
                        c1, c2, c3 = st.columns(3)
                        cols = [c1, c2, c3, c1, c2]
                        for j in range(5):
                            default_player = default_players[j] if j < len(default_players) else ""
                            with cols[j]:
                                player = st.text_input(
                                    f"Joueur {j+1}",
                                    value=default_player,
                                    key=f"men_player_{i}_{j}",
                                )
                                players.append(player)
                        men_rosters[team_name] = players

        with col2:
            if num_women_teams > 0:
                st.subheader(":material/female: Équipes féminines")
                for i in range(num_women_teams):
                    # Get default values from CSV
                    default_team = default_women_names[i] if i < len(default_women_names) else f"Équipe F{i+1}"
                    default_players = default_women_teams.get(default_team, {}).get("players", [])
                    
                    with st.expander(default_team, expanded=(i == 0)):
                        team_name = st.text_input(
                            "Nom de l'équipe",
                            value=default_team,
                            key=f"women_team_{i}",
                        )
                        women_teams.append(team_name)

                        players = []
                        c1, c2, c3 = st.columns(3)
                        cols = [c1, c2, c3, c1, c2]
                        for j in range(5):
                            default_player = default_players[j] if j < len(default_players) else ""
                            with cols[j]:
                                player = st.text_input(
                                    f"Joueuse {j+1}",
                                    value=default_player,
                                    key=f"women_player_{i}_{j}",
                                )
                                players.append(player)
                        women_rosters[team_name] = players

        st.session_state.men_teams = men_teams
        st.session_state.women_teams = women_teams
        st.session_state.men_rosters = men_rosters
        st.session_state.women_rosters = women_rosters

    with tab3:
        men_teams = st.session_state.get(
            "men_teams", [f"Équipe M{i+1}" for i in range(num_men_teams)]
        )
        women_teams = st.session_state.get(
            "women_teams", [f"Équipe F{i+1}" for i in range(num_women_teams)]
        )
        men_num_pools = st.session_state.get("men_num_pools", 3)
        women_num_pools = st.session_state.get("women_num_pools", 1)

        men_pools = (
            distribute_teams_to_pools(men_teams, men_num_pools) if men_teams else {}
        )
        women_pools = (
            distribute_teams_to_pools(women_teams, women_num_pools)
            if women_teams
            else {}
        )

        st.session_state.men_pools = men_pools
        st.session_state.women_pools = women_pools

        st.header(":material/account_tree: Structure du tournoi")

        mermaid_code = generate_mermaid_diagram(men_pools, women_pools)
        mermaid(mermaid_code)

        # Generate schedule automatically
        scheduled, stats = schedule_games(
            men_pools, women_pools, num_fields, game_duration, total_time
        )

        if (
            stats["men_games"] < stats["men_games_needed"]
            or stats["women_games"] < stats["women_games_needed"]
        ):
            st.warning(
                ":material/warning: Certains matchs n'ont pas pu être planifiés!"
            )

        st.subheader(":material/bar_chart: Statistiques")

        with st.container(horizontal=True):
            st.metric("Matchs total", stats["total_games"], border=True)
            st.metric("Matchs masculins", stats["men_games"], border=True)
            st.metric("Matchs féminins", stats["women_games"], border=True)
            st.metric("Durée effective", f"{stats['total_duration']} min", border=True)

        st.subheader(":material/view_timeline: Planning par rotation")

        # Build Gantt chart data with rotations
        gantt_data = []
        for game in scheduled:
            rotation = game.start_time // game_duration + 1
            t1 = game.team1.replace("Équipe ", "")
            t2 = game.team2.replace("Équipe ", "")
            gantt_data.append({
                "Terrain": f"Terrain {game.field}",
                "Rotation": rotation,
                "Match": f"{game.team1} vs {game.team2}",
                "Label": f"{t1}\nVS\n{t2}",
                "Tournoi": "Masculin" if game.tournament == "men" else "Féminin",
                "Poule": f"Poule {game.pool}",
            })
        
        gantt_df = pd.DataFrame(gantt_data)
        max_rotation = gantt_df["Rotation"].max() if len(gantt_df) > 0 else 1
        
        # Create Gantt chart with Altair - rectangles
        bars = alt.Chart(gantt_df).mark_rect(
            cornerRadius=4,
            stroke="white",
            strokeWidth=2
        ).encode(
            x=alt.X(
                "Rotation:O",
                title="Rotation (6 min chacune)",
                axis=alt.Axis(labelAngle=0)
            ),
            y=alt.Y("Terrain:N", title=None, sort=[f"Terrain {i+1}" for i in range(num_fields)]),
            color=alt.Color(
                "Tournoi:N",
                scale=alt.Scale(
                    domain=["Masculin", "Féminin"],
                    range=["#1B2838", "#F47920"]
                ),
                legend=alt.Legend(title="Tournoi", orient="top")
            ),
            tooltip=["Terrain", "Rotation", "Match", "Tournoi", "Poule"]
        )
        
        # Add text labels on top
        text = alt.Chart(gantt_df).mark_text(
            align="center",
            baseline="middle",
            color="white",
            fontSize=10,
            fontWeight="bold",
            lineBreak="\n"
        ).encode(
            x=alt.X("Rotation:O"),
            y=alt.Y("Terrain:N", sort=[f"Terrain {i+1}" for i in range(num_fields)]),
            text="Label:N"
        )
        
        gantt_chart = (bars + text).properties(
            height=60 * num_fields + 60
        )

        st.altair_chart(gantt_chart, use_container_width=True)
        
        st.caption(f"{int(max_rotation)} rotations × 6 min = {int(max_rotation) * 6} min total")

        st.subheader(":material/stadium: Planning par terrain")

        # Create tabs for each field
        field_tabs = st.tabs([f"Terrain {i+1}" for i in range(num_fields)])

        for field_idx, field_tab in enumerate(field_tabs):
            field_num = field_idx + 1
            field_games = sorted(
                [g for g in scheduled if g.field == field_num],
                key=lambda g: g.start_time,
            )

            with field_tab:
                if not field_games:
                    st.caption("Aucun match sur ce terrain")
                    continue

                for game in field_games:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([1, 2, 1])
                        with c1:
                            st.caption(
                                f"{format_time(game.start_time)} - {format_time(game.end_time)}"
                            )
                        with c2:
                            st.markdown(f"**{game.team1}** vs **{game.team2}**")
                        with c3:
                            if game.tournament == "men":
                                st.badge(
                                    f"M-{game.pool}",
                                    icon=":material/male:",
                                    color="blue",
                                )
                            else:
                                st.badge(
                                    f"F-{game.pool}",
                                    icon=":material/female:",
                                    color="orange",
                                )

        st.subheader(":material/schedule: Vue chronologique")

        timeline_data = []
        for game in sorted(scheduled, key=lambda g: (g.start_time, g.field)):
            timeline_data.append(
                {
                    "Heure": f"{format_time(game.start_time)} - {format_time(game.end_time)}",
                    "Terrain": f"T{game.field}",
                    "Poule": f"{game.tournament[0].upper()}-{game.pool}",
                    "Match": f"{game.team1} vs {game.team2}",
                }
            )

        df = pd.DataFrame(timeline_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

    with tab4:
        st.header(":material/list: Récapitulatif par poule")

        men_pools = st.session_state.get("men_pools", {})
        women_pools = st.session_state.get("women_pools", {})

        col1, col2 = st.columns(2)

        with col1:
            if men_pools:
                st.subheader(":material/male: Poules masculines")
                for pool_name, teams in men_pools.items():
                    with st.container(border=True):
                        st.markdown(f"**Poule {pool_name}** ({len(teams)} équipes)")
                        for team in teams:
                            with st.expander(team, icon=":material/group:"):
                                roster = st.session_state.get("men_rosters", {}).get(
                                    team, []
                                )
                                for i, player in enumerate(roster, 1):
                                    st.write(f"{i}. {player}")

        with col2:
            if women_pools:
                st.subheader(":material/female: Poules féminines")
                for pool_name, teams in women_pools.items():
                    with st.container(border=True):
                        st.markdown(f"**Poule {pool_name}** ({len(teams)} équipes)")
                        for team in teams:
                            with st.expander(team, icon=":material/group:"):
                                roster = st.session_state.get("women_rosters", {}).get(
                                    team, []
                                )
                                for i, player in enumerate(roster, 1):
                                    st.write(f"{i}. {player}")

else:
    st.info(
        ":material/arrow_back: Configurez le nombre d'équipes dans la barre latérale pour commencer."
    )
