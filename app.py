import streamlit as st
import random
import time

# --- 설정 및 상수 ---
st.set_page_config(page_title="Coup: The Python Game", layout="wide")

ROLES = ["Duke", "Assassin", "Captain", "Ambassador", "Contessa"]
ROLE_KOREAN = {
    "Duke": "공작",
    "Assassin": "암살자",
    "Captain": "사령관",
    "Ambassador": "대사",
    "Contessa": "귀부인"
}

# 무료 아바타 이미지 (DiceBear API 사용)
ROLE_IMAGES = {
    "Duke": "https://api.dicebear.com/7.x/avataaars/svg?seed=Duke&clothing=blazerAndShirt&top=shortHairTheCaesar",
    "Assassin": "https://api.dicebear.com/7.x/avataaars/svg?seed=Assassin&clothing=hoodie&accessories=eyepatch",
    "Captain": "https://api.dicebear.com/7.x/avataaars/svg?seed=Captain&clothing=graphicShirt&top=hat",
    "Ambassador": "https://api.dicebear.com/7.x/avataaars/svg?seed=Ambassador&clothing=collarAndSweater&accessories=round",
    "Contessa": "https://api.dicebear.com/7.x/avataaars/svg?seed=Contessa&clothing=dress&top=longHairMiaWallace"
}

ACTIONS = {
    "Income": {"cost": 0, "role": None, "desc": "소득 (+1원, 방어 불가)"},
    "Foreign Aid": {"cost": 0, "role": None, "desc": "해외원조 (+2원, 공작이 방어 가능)"},
    "Tax": {"cost": 0, "role": "Duke", "desc": "세금징수 (+3원, 공작 능력)"},
    "Steal": {"cost": 0, "role": "Captain", "desc": "갈취 (+2원 뺏기, 사령관 능력)"},
    "Assassinate": {"cost": 3, "role": "Assassin", "desc": "암살 (코인 3원 소모, 카드 제거)"},
    "Exchange": {"cost": 0, "role": "Ambassador", "desc": "교환 (카드 2장 교체)"},
    "Coup": {"cost": 7, "role": None, "desc": "쿠 (코인 7원 소모, 방어 불가 일격)"},
}

# --- 게임 상태 초기화 ---
if 'initialized' not in st.session_state:
    st.session_state.initialized = True
    st.session_state.deck = []
    st.session_state.log = ["게임이 시작되었습니다."]
    st.session_state.turn = "Player"  # Player or AI
    st.session_state.phase = "SELECT_ACTION"  # SELECT_ACTION, REACTION_WAIT, RESOLVE
    
    # 덱 생성 (각 3장)
    deck = []
    for r in ROLES:
        deck.extend([r] * 3)
    random.shuffle(deck)
    st.session_state.deck = deck
    
    # 플레이어 초기화
    st.session_state.player = {
        "name": "나 (Player)",
        "coins": 2,
        "cards": [st.session_state.deck.pop(), st.session_state.deck.pop()],
        "alive_cards": [True, True] # 카드 생존 여부
    }
    
    st.session_state.ai = {
        "name": "AI (Computer)",
        "coins": 2,
        "cards": [st.session_state.deck.pop(), st.session_state.deck.pop()],
        "alive_cards": [True, True]
    }
    
    # 임시 상태 저장소
    st.session_state.current_action = None # {actor, action_name, target}

# --- 헬퍼 함수들 ---
def log(msg):
    st.session_state.log.insert(0, msg)

def get_alive_cards(player_dict):
    return [c for idx, c in enumerate(player_dict["cards"]) if player_dict["alive_cards"][idx]]

def check_game_over():
    p_alive = any(st.session_state.player["alive_cards"])
    ai_alive = any(st.session_state.ai["alive_cards"])
    if not p_alive:
        st.error("패배했습니다... AI가 승리했습니다.")
        st.stop()
    if not ai_alive:
        st.balloons()
        st.success("축하합니다! 승리했습니다!")
        st.stop()

def draw_card():
    if st.session_state.deck:
        return st.session_state.deck.pop()
    else:
        return "Unknown"

# --- AI 로직 ---
def ai_decide_action():
    ai = st.session_state.ai
    hand = get_alive_cards(ai)
    
    # 1. 킬각: 돈이 7원 이상이면 무조건 쿠
    if ai["coins"] >= 7:
        return "Coup"
    
    # 2. 공격: 돈이 3원 이상이고 암살자가 있거나, 없어도 과감하게(30%) 암살 시도
    if ai["coins"] >= 3:
        if "Assassin" in hand or random.random() < 0.3:
            return "Assassinate"

    # 3. 돈 벌기: 공작이 있으면 100% 세금, 없어도 60% 확률로 블러핑
    if "Duke" in hand or random.random() < 0.6:
        return "Tax"
    
    # 4. 견제: 사령관이 있으면 갈취
    if "Captain" in hand:
        return "Steal"
        
    # 5. 기본: 그냥 소득이나 해외원조
    if random.random() < 0.5:
        return "Foreign Aid"
    else:
        return "Income"

