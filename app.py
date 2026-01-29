import streamlit as st
import random
import time

# ---------------------------
# 0) 페이지 / 모바일 최적화
# ---------------------------
st.set_page_config(page_title="Coup: Mobile Icon UI (2~8p)", layout="centered")

# ---------------------------
# 1) 룰/리소스 (이미지 제거 → 아이콘)
# ---------------------------
ROLES = ["Duke", "Assassin", "Captain", "Ambassador", "Contessa"]

ROLE_KO = {
    "Duke": "공작",
    "Assassin": "암살자",
    "Captain": "사령관",
    "Ambassador": "대사",
    "Contessa": "귀부인"
}

ROLE_ICON = {
    "Duke": "👑",
    "Assassin": "🗡️",
    "Captain": "⚓",
    "Ambassador": "🤝",
    "Contessa": "👒"
}

ACTIONS = {
    "Income": {
        "cost": 0, "claim_role": None,
        "blockable": False, "block_roles": [],
        "needs_target": False,
        "desc": "소득 (+1, 방어/도전 불가)"
    },
    "Foreign Aid": {
        "cost": 0, "claim_role": None,
        "blockable": True, "block_roles": ["Duke"],
        "needs_target": False,
        "desc": "해외원조 (+2, 공작으로 방해 가능)"
    },
    "Tax": {
        "cost": 0, "claim_role": "Duke",
        "blockable": False, "block_roles": [],
        "needs_target": False,
        "desc": "세금징수 (+3, 공작 주장)"
    },
    "Steal": {
        "cost": 0, "claim_role": "Captain",
        "blockable": True, "block_roles": ["Captain", "Ambassador"],
        "needs_target": True,
        "desc": "갈취 (+2, 대상이 사령관/대사로 방해 가능)"
    },
    "Assassinate": {
        "cost": 3, "claim_role": "Assassin",
        "blockable": True, "block_roles": ["Contessa"],
        "needs_target": True,
        "desc": "암살 (3코인, 대상이 귀부인으로 방해 가능)"
    },
    "Exchange": {
        "cost": 0, "claim_role": "Ambassador",
        "blockable": False, "block_roles": [],
        "needs_target": False,
        "desc": "교환 (대사 주장, 덱에서 2장 보고 교체)"
    },
    "Coup": {
        "cost": 7, "claim_role": None,
        "blockable": False, "block_roles": [],
        "needs_target": True,
        "desc": "쿠 (7코인, 방어 불가)"
    },
}

# ---------------------------
# 2) 로그 / 유틸
# ---------------------------
def log(msg: str):
    if "log" not in st.session_state:
        st.session_state.log = []
    st.session_state.log.insert(0, msg)

def alive_players_idxs():
    return [i for i, p in enumerate(st.session_state.players) if p["alive"]]

def next_alive_idx(from_idx: int):
    n = len(st.session_state.players)
    j = (from_idx + 1) % n
    while not st.session_state.players[j]["alive"]:
        j = (j + 1) % n
    return j

def turn_order_after(actor_idx: int):
    n = len(st.session_state.players)
    order = []
    j = (actor_idx + 1) % n
    while j != actor_idx:
        if st.session_state.players[j]["alive"]:
            order.append(j)
        j = (j + 1) % n
    return order

def get_alive_cards(player_idx: int):
    p = st.session_state.players[player_idx]
    return [c for k, c in enumerate(p["cards"]) if p["alive_cards"][k]]

def draw_card():
    if st.session_state.deck:
        return st.session_state.deck.pop()
    return random.choice(ROLES)

def ensure_target_valid(action_name, actor_idx, target_idx):
    info = ACTIONS[action_name]
    if not info["needs_target"]:
        return None

    if target_idx is None:
        candidates = [i for i in alive_players_idxs() if i != actor_idx]
        return random.choice(candidates) if candidates else None

    if target_idx == actor_idx or (not st.session_state.players[target_idx]["alive"]):
        candidates = [i for i in alive_players_idxs() if i != actor_idx]
        return random.choice(candidates) if candidates else None

    return target_idx

def check_game_over():
    alive = alive_players_idxs()
    if len(alive) <= 1:
        if len(alive) == 1:
            winner = st.session_state.players[alive[0]]
            if winner["is_ai"]:
                st.error(f"게임 종료! 승자: {winner['name']}")
            else:
                st.balloons()
                st.success("축하합니다! 최후의 승자가 되셨습니다!")
        else:
            st.error("게임 종료! (생존자 없음)")
        st.stop()

def finalize_deaths():
    for p in st.session_state.players:
        if p["alive"] and not any(p["alive_cards"]):
            p["alive"] = False
            log(f"⚰️ {p['name']} 탈락!")
    check_game_over()

def replace_revealed_card(target_idx: int, role: str):
    p = st.session_state.players[target_idx]
    for i in range(len(p["cards"])):
        if p["alive_cards"][i] and p["cards"][i] == role:
            st.session_state.deck.append(role)
            random.shuffle(st.session_state.deck)
            p["cards"][i] = draw_card()
            return

def request_influence_loss(player_idx: int, reason: str):
    p = st.session_state.players[player_idx]
    alive_idxs = [i for i, a in enumerate(p["alive_cards"]) if a]
    if not alive_idxs:
        return

    if p["is_ai"]:
        lose_i = random.choice(alive_idxs)
        lose_card = p["cards"][lose_i]
        p["alive_cards"][lose_i] = False
        log(f"💀 {p['name']} 영향력 제거: {ROLE_ICON[lose_card]} {ROLE_KO[lose_card]} ({reason})")
        finalize_deaths()
    else:
        st.session_state.pending_loss = {"player_idx": player_idx, "reason": reason}

def apply_influence_loss_if_pending():
