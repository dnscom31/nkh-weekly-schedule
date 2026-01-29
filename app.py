# app.py
import streamlit as st
import random
import time
import math

# ---------------------------
# 0) 페이지 / 모바일 최적화
# ---------------------------
st.set_page_config(page_title="Coup: Mobile Deluxe (2~8p)", layout="centered")

# ---------------------------
# 1) 상수 / 리소스
# ---------------------------
ROLES = ["Duke", "Assassin", "Captain", "Ambassador", "Contessa"]

ROLE_IMAGES = {
    "Duke": "https://images.unsplash.com/photo-1596727147705-01a298de3024?w=800&q=80",
    "Assassin": "https://images.unsplash.com/photo-1531384441138-2736e62e0919?w=800&q=80",
    "Captain": "https://images.unsplash.com/photo-1595590424283-b8f17842773f?w=800&q=80",
    "Ambassador": "https://images.unsplash.com/photo-1556761175-5973dc0f32e7?w=800&q=80",
    "Contessa": "https://images.unsplash.com/photo-1566492031773-4f4e44671857?w=800&q=80"
}

ROLE_KO = {
    "Duke": "공작",
    "Assassin": "암살자",
    "Captain": "사령관",
    "Ambassador": "대사",
    "Contessa": "귀부인"
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
        "desc": "갈취 (+2 훔치기, 대상이 사령관/대사로 방해 가능)"
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
# 2) 유틸 / 로그
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
    # 덱이 마르면(극단 상황) 역할에서 랜덤(최대한 피하도록 덱을 크게 만듦)
    return random.choice(ROLES)

def ensure_target_valid(action_name, actor_idx, target_idx):
    """대상 필요한 액션에서 대상이 살아있지 않으면 자동 보정"""
    info = ACTIONS[action_name]
    if not info["needs_target"]:
        return None
    if target_idx is None or not st.session_state.players[target_idx]["alive"] or target_idx == actor_idx:
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

def request_influence_loss(player_idx: int, reason: str):
    """영향력(카드) 1장 잃기: 인간은 선택 UI, AI는 자동 선택"""
    p = st.session_state.players[player_idx]
    alive_idxs = [i for i, a in enumerate(p["alive_cards"]) if a]
    if not alive_idxs:
        return  # 이미 탈락

    if p["is_ai"]:
        lose_i = random.choice(alive_idxs)
        lose_card = p["cards"][lose_i]
        p["alive_cards"][lose_i] = False
        log(f"💀 {p['name']} 영향력 1장 공개/제거: [{ROLE_KO[lose_card]}] ({reason})")
    else:
        # 인간 선택이 필요하면 state에 태스크로 걸어둔다
        st.session_state.pending_loss = {
            "player_idx": player_idx,
            "reason": reason
        }

def apply_influence_loss_if_pending():
    """인간이 영향력 잃을 때 선택 UI 제공"""
    if "pending_loss" not in st.session_state or st.session_state.pending_loss is None:
        return False

    info = st.session_state.pending_loss
    p = st.session_state.players[info["player_idx"]]
    if not p["alive"]:
        st.session_state.pending_loss = None
        return False

    alive_idxs = [i for i, a in enumerate(p["alive_cards"]) if a]
    if not alive_idxs:
        st.session_state.pending_loss = None
        return False

    st.warning(f"🃏 영향력 1장을 잃어야 합니다. 사유: {info['reason']}")
    st.write("공개/제거할 카드를 선택하세요.")

    cols = st.columns(len(alive_idxs))
    for col, card_i in zip(cols, alive_idxs):
        card = p["cards"][card_i]
        with col:
            st.image(ROLE_IMAGES[card], caption=f"{ROLE_KO[card]}", use_container_width=True)
            if st.button(f"이 카드 제거: {ROLE_KO[card]}", key=f"lose_{card_i}"):
                p["alive_cards"][card_i] = False
                log(f"💀 {p['name']} 영향력 1장 공개/제거: [{ROLE_KO[card]}] ({info['reason']})")
                st.session_state.pending_loss = None
                finalize_deaths()
                st.rerun()

    # 선택이 끝나기 전에는 진행 중지
    return True

def finalize_deaths():
    """0장 되면 탈락 처리"""
    for p in st.session_state.players:
        if p["alive"] and not any(p["alive_cards"]):
            p["alive"] = False
            log(f"⚰️ {p['name']} 탈락!")
    check_game_over()

def replace_revealed_card(target_idx: int, role: str):
    """도전에서 '진짜 역할'을 보여줬다면 그 카드 1장을 덱에 넣고 새 카드로 교체"""
    p = st.session_state.players[target_idx]
    for i in range(len(p["cards"])):
        if p["alive_cards"][i] and p["cards"][i] == role:
            st.session_state.deck.append(role)
            random.shuffle(st.session_state.deck)
            p["cards"][i] = draw_card()
            return

# ---------------------------
# 3) AI 의사결정(간단 버전)
# ---------------------------
def ai_pick_target(actor_idx: int):
    candidates = [i for i in alive_players_idxs() if i != actor_idx]
    return random.choice(candidates) if candidates else None

def ai_decide_action(ai_idx: int):
    ai = st.session_state.players[ai_idx]
    hand = get_alive_cards(ai_idx)
    target = ai_pick_target(ai_idx)

    # 10코인 강제 쿠(보드게임 룰)
    if ai["coins"] >= 10:
        return "Coup", target

    # 기본 전략(단순)
    if ai["coins"] >= 7 and target is not None:
        return "Coup", target
    if ai["coins"] >= 3 and target is not None and ("Assassin" in hand or random.random() < 0.25):
        return "Assassinate", target
    if "Duke" in hand or random.random() < 0.45:
        return "Tax", None
    if "Captain" in hand and target is not None and random.random() < 0.55:
        return "Steal", target
    if "Ambassador" in hand and random.random() < 0.2:
        return "Exchange", None
    return ("Foreign Aid", None) if random.random() < 0.6 else ("Income", None)

def ai_wants_challenge(ai_idx: int, claimed_role: str, actor_idx: int):
    """AI가 역할 주장에 도전할지"""
    if claimed_role is None:
        return False
    # 너무 과격하지 않게(재미+균형)
    hand = get_alive_cards(ai_idx)
    if hand.count(claimed_role) == 2:
        return True  # 강한 확신(하우스)
    # 랜덤 도전
    return random.random() < 0.12

def ai_wants_block(ai_idx: int, action_name: str, actor_idx: int, target_idx: int):
    """AI가 방해(block)할지. Foreign Aid는 누구나 가능, 나머지는 대상만"""
    info = ACTIONS[action_name]
    if not info["blockable"]:
        return False

    # Foreign Aid: 누구나 Duke로 방해 가능
    if action_name == "Foreign Aid":
        hand = get_alive_cards(ai_idx)
        if "Duke" in hand:
            return random.random() < 0.75
        return random.random() < 0.15

    # 그 외: 대상만 방어 가능
    if target_idx != ai_idx:
        return False

    hand = get_alive_cards(ai_idx)
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
# 4) 게임 상태(페이즈) 설계
# ---------------------------
# phase:
#   SETUP
#   TURN_START (행동 선택)
#   AWAIT_CHALLENGE (행동 주장에 대한 도전 창)
#   AWAIT_BLOCK (방해 창)
#   AWAIT_BLOCK_CHALLENGE (방해 주장에 대한 도전 창)
#   RESOLVE_ACTION (최종 실행)
#
# current_action:
#   {actor_idx, action_name, target_idx, claimed_role, blocker_idx, block_role, challenger_idx, block_challenger_idx}

def reset_game(n_players: int):
    st.session_state.clear()
    st.session_state.phase = "TURN_START"
    st.session_state.log = ["게임 시작! (모바일 로그 중심 UI)"]
    st.session_state.n_players = n_players

    # 8인 지원을 위한 덱 확장(하우스룰)
    copies = 4 if n_players >= 7 else 3
    deck = []
    for r in ROLES:
        deck.extend([r] * copies)
    random.shuffle(deck)
    st.session_state.deck = deck

    # 플레이어 생성(0번만 인간, 나머지 AI)
    st.session_state.players = []
    names = ["나 (Player)"] + [f"AI {i} (Bot)" for i in range(1, n_players)]
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

    st.session_state.current_action = None
    st.session_state.pending_loss = None

    # 자동 진행 / 속도
    st.session_state.autoplay = True
    st.session_state.speed = 0.9  # 초

    log(f"첫 턴: {st.session_state.players[st.session_state.turn_idx]['name']}")

def get_current_player():
    return st.session_state.players[st.session_state.turn_idx]

def go_next_turn():
    st.session_state.turn_idx = next_alive_idx(st.session_state.turn_idx)
    st.session_state.current_action = None
    st.session_state.phase = "TURN_START"
    log(f"다음 턴: {st.session_state.players[st.session_state.turn_idx]['name']}")
    st.rerun()

# ---------------------------
# 5) 도전/방해/실행 처리
# ---------------------------
def resolve_challenge(challenger_idx: int, target_idx: int, role_claimed: str, context: str):
    """도전 결과 처리: 진짜면 도전자 영향력 잃고, 대상은 카드 교체 / 가짜면 대상이 영향력 잃음"""
    challenger = st.session_state.players[challenger_idx]
    target = st.session_state.players[target_idx]
    target_hand = get_alive_cards(target_idx)

    if role_claimed in target_hand:
        log(f"🛡️ 인증 성공! {target['name']}는 [{ROLE_KO[role_claimed]}] 보유 ({context})")
        log(f"❌ 도전 실패: {challenger['name']} 영향력 1장 잃음")
        request_influence_loss(challenger_idx, reason=f"도전 실패({context})")
        replace_revealed_card(target_idx, role_claimed)
        return True  # target wins
    else:
        log(f"🤥 블러핑 적발! {target['name']}는 [{ROLE_KO[role_claimed]}] 없음 ({context})")
        log(f"⚔️ 도전 성공: {target['name']} 영향력 1장 잃음")
        request_influence_loss(target_idx, reason=f"도전 성공으로 패배({context})")
        return False  # challenger wins

def execute_action_final():
    act = st.session_state.current_action
    actor = st.session_state.players[act["actor_idx"]]
    action_name = act["action_name"]
    target = st.session_state.players[act["target_idx"]] if act["target_idx"] is not None else None

    # 비용 지불
    actor["coins"] -= ACTIONS[action_name]["cost"]

    # 실행
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
        # 보드게임 느낌: 살아있는 카드 수만큼 유지, 덱에서 2장 확인해 교체(단순화: 랜덤 유지)
        new_cards = [draw_card(), draw_card()]
        current_alive = get_alive_cards(actor["id"])
        pool = current_alive + new_cards
        random.shuffle(pool)
        lives = sum(actor["alive_cards"])
        keep = pool[:lives]
        # 나머지 덱 반환
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

def maybe_autoplay_delay():
    """자동 진행일 때만 딜레이"""
    if st.session_state.autoplay:
        time.sleep(float(st.session_state.speed))

# ---------------------------
# 6) 초기: 설정 화면(플레이 인원)
# ---------------------------
if "n_players" not in st.session_state:
    st.title("🃏 Coup (쿠) : 모바일 실감형 (2~8인)")
    st.write("✅ 목표: 로그 중심 + 자동진행 속도조절 + 모든 플레이어 개입(도전/방해/방해도전)")
    n = st.slider("플레이 인원수", min_value=2, max_value=8, value=4, step=1)
    st.info("주의: 7~8인은 보드게임 원본(최대 6인) 확장 하우스룰로 덱(역할당 4장)을 사용합니다.")
    if st.button("게임 시작"):
        reset_game(n)
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
        reset_game(n)
        st.rerun()

# ---------------------------
# 8) 상단: 현재 선언 + 로그 (모바일 1열)
# ---------------------------
st.title("🃏 Coup (쿠) : 모바일 실감형")

# AI 상태는 접어서 보기
with st.expander("🤖 플레이어 상태(접기/펼치기)", expanded=False):
    for i, p in enumerate(st.session_state.players):
        if not p["alive"]:
            st.write(f"⚰️ {p['name']} (탈락)")
            continue
        alive_cnt = sum(p["alive_cards"])
        turn_mark = "👉" if i == st.session_state.turn_idx else ""
        st.write(f"{turn_mark} **{p['name']}** | 💰 {p['coins']} | 🃏 {alive_cnt}/2")

# 현재 선언/상황
if st.session_state.current_action:
    act = st.session_state.current_action
    actor = st.session_state.players[act["actor_idx"]]["name"]
    action = act["action_name"]
    target_msg = ""
    if act.get("target_idx") is not None:
        target_msg = f" → {st.session_state.players[act['target_idx']]['name']}"
    st.warning(f"📢 현재 선언: **{actor} [{ACTIONS[action]['desc'].split(' ')[0]}]**{target_msg}")

st.header("📜 로그")
log_box = st.container(height=260)
for m in st.session_state.log:
    log_box.text(m)

st.divider()

# 영향력(카드) 잃기 선택이 걸려있으면 여기서 처리(이게 있으면 진행 중단)
if apply_influence_loss_if_pending():
    st.stop()

# ---------------------------
# 9) 내 카드 표시(모바일)
# ---------------------------
me = st.session_state.players[0]
if me["alive"]:
    st.subheader("👤 내 상태")
    st.metric("💰 코인", me["coins"])
    ccols = st.columns(2)
    for j in range(2):
        with ccols[j]:
            card = me["cards"][j]
            alive = me["alive_cards"][j]
            st.image(ROLE_IMAGES[card], caption=f"{'' if alive else '❌'} {ROLE_KO[card]}", use_container_width=True)
else:
    st.error("당신은 탈락했습니다. (관전)")
    # 관전이어도 자동진행은 계속될 수 있음

st.divider()

# ---------------------------
# 10) 메인 루프(페이즈별)
# ---------------------------
curr = get_current_player()

# (A) TURN_START: 행동 선택
if st.session_state.phase == "TURN_START":
    # 10코인 강제 쿠(보드게임 룰)
    if curr["coins"] >= 10:
        target = ai_pick_target(curr["id"]) if curr["is_ai"] else None

        st.error("💥 10코인 이상입니다! 이번 턴은 '쿠'를 반드시 해야 합니다.")
        if curr["is_ai"]:
            # AI는 자동 선택
            target = ensure_target_valid("Coup", curr["id"], target)
            st.session_state.current_action = {
                "actor_idx": curr["id"],
                "action_name": "Coup",
                "target_idx": target,
                "claimed_role": None,
                "blocker_idx": None,
                "block_role": None,
                "challenger_idx": None,
                "block_challenger_idx": None,
            }
            log(f"💥 강제 쿠 선언: {curr['name']} → {st.session_state.players[target]['name']}")
            st.session_state.phase = "AWAIT_CHALLENGE"
            maybe_autoplay_delay()
            st.rerun()
        else:
            # 인간은 대상 선택
            candidates = [i for i in alive_players_idxs() if i != 0]
            if candidates:
                t = st.selectbox("대상 선택", candidates, format_func=lambda x: st.session_state.players[x]["name"])
                if st.button("Coup(쿠) 선언"):
                    st.session_state.current_action = {
                        "actor_idx": 0,
                        "action_name": "Coup",
                        "target_idx": t,
                        "claimed_role": None,
                        "blocker_idx": None,
                        "block_role": None,
                        "challenger_idx": None,
                        "block_challenger_idx": None,
                    }
                    log(f"💥 강제 쿠 선언: {curr['name']} → {st.session_state.players[t]['name']}")
                    st.session_state.phase = "AWAIT_CHALLENGE"
                    st.rerun()
            else:
                # 대상이 없으면 게임 종료 케이스에 가깝다
                check_game_over()
        st.stop()

    # 일반 턴
    if curr["id"] == 0 and curr["alive"]:
        st.subheader("⚡ 내 차례: 행동 선택")

        # 대상 선택(필요한 액션용)
        alive_targets = [i for i in alive_players_idxs() if i != 0]
        target_sel = None
        if alive_targets:
            target_sel = st.selectbox("대상(공격 액션일 때)", alive_targets,
                                      format_func=lambda x: st.session_state.players[x]["name"])

        # 버튼을 큰 단위로
        # (모바일에서 한 줄에 너무 많으면 불편 -> 2열씩)
        col1, col2 = st.columns(2)
        if col1.button("소득 (+1)"):
            st.session_state.current_action = {
                "actor_idx": 0, "action_name": "Income", "target_idx": None,
                "claimed_role": None, "blocker_idx": None, "block_role": None,
                "challenger_idx": None, "block_challenger_idx": None
            }
            log("👤 내가 '소득' 선언")
            st.session_state.phase = "AWAIT_CHALLENGE"
            st.rerun()

        if col2.button("해외원조 (+2)"):
            st.session_state.current_action = {
                "actor_idx": 0, "action_name": "Foreign Aid", "target_idx": None,
                "claimed_role": None, "blocker_idx": None, "block_role": None,
                "challenger_idx": None, "block_challenger_idx": None
            }
            log("👤 내가 '해외원조' 선언")
            st.session_state.phase = "AWAIT_CHALLENGE"
            st.rerun()

        col3, col4 = st.columns(2)
        if col3.button("세금징수 (+3, 공작)"):
            st.session_state.current_action = {
                "actor_idx": 0, "action_name": "Tax", "target_idx": None,
                "claimed_role": "Duke", "blocker_idx": None, "block_role": None,
                "challenger_idx": None, "block_challenger_idx": None
            }
            log("👤 내가 '세금징수(공작 주장)' 선언")
            st.session_state.phase = "AWAIT_CHALLENGE"
            st.rerun()

        if col4.button("교환 (대사)"):
            st.session_state.current_action = {
                "actor_idx": 0, "action_name": "Exchange", "target_idx": None,
                "claimed_role": "Ambassador", "blocker_idx": None, "block_role": None,
                "challenger_idx": None, "block_challenger_idx": None
            }
            log("👤 내가 '교환(대사 주장)' 선언")
            st.session_state.phase = "AWAIT_CHALLENGE"
            st.rerun()

        col5, col6 = st.columns(2)
        if col5.button("갈취 (+2, 사령관)"):
            if target_sel is None:
                st.warning("대상을 선택하세요.")
            else:
                st.session_state.current_action = {
                    "actor_idx": 0, "action_name": "Steal", "target_idx": target_sel,
                    "claimed_role": "Captain", "blocker_idx": None, "block_role": None,
                    "challenger_idx": None, "block_challenger_idx": None
                }
                log(f"👤 내가 '갈취(사령관 주장)' 선언 → {st.session_state.players[target_sel]['name']}")
                st.session_state.phase = "AWAIT_CHALLENGE"
                st.rerun()

        if col6.button("암살 (-3, 암살자)"):
            if me["coins"] < 3:
                st.warning("코인이 3 미만이라 암살 불가")
            elif target_sel is None:
                st.warning("대상을 선택하세요.")
            else:
                st.session_state.current_action = {
                    "actor_idx": 0, "action_name": "Assassinate", "target_idx": target_sel,
                    "claimed_role": "Assassin", "blocker_idx": None, "block_role": None,
                    "challenger_idx": None, "block_challenger_idx": None
                }
                log(f"👤 내가 '암살(암살자 주장)' 선언 → {st.session_state.players[target_sel]['name']}")
                st.session_state.phase = "AWAIT_CHALLENGE"
                st.rerun()

        # 쿠는 별도
        if st.button("쿠 (-7, 방어불가)"):
            if me["coins"] < 7:
                st.warning("코인이 7 미만이라 쿠 불가")
            elif target_sel is None:
                st.warning("대상을 선택하세요.")
            else:
                st.session_state.current_action = {
                    "actor_idx": 0, "action_name": "Coup", "target_idx": target_sel,
                    "claimed_role": None, "blocker_idx": None, "block_role": None,
                    "challenger_idx": None, "block_challenger_idx": None
                }
                log(f"👤 내가 '쿠' 선언 → {st.session_state.players[target_sel]['name']}")
                st.session_state.phase = "AWAIT_CHALLENGE"
                st.rerun()

        st.stop()

    # AI 턴
    if curr["is_ai"] and curr["alive"]:
        act_name, target = ai_decide_action(curr["id"])
        target = ensure_target_valid(act_name, curr["id"], target)

        st.session_state.current_action = {
            "actor_idx": curr["id"],
            "action_name": act_name,
            "target_idx": target,
            "claimed_role": ACTIONS[act_name]["claim_role"],
            "blocker_idx": None,
            "block_role": None,
            "challenger_idx": None,
            "block_challenger_idx": None,
        }

        tmsg = ""
        if target is not None:
            tmsg = f" → {st.session_state.players[target]['name']}"
        log(f"🤖 {curr['name']} 행동 선언: {ACTIONS[act_name]['desc'].split(' ')[0]}{tmsg}")
        st.session_state.phase = "AWAIT_CHALLENGE"
        maybe_autoplay_delay()
        st.rerun()

    # 혹시 턴 플레이어가 죽어있으면 넘김
    if not curr["alive"]:
        go_next_turn()

# (B) AWAIT_CHALLENGE: 행동 주장(있다면)에 대한 도전 창
if st.session_state.phase == "AWAIT_CHALLENGE":
    act = st.session_state.current_action
    actor_idx = act["actor_idx"]
    action_name = act["action_name"]
    claimed_role = act.get("claimed_role")
    actor = st.session_state.players[actor_idx]

    # 도전 대상은 "역할 주장"이 있을 때만 의미 있음
    if claimed_role is None:
        # 도전 자체가 없으니 바로 방해 단계로
        st.session_state.phase = "AWAIT_BLOCK"
        maybe_autoplay_delay()
        st.rerun()

    # 인간(나)이 도전 가능(내가 행동자가 아닐 때)
    can_i_challenge = (me["alive"] and actor_idx != 0 and claimed_role is not None)

    if can_i_challenge:
        st.subheader("⚔️ 도전(Challenge) 기회")
        st.write(f"{actor['name']}가 **[{ROLE_KO[claimed_role]}]** 역할을 주장했습니다.")
        c1, c2 = st.columns(2)
        if c1.button("도전한다! (Challenge)"):
            # 도전 처리(인간이 우선권을 갖는 느낌)
            win = resolve_challenge(0, actor_idx, claimed_role, context=f"{action_name} 주장")
            finalize_deaths()
            if apply_influence_loss_if_pending():
                st.stop()
            if win:
                # 인증 성공 -> 행동 계속
                st.session_state.phase = "AWAIT_BLOCK"
            else:
                # 블러핑 적발 -> 행동 실패, 턴 종료
                go_next_turn()
            maybe_autoplay_delay()
            st.rerun()

        if c2.button("패스 (도전 안 함)"):
            pass  # 아래 AI 판단으로 넘어감

    # AI들 도전 판단: 턴 순서대로(실감)
    if True:
        order = turn_order_after(actor_idx)
        chosen = None
        for i in order:
            if i == 0:
                continue  # 인간은 위에서 처리(패스 했으면 AI로)
            if st.session_state.players[i]["alive"]:
                if ai_wants_challenge(i, claimed_role, actor_idx):
                    chosen = i
                    break

        if chosen is not None:
            log(f"🚨 도전 발생: {st.session_state.players[chosen]['name']} → {actor['name']} ({ROLE_KO[claimed_role]} 주장 의심)")
            win = resolve_challenge(chosen, actor_idx, claimed_role, context=f"{action_name} 주장")
            finalize_deaths()
            if apply_influence_loss_if_pending():
                st.stop()
            if win:
                st.session_state.phase = "AWAIT_BLOCK"
            else:
                go_next_turn()
            maybe_autoplay_delay()
            st.rerun()

    # 아무도 도전 안 하면 방해 단계로
    st.session_state.phase = "AWAIT_BLOCK"
    maybe_autoplay_delay()
    st.rerun()

# (C) AWAIT_BLOCK: 방해(블록) 기회
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

    # 방해 가능한 플레이어 결정
    possible_blockers = []
    if action_name == "Foreign Aid":
        # 누구나 공작으로 방해 가능(행동자 제외)
        possible_blockers = [i for i in alive_players_idxs() if i != actor_idx]
        block_role = "Duke"
    else:
        # 대상만 방어 가능
        if target_idx is not None and st.session_state.players[target_idx]["alive"]:
            possible_blockers = [target_idx]
        block_role = info["block_roles"][0]  # Assassinate=Contessa, Steal=Captain/Ambassador(표기용)

    # 인간이 방해할 수 있으면 UI 제공
    can_i_block = (0 in possible_blockers and me["alive"])
    if can_i_block:
        st.subheader("🛡️ 방해(Block) 기회")
        if action_name == "Foreign Aid":
            st.write("해외원조는 누구나 **공작**으로 방해할 수 있습니다.")
            display_role = "Duke"
        elif action_name == "Assassinate":
            st.write("암살은 대상이 **귀부인**으로 방해할 수 있습니다.")
            display_role = "Contessa"
        else:
            st.write("갈취는 대상이 **사령관/대사**로 방해할 수 있습니다.")
            display_role = "Captain"

        c1, c2 = st.columns(2)
        if c1.button(f"방해한다! ({ROLE_KO[display_role]})"):
            act["blocker_idx"] = 0
            act["block_role"] = display_role
            log(f"🛡️ 방해 선언: {me['name']} ({ROLE_KO[display_role]} 주장)")
            st.session_state.phase = "AWAIT_BLOCK_CHALLENGE"
            st.rerun()
        if c2.button("패스 (방해 안 함)"):
            pass

    # AI 방해 판단: 턴 순서대로(실감)
    chosen = None
    chosen_role = None

    # Foreign Aid는 다수 가능 -> 턴 순서대로 먼저 방해하는 1명만 성립(보드게임에서 누가 먼저 말했냐 느낌)
    order = turn_order_after(actor_idx)
    for i in order:
        if i in possible_blockers and st.session_state.players[i]["alive"]:
            if i == 0:
                continue
            if ai_wants_block(i, action_name, actor_idx, target_idx):
                chosen = i
                if action_name == "Foreign Aid":
                    chosen_role = "Duke"
                elif action_name == "Assassinate":
                    chosen_role = "Contessa"
                else:
                    # Steal: Captain/Ambassador 중 하나 주장(랜덤)
                    hand = get_alive_cards(i)
                    if "Ambassador" in hand and random.random() < 0.5:
                        chosen_role = "Ambassador"
                    else:
                        chosen_role = "Captain"
                break

    if chosen is not None:
        act["blocker_idx"] = chosen
        act["block_role"] = chosen_role
        log(f"🛡️ 방해 선언: {st.session_state.players[chosen]['name']} ({ROLE_KO[chosen_role]} 주장)")
        st.session_state.phase = "AWAIT_BLOCK_CHALLENGE"
        maybe_autoplay_delay()
        st.rerun()

    # 방해가 없으면 실행
    st.session_state.phase = "RESOLVE_ACTION"
    maybe_autoplay_delay()
    st.rerun()

# (D) AWAIT_BLOCK_CHALLENGE: 방해 주장에 대한 도전 창
if st.session_state.phase == "AWAIT_BLOCK_CHALLENGE":
    act = st.session_state.current_action
    blocker_idx = act["blocker_idx"]
    block_role = act["block_role"]
    actor_idx = act["actor_idx"]

    blocker = st.session_state.players[blocker_idx]
    st.subheader("🛡️ 방해가 선언되었습니다")
    st.write(f"{blocker['name']}가 **[{ROLE_KO[block_role]}]** 자격으로 방해했습니다.")

    # 인간이 방해에 도전 가능(내가 방해자가 아닐 때)
    can_i_challenge_block = (me["alive"] and blocker_idx != 0)

    if can_i_challenge_block:
        c1, c2 = st.columns(2)
        if c1.button("방해에 도전한다! (Challenge Block)"):
            log(f"🚨 방해 도전: {me['name']} → {blocker['name']} ({ROLE_KO[block_role]} 의심)")
            win = resolve_challenge(0, blocker_idx, block_role, context="방해 주장")
            finalize_deaths()
            if apply_influence_loss_if_pending():
                st.stop()

            if win:
                # 방해자가 진짜였다 -> 방해 성공, 원래 행동 취소, 턴 종료(행동자 턴은 소비됨)
                log("🧱 방해 확정! 원래 행동은 취소됩니다.")
                go_next_turn()
            else:
                # 방해자가 거짓 -> 방해 무효, 행동 실행
                log("🧨 방해 무효! 원래 행동이 강행됩니다.")
                st.session_state.phase = "RESOLVE_ACTION"
                maybe_autoplay_delay()
                st.rerun()

        if c2.button("패스 (도전 안 함)"):
            pass

    # AI들이 방해에 도전할지: 턴 순서대로(실감)
    order = turn_order_after(actor_idx)
    chosen = None
    for i in order:
        if i == blocker_idx:
            continue
        if i == 0:
            continue
        if st.session_state.players[i]["alive"]:
            if ai_wants_challenge_block(i):
                chosen = i
                break

    if chosen is not None:
        log(f"🚨 방해 도전: {st.session_state.players[chosen]['name']} → {blocker['name']} ({ROLE_KO[block_role]} 의심)")
        win = resolve_challenge(chosen, blocker_idx, block_role, context="방해 주장")
        finalize_deaths()
        if apply_influence_loss_if_pending():
            st.stop()

        if win:
            log("🧱 방해 확정! 원래 행동은 취소됩니다.")
            go_next_turn()
        else:
            log("🧨 방해 무효! 원래 행동이 강행됩니다.")
            st.session_state.phase = "RESOLVE_ACTION"
            maybe_autoplay_delay()
            st.rerun()

    # 아무도 도전 안 하면 방해 확정 -> 행동 취소 -> 턴 종료
    log("🧱 방해가 인정되었습니다. 원래 행동은 취소됩니다.")
    go_next_turn()

# (E) RESOLVE_ACTION: 최종 실행
if st.session_state.phase == "RESOLVE_ACTION":
    act = st.session_state.current_action
    action_name = act["action_name"]
    actor = st.session_state.players[act["actor_idx"]]

    # 방해 확정이 아닌 상태에서만 여기로 옴
    # 비용 부족 방지(인간이 실수로 눌렀을 때 대비)
    if actor["coins"] < ACTIONS[action_name]["cost"]:
        log(f"⚠️ 비용 부족으로 행동 실패: {actor['name']} ({ACTIONS[action_name]['desc'].split(' ')[0]})")
        go_next_turn()

    execute_action_final()