def ai_react_to_player(action_name):
    """플레이어의 행동에 대해 AI가 도전(Challenge)할지 방어(Block)할지 결정"""
    ai = st.session_state.ai
    hand = get_alive_cards(ai)
    player_action = ACTIONS[action_name]
    
    # 1. 도전(Challenge) 로직
    needed_role = player_action['role']
    if needed_role:
        my_dupes = hand.count(needed_role)
        if my_dupes == 2: 
            return "Challenge"
    
    if needed_role and random.random() < 0.2:
        return "Challenge"

    # 2. 방어(Block) 로직
    if action_name == "Assassinate":
        if "Contessa" in hand: return "Block"
        if random.random() < 0.4: return "Block"
        
    if action_name == "Steal":
        if "Captain" in hand or "Ambassador" in hand: return "Block"
        if random.random() < 0.3: return "Block"

    if action_name == "Foreign Aid":
        if "Duke" in hand: return "Block"
        if random.random() < 0.2: return "Block"

    return "Pass"

# --- 핵심 게임 로직 처리 ---

def execute_action_result(actor_key, action_name):
    actor = st.session_state.player if actor_key == "Player" else st.session_state.ai
    target = st.session_state.ai if actor_key == "Player" else st.session_state.player
    
    cost = ACTIONS[action_name]["cost"]
    actor["coins"] -= cost
    
    log(f"✅ {actor['name']}의 [{ACTIONS[action_name]['desc'].split(' ')[0]}] 행동이 성공했습니다.")

    if action_name == "Income":
        actor["coins"] += 1
    elif action_name == "Foreign Aid":
        actor["coins"] += 2
    elif action_name == "Tax":
        actor["coins"] += 3
    elif action_name == "Steal":
        steal_amount = min(2, target["coins"])
        target["coins"] -= steal_amount
        actor["coins"] += steal_amount
        log(f"{steal_amount}원을 뺏었습니다.")
    elif action_name == "Assassinate":
        lose_life(target)
        log(f"{target['name']}가 암살당해 카드를 잃었습니다.")
    elif action_name == "Coup":
        lose_life(target)
        log(f"{target['name']}가 쿠를 맞아 카드를 잃었습니다.")
    elif action_name == "Exchange":
        new_cards = [draw_card(), draw_card()]
        current_hand = get_alive_cards(actor)
        pool = current_hand + new_cards
        random.shuffle(pool)
        
        lives = sum(actor["alive_cards"])
        keep = pool[:lives]
        return_deck = pool[lives:]
        
        st.session_state.deck.extend(return_deck)
        random.shuffle(st.session_state.deck)
        
        alive_idx = 0
        for i in range(2):
            if actor["alive_cards"][i]:
                actor["cards"][i] = keep[alive_idx]
                alive_idx += 1
        log(f"{actor['name']}가 카드를 교환했습니다.")

    st.session_state.current_action = None
    st.session_state.turn = "AI" if actor_key == "Player" else "Player"
    st.session_state.phase = "SELECT_ACTION"
    st.rerun()

def lose_life(victim_dict):
    for i in range(2):
        if victim_dict["alive_cards"][i]:
            victim_dict["alive_cards"][i] = False
            log(f"💀 {victim_dict['name']}의 카드 [{ROLE_KOREAN[victim_dict['cards'][i]]}] 제거됨!")
            break
    check_game_over()

def resolve_challenge(challenger_key, target_key, role_claimed):
    challenger = st.session_state.player if challenger_key == "Player" else st.session_state.ai
    target = st.session_state.player if target_key == "Player" else st.session_state.ai
    
    target_hand = get_alive_cards(target)
    
    if role_claimed in target_hand:
        # 블러핑 아님: 도전자 패배
        log(f"🛡️ {target['name']}가 {ROLE_KOREAN[role_claimed]} 카드를 인증했습니다! (참말)")
        log(f"❌ {challenger['name']}의 도전 실패! 패널티로 카드를 잃습니다.")
        lose_life(challenger)
        
        st.session_state.deck.append(role_claimed)
        random.shuffle(st.session_state.deck)
        
        for i in range(2):
            if target["alive_cards"][i] and target["cards"][i] == role_claimed:
                target["cards"][i] = draw_card()
                break
        
        return "CHALLENGE_FAILED" 
    else:
        # 블러핑 걸림: 타겟 패배
        log(f"🤥 {target['name']}는 {ROLE_KOREAN[role_claimed]} 카드가 없었습니다! (거짓말)")
        log(f"⚔️ {challenger['name']}의 도전 성공!")
        lose_life(target)
        return "CHALLENGE_SUCCESS" 

