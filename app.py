# app.py
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

# 작은 아이콘(원하시면 다른 이모지로 바꿔드릴 수 있음)
ROLE_ICON = {
    "Duke": "👑",
    "Assassin": "🗡️",
    "Captain": "⚓",
    "Ambassador": "🤝",
    "Contessa": "👒"
}

# 액션 정의(보드게임 룰 기준)
ACTIONS = {
    "Income": {
        "cost": 0, "claim_role": None,
        "blockable": False, "block_roles": [],
        "needs_target": False,
        "desc": "소득 (+1, 방어/도전 불가)"
    },
    "Foreign Aid": {
        "cost": 0, "claim_role": None,
        "blockable": True, "block_roles": ["Duke"],  # 누구나 Duke로 방해 가능
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
        "blockable": True, "block_roles": ["Captain", "Ambassador"],  # 대상만 방어 가능
        "needs_target": True,
        "desc": "갈취 (+2, 대상이 사령관/대사로 방해 가능)"
    },
    "Assassinate": {
        "cost": 3, "claim_role": "Assassin",
        "blockable": True, "block_roles": ["Contessa"],  # 대상만 방어 가능
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
    """actor 다음 플레이어부터 한 바퀴(actor 제외) 순서"""
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
    """도전에서 진짜 역할을 보여줬다면 그 카드 1장을 덱에 넣고 새 카드로 교체"""
    p = st.session_state.players[target_idx]
    for i in range(len(p["cards"])):
        if p["alive_cards"][i] and p["cards"][i] == role:
            st.session_state.deck.append(role)
            random.shuffle(st.session_state.deck)
            p["cards"][i] = draw_card()
            return

def request_influence_loss(player_idx: int, reason: str):
    """영향력(카드) 1장 잃기: 인간은 선택 UI, AI는 자동"""
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
    """인간 영향력 제거 선택 UI (진짜 보드게임처럼 선택)"""
    info = st.session_state.get("pending_loss")
    if not info:
        return False

    p = st.session_state.players[info["player_idx"]]
    if not p["alive"]:
        st.session_state.pending_loss = None
        return False

    alive_idxs = [i for i, a in enumerate(p["alive_cards"]) if a]
    if not alive_idxs:
        st.session_state.pending_loss = None
        return False

    st.warning(f"🃏 영향력 1장 잃기 필요 — 사유: {info['reason']}")
    cols = st.columns(len(alive_idxs))
    for col, ci in zip(cols, alive_idxs):
        card = p["cards"][ci]
        with col:
            st.write(f"**{ROLE_ICON[card]} {ROLE_KO[card]}**")
            if st.button("이 카드 제거", key=f"lose_{ci}"):
                p["alive_cards"][ci] = False
                log(f"💀 {p['name']} 영향력 제거: {ROLE_ICON[card]} {ROLE_KO[card]} ({info['reason']})")
                st.session_state.pending_loss = None
                finalize_deaths()
                st.rerun()

    return True

def maybe_autoplay_delay():
    if st.session_state.get("autoplay", True):
        time.sleep(float(st.session_state.get("speed", 0.8)))

# ---------------------------
# 3) AI (간단)
# ---------------------------
def ai_pick_target(actor_idx: int):
    candidates = [i for i in alive_players_idxs() if i != actor_idx]
    return random.choice(candidates) if candidates else None

def ai_decide_action(ai_idx: int):
    ai = st.session_state.players[ai_idx]
    hand = get_alive_cards(ai_idx)
    target = ai_pick_target(ai_idx)

    if ai["coins"] >= 10:
        return "Coup", target
    if ai["coins"] >= 7 and target is not None:
        return "Coup", target
    if ai["coins"] >= 3 and target is not None and ("Assassin" in hand or random.random() < 0.25):
        return "Assassinate", target
    if "Duke" in hand or random.random() < 0.45:
        return "Tax", None
    if "Captain" in hand and target is not None and random.random() < 0.55:
        return "Steal", target
    if "Ambassador" in hand and random.random() < 0.20:
        return "Exchange", None
    return ("Foreign Aid", None) if random.random() < 0.6 else ("Income", None)

def ai_wants_challenge(ai_idx: int, claimed_role: str):
    if claimed_role is None:
        return False
    return random.random() < 0.12

def ai_wants_block(ai_idx: int, action_name: str, target_idx: int):
    info = ACTIONS[action_name]
    if not info["blockable"]:
        return False

    hand = get_alive_cards(ai_idx)

    # Foreign Aid: 누구나 Duke로 방해 가능
    if action_name == "Foreign Aid":
        if "Duke" in hand:
            return random.random() < 0.75
        return random.random() < 0.15

    # Assassinate/Steal: 대상만 방해 가능(원래 룰)
    if ai_idx != target_idx:
        return False

    if action_name == "Assassinate":
        if "Contessa" in hand:
            return random.random() < 0.85
        return random.random() < 0.25

    if action_name == "Steal":
        if "Captain" in hand or "Ambassador" in hand:
            return random.random() < 0.75
        return random.random() < 0.20

    return False

def ai_wants_challenge_block(ai_idx: int):
    return random.random() < 0.18

# ---------------------------
# 4) 페이즈/상태
# ---------------------------
# phase:
#   TURN_START
#   AWAIT_CHALLENGE
#   AWAIT_BLOCK
#   AWAIT_BLOCK_CHALLENGE
#   RESOLVE_ACTION
#
# current_action:
#   {actor_idx, action_name, target_idx, claimed_role, blocker_idx, block_role}
#
# 인간 개입은 "실시간" 느낌 위해:
#   - 인간이 개입할 수 있는 창에서는 자동으로 다음으로 넘어가지 않음
#   - 인간이 "패스" 버튼을 눌러야 AI 판단/다음 진행

def reset_game(n_players: int, ai_names: list[str]):
    st.session_state.clear()
    st.session_state.n_players = n_players
    st.session_state.log = ["게임 시작! (아이콘 UI + 실시간 개입)"]

    # 7~8인 덱 확장(역할당 4장, 하우스룰)
    copies = 4 if n_players >= 7 else 3
    deck = []
    for r in ROLES:
        deck.extend([r] * copies)
    random.shuffle(deck)
    st.session_state.deck = deck

    st.session_state.players = []
    names = ["나 (Player)"] + ai_names
    for i in range(n_players):
        st.session_state.players.append({
            "id": i,
            "name": names[i],
            "is_ai": i != 0,
            "coins": 2,
            "cards": [draw_card(), draw_card()],
            "alive_cards": [True, True],
            "alive": True
        })

    st.session_state.turn_idx = random.randint(0, n_players - 1)
    st.session_state.phase = "TURN_START"
    st.session_state.current_action = None
    st.session_state.pending_loss = None

    st.session_state.autoplay = True
    st.session_state.speed = 0.9

    st.session_state.selected_target = None  # 아이콘 클릭으로 지정
    log(f"첫 턴: {st.session_state.players[st.session_state.turn_idx]['name']}")

def get_current_player():
    return st.session_state.players[st.session_state.turn_idx]

def go_next_turn():
    st.session_state.turn_idx = next_alive_idx(st.session_state.turn_idx)
    st.session_state.current_action = None
    st.session_state.phase = "TURN_START"
    st.session_state.selected_target = None
    log(f"다음 턴: {st.session_state.players[st.session_state.turn_idx]['name']}")
    st.rerun()

# ---------------------------
# 5) 도전/방해/실행
# ---------------------------
def resolve_challenge(challenger_idx: int, target_idx: int, role_claimed: str, context: str):
    challenger = st.session_state.players[challenger_idx]
    target = st.session_state.players[target_idx]
    target_hand = get_alive_cards(target_idx)

    if role_claimed in target_hand:
        log(f"🛡️ 인증 성공: {target['name']}는 {ROLE_ICON[role_claimed]} {ROLE_KO[role_claimed]} 보유 ({context})")
        log(f"❌ 도전 실패: {challenger['name']} 영향력 1장 잃음")
        request_influence_loss(challenger_idx, reason=f"도전 실패({context})")
        replace_revealed_card(target_idx, role_claimed)
        return True
    else:
        log(f"🤥 블러핑 적발: {target['name']}는 {ROLE_ICON[role_claimed]} {ROLE_KO[role_claimed]} 없음 ({context})")
        log(f"⚔️ 도전 성공: {target['name']} 영향력 1장 잃음")
        request_influence_loss(target_idx, reason=f"도전 성공으로 패배({context})")
        return False

def execute_action_final():
    act = st.session_state.current_action
    actor = st.session_state.players[act["actor_idx"]]
    action_name = act["action_name"]
    target = st.session_state.players[act["target_idx"]] if act["target_idx"] is not None else None

    actor["coins"] -= ACTIONS[action_name]["cost"]

    if action_name == "Income":
        actor["coins"] += 1
        log(f"✅ {actor['name']} 소득 +1")

    elif action_name == "Foreign Aid":
        actor["coins"] += 2
        log(f"✅ {actor['name']} 해외원조 +2")

    elif action_name == "Tax":
        actor["coins"] += 3
        log(f"✅ {actor['name']} 세금징수 +3")

    elif action_name == "Steal":
        steal_amount = min(2, target["coins"])
        target["coins"] -= steal_amount
        actor["coins"] += steal_amount
        log(f"✅ {actor['name']} 갈취 성공: {target['name']}에게서 {steal_amount}코인")

    elif action_name == "Assassinate":
        log(f"✅ {actor['name']} 암살 성공: {target['name']} 영향력 1장 잃음")
        request_influence_loss(target["id"], reason="암살")

    elif action_name == "Exchange":
        new_cards = [draw_card(), draw_card()]
        current_alive = get_alive_cards(actor["id"])
        pool = current_alive + new_cards
        random.shuffle(pool)
        lives = sum(actor["alive_cards"])
        keep = pool[:lives]
        for c in pool[lives:]:
            st.session_state.deck.append(c)
        random.shuffle(st.session_state.deck)

        alive_k = 0
        for i in range(2):
            if actor["alive_cards"][i]:
                actor["cards"][i] = keep[alive_k]
                alive_k += 1
        log(f"✅ {actor['name']} 교환 완료")

    elif action_name == "Coup":
        log(f"✅ {actor['name']} 쿠 성공: {target['name']} 영향력 1장 잃음(방어 불가)")
        request_influence_loss(target["id"], reason="쿠")

    finalize_deaths()
    go_next_turn()

# ---------------------------
# 6) 시작 화면: 인원 + AI 이름
# ---------------------------
if "n_players" not in st.session_state:
    st.title("🃏 Coup (쿠) : 아이콘 모바일 UI (2~8인)")
    n = st.slider("플레이 인원수", min_value=2, max_value=8, value=4, step=1)

    st.caption("7~8인은 원본 최대 6인을 넘어서는 하우스룰(덱 확장)로 동작합니다.")
    st.subheader("AI 이름 설정(구분용)")
    ai_names = []
    for i in range(1, n):
        ai_names.append(st.text_input(f"AI {i} 이름", value=f"Alpha{i}"))

    if st.button("게임 시작"):
        reset_game(n, ai_names)
        st.rerun()
    st.stop()

# ---------------------------
# 7) 사이드바: 자동진행/속도/리셋
# ---------------------------
with st.sidebar:
    st.subheader("⚙️ 진행 설정")
    st.session_state.autoplay = st.toggle("자동 진행", value=st.session_state.get("autoplay", True))
    st.session_state.speed = st.slider("자동 진행 속도(초)", 0.2, 3.0, float(st.session_state.get("speed", 0.9)), 0.1)
    if st.button("🔄 새 게임(리셋)"):
        n = st.session_state.n_players
        # 리셋 시 AI 이름은 현재 플레이어명에서 재사용
        ai_names = [st.session_state.players[i]["name"] for i in range(1, n)]
        reset_game(n, ai_names)
        st.rerun()

# ---------------------------
# 8) 상단: 플레이어 상태(통합) + 타겟 선택(아이콘 클릭)
# ---------------------------
st.title("🃏 Coup (쿠)")

# 영향력 제거 선택이 걸려있으면 먼저 처리
if apply_influence_loss_if_pending():
    st.stop()

# 플레이어 상태(내 상태 포함)
st.subheader("👥 플레이어 상태 (아이콘)")
players = st.session_state.players
turn_idx = st.session_state.turn_idx

# 공격 대상(아이콘 클릭) 선택 UI: 내 턴에만 의미 있지만, 미리 선택 가능하게 열어둠
# - 드롭다운 대신 버튼 클릭
def render_player_chip(i: int):
    p = players[i]
    if not p["alive"]:
        return f"⚰️ {p['name']}"
    alive_cnt = sum(p["alive_cards"])
    turn_mark = "👉" if i == turn_idx else ""
    you_mark = "🟢" if i == 0 else "🤖"
    # 카드 표시는 실감 위해: 살아있는 카드는 '❓', 죽은 카드는 공개 아이콘
    card_bits = []
    for k in range(2):
        if p["alive_cards"][k]:
            card_bits.append("❓")
        else:
            c = p["cards"][k]
            card_bits.append(f"{ROLE_ICON[c]}")
    cards_str = " ".join(card_bits)
    sel = "🎯" if st.session_state.get("selected_target") == i else ""
    return f"{turn_mark}{you_mark} {p['name']} {sel}\n💰{p['coins']} | 🃏{alive_cnt}/2 | {cards_str}"

# 모바일에서 한 줄에 너무 많은 버튼은 불편 → 2열 정도로 자동 배치
alive_idxs = [i for i in range(len(players)) if players[i]["alive"]]
rows = []
tmp = []
for i in range(len(players)):
    tmp.append(i)
    if len(tmp) == 2:
        rows.append(tmp)
        tmp = []
if tmp:
    rows.append(tmp)

for r, row in enumerate(rows):
    cols = st.columns(len(row))
    for col, i in zip(cols, row):
        with col:
            label = render_player_chip(i)
            disabled = (not players[i]["alive"])
            # 내 자신은 타겟 선택 불가 처리
            if i == 0:
                # 내 칩은 타겟 버튼 역할 하지 않도록
                st.button(label, key=f"chip_{i}", disabled=True)
            else:
                if st.button(label, key=f"chip_{i}", disabled=disabled):
                    st.session_state.selected_target = i
                    st.rerun()

st.divider()

# 현재 선언/상황
if st.session_state.current_action:
    act = st.session_state.current_action
    actor = players[act["actor_idx"]]["name"]
    action = act["action_name"]
    target_msg = ""
    if act.get("target_idx") is not None:
        target_msg = f" → {players[act['target_idx']]['name']}"
    st.warning(f"📢 현재 선언: **{actor} [{ACTIONS[action]['desc'].split(' ')[0]}]**{target_msg}")

# 로그
st.header("📜 로그")
log_box = st.container(height=240)
for m in st.session_state.log:
    log_box.text(m)

st.divider()

# ---------------------------
# 9) 하단: 행동 버튼(가로배열) + 내 턴/AI 턴 처리
# ---------------------------
curr = get_current_player()
me = players[0]

# 페이즈/행동 처리: "실시간 개입" 느낌을 위해
# 인간이 개입할 수 있는 창에서는 자동으로 넘어가지 않음
def set_action(actor_idx, action_name, target_idx):
    st.session_state.current_action = {
        "actor_idx": actor_idx,
        "action_name": action_name,
        "target_idx": target_idx,
        "claimed_role": ACTIONS[action_name]["claim_role"],
        "blocker_idx": None,
        "block_role": None,
        # 인간 개입 진행 플래그
        "human_challenge_done": False,
        "human_block_done": False,
        "human_block_challenge_done": False,
    }

# ---------------------------
# TURN_START
# ---------------------------
if st.session_state.phase == "TURN_START":
    # 강제 쿠(10코인)
    if curr["coins"] >= 10:
        st.error("💥 10코인 이상! 이번 턴은 '쿠' 강제입니다.")
        if curr["is_ai"]:
            t = ensure_target_valid("Coup", curr["id"], ai_pick_target(curr["id"]))
            set_action(curr["id"], "Coup", t)
            log(f"💥 강제 쿠 선언: {curr['name']} → {players[t]['name']}")
            st.session_state.phase = "AWAIT_CHALLENGE"
            maybe_autoplay_delay()
            st.rerun()
        else:
            t = st.session_state.get("selected_target")
            if t is None:
                st.info("🎯 공격 대상을 위 플레이어 칩(버튼)으로 먼저 선택하세요.")
            elif st.button("Coup(쿠) 선언"):
                set_action(0, "Coup", t)
                log(f"💥 강제 쿠 선언: {curr['name']} → {players[t]['name']}")
                st.session_state.phase = "AWAIT_CHALLENGE"
                st.rerun()
        st.stop()

    # 내 턴: 행동 버튼(가로배열)
    if curr["id"] == 0 and me["alive"]:
        st.subheader("⚡ 내 차례: 행동 선택 (가로 버튼)")

        # 대상이 필요한 액션은 selected_target 사용
        t = st.session_state.get("selected_target")

        # 가로배열: 7개를 한 줄로(모바일에서 자동 줄바꿈될 수 있음)
        cols = st.columns(7)
        if cols[0].button("소득"):
            set_action(0, "Income", None)
            log("👤 소득 선언")
            st.session_state.phase = "AWAIT_CHALLENGE"
            st.rerun()

        if cols[1].button("해외원조"):
            set_action(0, "Foreign Aid", None)
            log("👤 해외원조 선언")
            st.session_state.phase = "AWAIT_CHALLENGE"
            st.rerun()

        if cols[2].button("세금징수"):
            set_action(0, "Tax", None)
            log("👤 세금징수(공작 주장) 선언")
            st.session_state.phase = "AWAIT_CHALLENGE"
            st.rerun()

        if cols[3].button("교환"):
            set_action(0, "Exchange", None)
            log("👤 교환(대사 주장) 선언")
            st.session_state.phase = "AWAIT_CHALLENGE"
            st.rerun()

        if cols[4].button("갈취"):
            if t is None:
                st.info("🎯 갈취 대상 선택: 위 플레이어 칩을 눌러 선택하세요.")
            else:
                set_action(0, "Steal", t)
                log(f"👤 갈취(사령관 주장) 선언 → {players[t]['name']}")
                st.session_state.phase = "AWAIT_CHALLENGE"
                st.rerun()

        if cols[5].button("암살"):
            if me["coins"] < 3:
                st.warning("코인 3 미만: 암살 불가")
            elif t is None:
                st.info("🎯 암살 대상 선택: 위 플레이어 칩을 눌러 선택하세요.")
            else:
                set_action(0, "Assassinate", t)
                log(f"👤 암살(암살자 주장) 선언 → {players[t]['name']}")
                st.session_state.phase = "AWAIT_CHALLENGE"
                st.rerun()

        if cols[6].button("쿠"):
            if me["coins"] < 7:
                st.warning("코인 7 미만: 쿠 불가")
            elif t is None:
                st.info("🎯 쿠 대상 선택: 위 플레이어 칩을 눌러 선택하세요.")
            else:
                set_action(0, "Coup", t)
                log(f"👤 쿠 선언 → {players[t]['name']}")
                st.session_state.phase = "AWAIT_CHALLENGE"
                st.rerun()

        st.stop()

    # AI 턴
    if curr["is_ai"] and curr["alive"]:
        act_name, target = ai_decide_action(curr["id"])
        target = ensure_target_valid(act_name, curr["id"], target)
        set_action(curr["id"], act_name, target)
        tmsg = f" → {players[target]['name']}" if target is not None else ""
        log(f"🤖 {curr['name']} 선언: {ACTIONS[act_name]['desc'].split(' ')[0]}{tmsg}")
        st.session_state.phase = "AWAIT_CHALLENGE"
        maybe_autoplay_delay()
        st.rerun()

    if not curr["alive"]:
        go_next_turn()

# ---------------------------
# AWAIT_CHALLENGE (행동 주장에 대한 도전)
# ---------------------------
if st.session_state.phase == "AWAIT_CHALLENGE":
    act = st.session_state.current_action
    actor_idx = act["actor_idx"]
    action_name = act["action_name"]
    claimed_role = act.get("claimed_role")
    actor = players[actor_idx]

    # 주장 역할이 없으면 도전 없이 다음
    if claimed_role is None:
        st.session_state.phase = "AWAIT_BLOCK"
        maybe_autoplay_delay()
        st.rerun()

    # 인간 도전 기회(내가 행동자가 아닐 때)
    can_i_challenge = (me["alive"] and actor_idx != 0 and not act["human_challenge_done"])

    if can_i_challenge:
        st.subheader("⚔️ 도전(Challenge) — 실시간 개입")
        st.write(f"{actor['name']}가 **{ROLE_ICON[claimed_role]} {ROLE_KO[claimed_role]}** 를 주장했습니다. 도전하시겠습니까?")
        c1, c2 = st.columns(2)
        if c1.button("도전한다!"):
            win = resolve_challenge(0, actor_idx, claimed_role, context=f"{action_name} 주장")
            finalize_deaths()
            if apply_influence_loss_if_pending():
                st.stop()
            if win:
                st.session_state.phase = "AWAIT_BLOCK"
            else:
                go_next_turn()
            st.rerun()

        if c2.button("패스"):
            act["human_challenge_done"] = True
            st.rerun()

        # 인간 선택 전에는 자동 진행하지 않음
        st.stop()

    # AI 도전(턴 순서대로)
    for i in turn_order_after(actor_idx):
        if i == 0:
            continue
        if players[i]["alive"] and ai_wants_challenge(i, claimed_role):
            log(f"🚨 도전: {players[i]['name']} → {actor['name']} ({ROLE_KO[claimed_role]} 의심)")
            win = resolve_challenge(i, actor_idx, claimed_role, context=f"{action_name} 주장")
            finalize_deaths()
            if apply_influence_loss_if_pending():
                st.stop()
            if win:
                st.session_state.phase = "AWAIT_BLOCK"
            else:
                go_next_turn()
            maybe_autoplay_delay()
            st.rerun()

    st.session_state.phase = "AWAIT_BLOCK"
    maybe_autoplay_delay()
    st.rerun()

# ---------------------------
# AWAIT_BLOCK (방해) — 해외원조는 전원, 암살/갈취는 대상만
# ---------------------------
if st.session_state.phase == "AWAIT_BLOCK":
    act = st.session_state.current_action
    action_name = act["action_name"]
    actor_idx = act["actor_idx"]
    target_idx = act.get("target_idx")
    info = ACTIONS[action_name]

    if not info["blockable"]:
        st.session_state.phase = "RESOLVE_ACTION"
        maybe_autoplay_delay()
        st.rerun()

    # 방해 가능한 사람들
    possible_blockers = []
    if action_name == "Foreign Aid":
        # 누구나 공작으로 방해 가능(행동자 제외)
        possible_blockers = [i for i in alive_players_idxs() if i != actor_idx]
        block_role_hint = "Duke"
    else:
        # 원래 룰: 대상만 방해 가능
        possible_blockers = [target_idx] if (target_idx is not None and players[target_idx]["alive"]) else []
        # 표시용
        block_role_hint = "Contessa" if action_name == "Assassinate" else "Captain"

    # 인간이 방해 가능하면 실시간 개입 UI 제공
    can_i_block = (0 in possible_blockers and me["alive"] and not act["human_block_done"])

    if can_i_block:
        st.subheader("🛡️ 방해(Block) — 실시간 개입")
        if action_name == "Foreign Aid":
            st.write("해외원조는 누구나 **공작(👑)** 으로 방해할 수 있습니다.")
            role_display = "Duke"
        elif action_name == "Assassinate":
            st.write("암살은 **대상만** 귀부인(👒)으로 방해할 수 있습니다. (타인을 대신 보호 불가)")
            role_display = "Contessa"
        else:
            st.write("갈취는 **대상만** 사령관(⚓)/대사(🤝)로 방해할 수 있습니다.")
            role_display = "Captain"

        c1, c2 = st.columns(2)
        if c1.button(f"방해한다! ({ROLE_ICON[role_display]} {ROLE_KO[role_display]})"):
            act["blocker_idx"] = 0
            act["block_role"] = role_display
            log(f"🛡️ 방해 선언: {me['name']} ({ROLE_ICON[role_display]} {ROLE_KO[role_display]} 주장)")
            st.session_state.phase = "AWAIT_BLOCK_CHALLENGE"
            st.rerun()

        if c2.button("패스"):
            act["human_block_done"] = True
            st.rerun()

        st.stop()

    # AI 방해(턴 순서대로)
    chosen = None
    chosen_role = None
    for i in turn_order_after(actor_idx):
        if i == 0:
            continue
        if i in possible_blockers and players[i]["alive"] and ai_wants_block(i, action_name, target_idx):
            chosen = i
            if action_name == "Foreign Aid":
                chosen_role = "Duke"
            elif action_name == "Assassinate":
                chosen_role = "Contessa"
            else:
                hand = get_alive_cards(i)
                # Steal 방해는 Captain 또는 Ambassador 주장 가능
                chosen_role = "Ambassador" if ("Ambassador" in hand and random.random() < 0.5) else "Captain"
            break

    if chosen is not None:
        act["blocker_idx"] = chosen
        act["block_role"] = chosen_role
        log(f"🛡️ 방해 선언: {players[chosen]['name']} ({ROLE_ICON[chosen_role]} {ROLE_KO[chosen_role]} 주장)")
        st.session_state.phase = "AWAIT_BLOCK_CHALLENGE"
        maybe_autoplay_delay()
        st.rerun()

    st.session_state.phase = "RESOLVE_ACTION"
    maybe_autoplay_delay()
    st.rerun()

# ---------------------------
# AWAIT_BLOCK_CHALLENGE (방해 주장에 대한 도전)
# ---------------------------
if st.session_state.phase == "AWAIT_BLOCK_CHALLENGE":
    act = st.session_state.current_action
    blocker_idx = act["blocker_idx"]
    block_role = act["block_role"]
    actor_idx = act["actor_idx"]

    blocker = players[blocker_idx]
    st.subheader("🧱 방해 발생")
    st.write(f"{blocker['name']}가 **{ROLE_ICON[block_role]} {ROLE_KO[block_role]}** 로 방해했습니다. 도전 가능!")

    # 인간 방해 도전 기회(내가 방해자가 아닐 때)
    can_i_challenge_block = (me["alive"] and blocker_idx != 0 and not act["human_block_challenge_done"])

    if can_i_challenge_block:
        c1, c2 = st.columns(2)
        if c1.button("방해에 도전한다!"):
            log(f"🚨 방해 도전: {me['name']} → {blocker['name']} ({ROLE_KO[block_role]} 의심)")
            win = resolve_challenge(0, blocker_idx, block_role, context="방해 주장")
            finalize_deaths()
            if apply_influence_loss_if_pending():
                st.stop()
            if win:
                log("🧱 방해 확정: 원래 행동 취소")
                go_next_turn()
            else:
                log("🧨 방해 무효: 원래 행동 강행")
                st.session_state.phase = "RESOLVE_ACTION"
                st.rerun()

        if c2.button("패스"):
            act["human_block_challenge_done"] = True
            st.rerun()

        st.stop()

    # AI 방해 도전(턴 순서대로)
    for i in turn_order_after(actor_idx):
        if i == 0 or i == blocker_idx:
            continue
        if players[i]["alive"] and ai_wants_challenge_block(i):
            log(f"🚨 방해 도전: {players[i]['name']} → {blocker['name']} ({ROLE_KO[block_role]} 의심)")
            win = resolve_challenge(i, blocker_idx, block_role, context="방해 주장")
            finalize_deaths()
            if apply_influence_loss_if_pending():
                st.stop()
            if win:
                log("🧱 방해 확정: 원래 행동 취소")
                go_next_turn()
            else:
                log("🧨 방해 무효: 원래 행동 강행")
                st.session_state.phase = "RESOLVE_ACTION"
            maybe_autoplay_delay()
            st.rerun()

    # 아무도 도전 안 하면 방해 인정 → 행동 취소
    log("🧱 방해가 인정되었습니다. 원래 행동은 취소됩니다.")
    go_next_turn()

# ---------------------------
# RESOLVE_ACTION (최종 실행)
# ---------------------------
if st.session_state.phase == "RESOLVE_ACTION":
    act = st.session_state.current_action
    actor = players[act["actor_idx"]]
    action_name = act["action_name"]

    # 비용 부족 방지(휴먼 실수 대비)
    if actor["coins"] < ACTIONS[action_name]["cost"]:
        log(f"⚠️ 비용 부족으로 행동 실패: {actor['name']} ({ACTIONS[action_name]['desc'].split(' ')[0]})")
        go_next_turn()

    execute_action_final()