# --- UI 렌더링 ---

with st.sidebar:
    st.header("📜 게임 로그")
    for msg in st.session_state.log:
        st.text(msg)

st.title("🃏 Coup (쿠) : 심리 전략 게임")

col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    st.subheader(f"🤖 {st.session_state.ai['name']}")
    st.metric("Coins", st.session_state.ai["coins"])
    
    ai_cols = st.columns(2)
    for i in range(2):
        card_name = st.session_state.ai["cards"][i]
        is_alive = st.session_state.ai["alive_cards"][i]
        with ai_cols[i]:
            if not is_alive:
                st.image(ROLE_IMAGES[card_name], caption=f"❌ {ROLE_KOREAN[card_name]}", width=80)
            else:
                st.info("뒷면") 

with col2:
    if st.session_state.current_action:
        act = st.session_state.current_action
        st.info(f"📢 현재 상황: {act['actor']}가 [{ACTIONS[act['action']]['desc']}] 시도 중...")

with col3:
    st.subheader(f"👤 {st.session_state.player['name']}")
    st.metric("Coins", st.session_state.player["coins"])
    
    p_cols = st.columns(2)
    for i in range(2):
        card_name = st.session_state.player["cards"][i]
        is_alive = st.session_state.player["alive_cards"][i]
        with p_cols[i]:
            opacity = 1.0 if is_alive else 0.5
            caption = ROLE_KOREAN[card_name] if is_alive else f"❌ {ROLE_KOREAN[card_name]}"
            st.image(ROLE_IMAGES[card_name], caption=caption, width=80)

st.divider()

# --- 게임 컨트롤러 ---

# 1. 플레이어 턴
if st.session_state.turn == "Player" and st.session_state.phase == "SELECT_ACTION":
    st.subheader("⚡ 당신의 차례입니다. 행동을 선택하세요.")
    
    if st.session_state.player["coins"] >= 10:
        if st.button("Coup (쿠) - 코인 10개 초과 강제"):
            st.session_state.current_action = {"actor": "Player", "action": "Coup", "target": "AI"}
            execute_action_result("Player", "Coup")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c5, c6, c7 = st.columns(3)
        
        if c1.button("소득 (+1)"):
            st.session_state.current_action = {"actor": "Player", "action": "Income", "target": "AI"}
            st.session_state.phase = "REACTION_WAIT"
            st.rerun()
            
        if c2.button("해외원조 (+2)"):
            st.session_state.current_action = {"actor": "Player", "action": "Foreign Aid", "target": "AI"}
            st.session_state.phase = "REACTION_WAIT"
            st.rerun()
            
        if c3.button("세금징수 (+3, 공작)"):
            st.session_state.current_action = {"actor": "Player", "action": "Tax", "target": "AI"}
            st.session_state.phase = "REACTION_WAIT"
            st.rerun()
            
        if c4.button("교환 (카드변경, 대사)"):
            st.session_state.current_action = {"actor": "Player", "action": "Exchange", "target": "AI"}
            st.session_state.phase = "REACTION_WAIT"
            st.rerun()

        if c5.button("갈취 (+2뺏기, 사령관)"):
            st.session_state.current_action = {"actor": "Player", "action": "Steal", "target": "AI"}
            st.session_state.phase = "REACTION_WAIT"
            st.rerun()
            
        if c6.button("암살 (-3코인, 암살자)"):
            if st.session_state.player["coins"] >= 3:
                st.session_state.current_action = {"actor": "Player", "action": "Assassinate", "target": "AI"}
                st.session_state.phase = "REACTION_WAIT"
                st.rerun()
            else:
                st.warning("코인이 부족합니다 (3원 필요)")
                
        if c7.button("쿠 (-7코인)"):
            if st.session_state.player["coins"] >= 7:
                st.session_state.current_action = {"actor": "Player", "action": "Coup", "target": "AI"}
                execute_action_result("Player", "Coup")
            else:
                st.warning("코인이 부족합니다 (7원 필요)")

# 2. 플레이어 행동 후 -> AI 반응
if st.session_state.turn == "Player" and st.session_state.phase == "REACTION_WAIT":
    action = st.session_state.current_action["action"]
    
    if action == "Income":
        execute_action_result("Player", "Income")
    else:
        with st.spinner("AI가 고민 중입니다..."):
            time.sleep(1) 
            reaction = ai_react_to_player(action)
        
        if reaction == "Pass":
            log("AI가 당신의 행동을 허용했습니다.")
            execute_action_result("Player", action)
            
        elif reaction == "Challenge":
            st.warning(f"🚨 AI가 당신의 [{ACTIONS[action]['role']}] 신분에 도전했습니다!")
            result = resolve_challenge("AI", "Player", ACTIONS[action]["role"])
            if result == "CHALLENGE_FAILED": 
                execute_action_result("Player", action)
            else: 
                st.session_state.current_action = None
                st.session_state.turn = "AI"
                st.session_state.phase = "SELECT_ACTION"
                st.rerun()
                
        elif reaction == "Block":
            st.warning("🛡️ AI가 방어를 시도합니다!")
            st.session_state.phase = "PLAYER_CHALLENGE_BLOCK"
            st.rerun()

# 3. AI 방어 후 -> 플레이어 선택
if st.session_state.phase == "PLAYER_CHALLENGE_BLOCK":
    st.subheader("AI가 방어했습니다. 도전하시겠습니까?")
    col1, col2 = st.columns(2)
    
    act = st.session_state.current_action["action"]
    block_role = "Contessa" if act == "Assassinate" else ("Duke" if act == "Foreign Aid" else "Captain")
    
    if col1.button("도전하기 (거짓말이다!)"):
        result = resolve_challenge("Player", "AI", block_role)
        if result == "CHALLENGE_SUCCESS": 
            execute_action_result("Player", act)
        else:
            st.session_state.current_action = None
            st.session_state.turn = "AI"
            st.session_state.phase = "SELECT_ACTION"
            st.rerun()
            
    if col2.button("인정하기 (방어 허용)"):
        log("AI의 방어를 인정했습니다. 행동이 무효화됩니다.")
        st.session_state.current_action = None
        st.session_state.turn = "AI"
        st.session_state.phase = "SELECT_ACTION"
        st.rerun()

# 4. AI 턴: 행동 선택
if st.session_state.turn == "AI" and st.session_state.phase == "SELECT_ACTION":
    with st.spinner("AI가 행동을 선택 중입니다..."):
        time.sleep(1)
        ai_act_name = ai_decide_action()
        st.session_state.current_action = {"actor": "AI", "action": ai_act_name, "target": "Player"}
        
        if ai_act_name in ["Coup", "Income"]:
            execute_action_result("AI", ai_act_name)
        else:
            st.session_state.phase = "PLAYER_REACTION_WAIT"
            st.rerun()

# 5. AI 행동 후 -> 플레이어 반응
if st.session_state.turn == "AI" and st.session_state.phase == "PLAYER_REACTION_WAIT":
    act_name = st.session_state.current_action["action"]
    role_needed = ACTIONS[act_name]["role"]
    
    st.error(f"⚠️ AI가 [{ACTIONS[act_name]['desc']}] 을(를) 선언했습니다!")
    
    col1, col2, col3 = st.columns(3)
    
    if col1.button("허용하기"):
        execute_action_result("AI", act_name)
        
    if role_needed and col2.button("도전하기 (블러핑 의심)"):
        result = resolve_challenge("Player", "AI", role_needed)
        if result == "CHALLENGE_SUCCESS":
            st.session_state.current_action = None
            st.session_state.turn = "Player"
            st.session_state.phase = "SELECT_ACTION"
            st.rerun()
        else:
             execute_action_result("AI", act_name)

    can_block = False
    block_btn_text = ""
    my_block_role = ""
    
    if act_name == "Foreign Aid":
        can_block = True
        block_btn_text = "공작으로 막기"
        my_block_role = "Duke"
    elif act_name == "Assassinate":
        can_block = True
        block_btn_text = "귀부인으로 막기"
        my_block_role = "Contessa"
    elif act_name == "Steal":
        can_block = True
        block_btn_text = "사령관/대사로 막기"
        my_block_role = "Captain" 
    
    if can_block and col3.button(block_btn_text):
        log(f"🛡️ 당신이 {my_block_role} 신분으로 방어를 시도했습니다.")
        
        if ai_react_to_player(act_name) == "Challenge":
             st.warning("🚨 AI가 당신의 방어에 도전했습니다!")
             result = resolve_challenge("AI", "Player", my_block_role)
             if result == "CHALLENGE_FAILED":
                 st.session_state.current_action = None
                 st.session_state.turn = "Player"
                 st.session_state.phase = "SELECT_ACTION"
                 st.rerun()
             else:
                 execute_action_result("AI", act_name)
        else:
            log("AI가 방어를 인정했습니다.")
            st.session_state.current_action = None
            st.session_state.turn = "Player"
            st.session_state.phase = "SELECT_ACTION"
            st.rerun()
