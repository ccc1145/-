import type {
  ActionRequest,
  ActionResponse,
  Choice,
  GameState,
  NarrativeSegment,
  SpiritRootType,
  StartSessionRequest,
  StartSessionResponse,
} from '../types/game'

const MOCK_DELAY = 450

let currentState: GameState | null = null
let currentChoices: Choice[] = []

function wait(ms = MOCK_DELAY): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

function cloneState(state: GameState): GameState {
  return structuredClone(state)
}

function randomQuality(): number {
  return Math.floor(Math.random() * 4) + 6
}

function randomSpiritRoot(): SpiritRootType {
  const roots: SpiritRootType[] = ['金', '木', '水', '火', '土']
  return roots[Math.floor(Math.random() * roots.length)]
}

function buildInitialState(request: StartSessionRequest): GameState {
  return {
    session_id: `sess_${Date.now()}`,
    current_scene_id: 'trial_grounds',
    turn_count: 0,
    player: {
      name: request.player_name.trim() || '无名',
      cultivation: 0,
      realm: {
        major: '练气',
        minor: 1,
      },
      spirit_root: {
        type: request.spirit_root_type ?? randomSpiritRoot(),
        quality: randomQuality(),
      },
      attributes: {
        strength: 5,
        agility: 5,
        intelligence: 6,
        perception: 7,
      },
      inventory: [],
      hp: 100,
      max_hp: 100,
      mp: 50,
      max_mp: 50,
      spirit_stones: 0,
      skills: [],
    },
    npcs: {
      master: {
        id: 'master',
        name: '玄清真人',
        affinity: 0,
        location: '青云门试炼场',
        known_info: ['青云门执事长老', '性情严厉，重视根基'],
        dialogue_history: [],
      },
      senior_brother: {
        id: 'senior_brother',
        name: '陆明远',
        affinity: 0,
        location: '青云门试炼场',
        known_info: ['青云门大师兄'],
        dialogue_history: [],
      },
      rival: {
        id: 'rival',
        name: '韩厉',
        affinity: -5,
        location: '青云门试炼场',
        known_info: ['与你同批参加入门试炼'],
        dialogue_history: [],
      },
    },
    world: {
      current_location: '青云门试炼场',
      time: {
        day: 1,
        period: '上午',
      },
      flags: {
        trial_completed: false,
        became_disciple: false,
        first_cultivation_completed: false,
      },
    },
    recent_events: [],
    free_input_history: [],
  }
}

function updateRealm(state: GameState): void {
  const cultivation = state.player.cultivation

  if (cultivation >= 180) {
    state.player.realm.minor = 3
  } else if (cultivation >= 90) {
    state.player.realm.minor = 2
  } else {
    state.player.realm.minor = 1
  }
}

function addCultivation(state: GameState, amount: number): void {
  state.player.cultivation += amount
  updateRealm(state)
}

function changeAffinity(state: GameState, npcId: string, amount: number): void {
  const npc = state.npcs[npcId]
  if (!npc) return
  npc.affinity = Math.max(-100, Math.min(100, npc.affinity + amount))
}

function addRecentEvent(
  state: GameState,
  playerChoice: string,
  narrative: string,
  stateChanges: Record<string, unknown>,
): void {
  state.recent_events.push({
    turn: state.turn_count,
    scene_id: state.current_scene_id,
    narrative,
    player_choice: playerChoice,
    state_changes: stateChanges,
    timestamp: new Date().toISOString(),
  })
  state.recent_events = state.recent_events.slice(-10)
}

function createResponse(
  state: GameState,
  narrativeSegments: NarrativeSegment[],
  choices: Choice[],
  options?: {
    sceneChanged?: boolean
    gameOver?: boolean
    freeInputEnabled?: boolean
    thought?: string
  },
): ActionResponse {
  const narrative = narrativeSegments.map((segment) => segment.text).join('\n')
  currentState = cloneState(state)
  currentChoices = structuredClone(choices)

  return {
    success: true,
    new_state: cloneState(state),
    narrative,
    narrative_segments: narrativeSegments,
    available_choices: choices,
    scene_changed: options?.sceneChanged ?? false,
    scene_id: state.current_scene_id,
    game_over: options?.gameOver ?? false,
    free_input_enabled: options?.freeInputEnabled ?? true,
    agent_thought: options?.thought,
  }
}

function handleTrialGrounds(state: GameState, payload: string): ActionResponse {
  if (payload === 'hesitate') {
    changeAffinity(state, 'master', -5)
    state.current_scene_id = 'trial_hesitate'
    const segments: NarrativeSegment[] = [
      {
        type: 'narration',
        text: '你没有立刻上前，而是暗自观察四周。几名弟子已经完成测试，测灵石上余光未散。',
      },
      {
        type: 'dialogue',
        speaker: '玄清真人',
        text: '修行之路，最忌瞻前顾后。既已来到此处，还不上前？',
      },
    ]
    const choices: Choice[] = [
      { id: 'touch_stone', text: '收敛心神，将手放上测灵石' },
      { id: 'apologize', text: '向长老行礼道歉' },
    ]
    addRecentEvent(state, payload, segments.map((item) => item.text).join(''), {
      'npcs.master.affinity': -5,
    })
    return createResponse(state, segments, choices, {
      sceneChanged: true,
      thought: '玩家犹豫，玄清真人好感度降低 5。',
    })
  }

  state.current_scene_id = 'trial_result'
  state.world.flags.trial_completed = true
  addCultivation(state, 10)

  const { type, quality } = state.player.spirit_root
  const lightDescription: Record<SpiritRootType, string> = {
    金: '金白色锋芒',
    木: '青绿色生机',
    水: '幽蓝色波纹',
    火: '赤红色流光',
    土: '沉黄色厚光',
    杂灵根: '五色交错的微光',
  }
  const segments: NarrativeSegment[] = [
    {
      type: 'narration',
      text: `你的掌心触及测灵石，冰凉之意沿着经脉散开。片刻后，石面浮现出${lightDescription[type]}，灵气在纹路间缓缓流动。`,
    },
    {
      type: 'dialogue',
      speaker: '玄清真人',
      text: `${type}灵根，品质${quality}等。根骨尚可，心性如何，还要日后再看。`,
    },
    {
      type: 'narration',
      text: '周围弟子的目光落在你身上。你隐约感觉到，体内似乎多出了一缕若有若无的灵气。',
    },
  ]
  const choices: Choice[] = [
    { id: 'express_gratitude', text: '弟子拜谢长老' },
    { id: 'stay_silent', text: '默默退到一旁' },
    { id: 'ask_question', text: '询问长老修炼之法' },
  ]
  addRecentEvent(state, payload, segments.map((item) => item.text).join(''), {
    'player.cultivation': 10,
    'world.flags.trial_completed': true,
  })
  return createResponse(state, segments, choices, {
    sceneChanged: true,
    thought: '完成灵根测试，修为增加 10，进入试炼结果场景。',
  })
}

function handleTrialHesitate(state: GameState, payload: string): ActionResponse {
  if (payload === 'apologize') {
    changeAffinity(state, 'master', 3)
  }
  return handleTrialGrounds(state, 'touch_stone')
}

function masterSelectionResponse(state: GameState, opening: NarrativeSegment[]): ActionResponse {
  state.current_scene_id = 'master_selection'
  const choices: Choice[] = [
    { id: 'choose_master', text: '请求拜入玄清真人门下' },
    { id: 'ask_senior', text: '先向大师兄了解门中情况' },
  ]
  return createResponse(state, opening, choices, {
    sceneChanged: true,
    thought: '试炼完成，进入拜师阶段。',
  })
}

function handleTrialResult(state: GameState, payload: string): ActionResponse {
  if (payload === 'express_gratitude') {
    changeAffinity(state, 'master', 3)
    return masterSelectionResponse(state, [
      {
        type: 'narration',
        text: '你整理衣袖，向玄清真人郑重行了一礼。',
      },
      {
        type: 'dialogue',
        speaker: '玄清真人',
        text: '知礼而不失锐气，尚可。今日试炼结束后，你可随我前往传功殿。',
      },
    ])
  }

  if (payload === 'ask_question') {
    changeAffinity(state, 'master', 2)
    state.current_scene_id = 'master_qa'
    const segments: NarrativeSegment[] = [
      {
        type: 'narration',
        text: '你没有立刻退下，而是恭敬询问如何感应天地灵气。',
      },
      {
        type: 'dialogue',
        speaker: '玄清真人',
        text: '修炼无捷径。先静心，再观息，最后才是引气入体。根基若浮，走得越快，跌得越重。',
      },
    ]
    const choices: Choice[] = [
      { id: 'accept_guidance', text: '牢记教诲，认真道谢' },
      { id: 'continue_trial', text: '点头退下，等待后续安排' },
    ]
    addRecentEvent(state, payload, segments.map((item) => item.text).join(''), {
      'npcs.master.affinity': 2,
    })
    return createResponse(state, segments, choices, {
      sceneChanged: true,
      thought: '玩家主动求教，玄清真人好感度增加 2。',
    })
  }

  return masterSelectionResponse(state, [
    {
      type: 'narration',
      text: '你没有多言，只是安静退到一旁。玄清真人略一颔首，转身继续主持试炼。',
    },
  ])
}

function handleMasterQa(state: GameState, payload: string): ActionResponse {
  if (payload === 'accept_guidance') {
    changeAffinity(state, 'master', 2)
  }
  return masterSelectionResponse(state, [
    {
      type: 'narration',
      text: '你将长老的话记在心中。钟声再次响起，试炼场上的弟子陆续被带往各峰。',
    },
  ])
}

function handleMasterSelection(state: GameState, payload: string): ActionResponse {
  if (payload === 'ask_senior') {
    changeAffinity(state, 'senior_brother', 4)
    const segments: NarrativeSegment[] = [
      {
        type: 'narration',
        text: '你走向站在石阶旁的大师兄，低声询问青云门各峰的情况。',
      },
      {
        type: 'dialogue',
        speaker: '陆明远',
        text: '玄清师叔虽严厉，却最重弟子根基。你若真心修行，拜入他门下并非坏事。',
      },
    ]
    const choices: Choice[] = [{ id: 'choose_master', text: '听从建议，请求拜师' }]
    addRecentEvent(state, payload, segments.map((item) => item.text).join(''), {
      'npcs.senior_brother.affinity': 4,
    })
    return createResponse(state, segments, choices, {
      thought: '向大师兄求教，大师兄好感度增加 4。',
    })
  }

  state.current_scene_id = 'first_cultivation'
  state.world.current_location = '青云门静室'
  state.world.time.period = '傍晚'
  state.world.flags.became_disciple = true
  changeAffinity(state, 'master', 5)
  state.player.inventory.push({
    item_id: 'qi_gathering_pill',
    name: '聚气丹',
    quantity: 1,
    effects: [{ type: 'cultivation', value: 40, description: '帮助初学者凝聚灵气' }],
  })

  const segments: NarrativeSegment[] = [
    {
      type: 'narration',
      text: '传功殿中香烟袅袅。你跪坐于蒲团前，双手奉上弟子礼。玄清真人沉默片刻，最终接过名册。',
    },
    {
      type: 'dialogue',
      speaker: '玄清真人',
      text: '从今日起，你便是我门下记名弟子。此丹助你初次引气，但修行终究要靠自己。',
    },
    {
      type: 'narration',
      text: '你获得了【聚气丹】。入夜前，你被带到一间安静石室，准备第一次正式修炼。',
    },
  ]
  const choices: Choice[] = [
    { id: 'meditate', text: '不用丹药，先依口诀打坐' },
    { id: 'take_pill', text: '服下聚气丹，尝试引气入体' },
  ]
  addRecentEvent(state, payload, segments.map((item) => item.text).join(''), {
    'world.flags.became_disciple': true,
    'npcs.master.affinity': 5,
    inventory: '获得聚气丹',
  })
  return createResponse(state, segments, choices, {
    sceneChanged: true,
    thought: '玩家拜师成功，获得聚气丹并进入首次修炼。',
  })
}

function handleFirstCultivation(state: GameState, payload: string): ActionResponse {
  let gained = 35
  let method = '你依照口诀调整呼吸，耐心捕捉游离在空气中的灵气。'

  if (payload === 'take_pill') {
    const pill = state.player.inventory.find((item) => item.item_id === 'qi_gathering_pill')
    if (pill && pill.quantity > 0) {
      pill.quantity -= 1
      gained = 55
      method = '丹药入口即化，一股温热药力顺着经脉散开。你趁势运转口诀，引导灵气归入丹田。'
    }
  }

  state.player.inventory = state.player.inventory.filter((item) => item.quantity > 0)
  addCultivation(state, gained)
  state.world.flags.first_cultivation_completed = true
  state.current_scene_id = 'sect_tournament'
  state.world.current_location = '青云门演武场'
  state.world.time.day = 30
  state.world.time.period = '上午'

  const segments: NarrativeSegment[] = [
    { type: 'narration', text: method },
    {
      type: 'narration',
      text: `数个周天后，你终于感受到丹田中凝成了一缕清晰灵气。修为提升了 ${gained} 点。`,
    },
    {
      type: 'dialogue',
      speaker: '陆明远',
      text: '一个月后的门派小比已经开始。师弟，真正的考验才刚刚到来。',
    },
  ]
  const choices: Choice[] = [
    { id: 'step_forward', text: '登上演武台，接受同门挑战' },
    { id: 'observe_first', text: '先观察其他弟子的招式' },
  ]
  addRecentEvent(state, payload, segments.map((item) => item.text).join(''), {
    'player.cultivation': gained,
    'world.flags.first_cultivation_completed': true,
  })
  return createResponse(state, segments, choices, {
    sceneChanged: true,
    thought: `首次修炼完成，修为增加 ${gained}。`,
  })
}

function handleTournament(state: GameState, payload: string): ActionResponse {
  let gained = 20
  let opening = '你握紧木剑，踏上演武台。对面的韩厉抬手行礼，眼中却带着毫不掩饰的战意。'

  if (payload === 'observe_first') {
    state.player.attributes.perception += 1
    gained = 25
    opening = '你没有急着登台，而是仔细观察前几场比试。灵力运转与步法衔接的规律，逐渐在你心中清晰起来。'
  }

  addCultivation(state, gained)
  changeAffinity(state, 'rival', 3)
  state.current_scene_id = 'ending'
  state.world.time.period = '下午'

  const segments: NarrativeSegment[] = [
    { type: 'narration', text: opening },
    {
      type: 'narration',
      text: '木剑相交，清脆之声回荡在演武场。你虽招式生涩，却在最后关头稳住心神，以半步之差取得胜势。',
    },
    {
      type: 'dialogue',
      speaker: '玄清真人',
      text: '胜负只是一时。今日你能守住本心，才算没有辜负这一个月的修行。',
    },
    {
      type: 'narration',
      text: '夕阳越过青云峰顶，你第一次真正意识到：自己的修仙之路，才刚刚开始。',
    },
  ]
  addRecentEvent(state, payload, segments.map((item) => item.text).join(''), {
    'player.cultivation': gained,
    'npcs.rival.affinity': 3,
  })
  return createResponse(state, segments, [], {
    sceneChanged: true,
    gameOver: true,
    freeInputEnabled: false,
    thought: 'MVP 主线完成。',
  })
}

function handleFreeInput(state: GameState, payload: string): ActionResponse {
  const text = payload.trim()
  const master = state.npcs.master
  let intent = 'chat'
  let affinityChange = 0
  let reply = '玄清真人看了你一眼，没有立刻回答。片刻后，他示意你继续说下去。'

  if (/修炼|变强|功法|灵气/.test(text)) {
    intent = 'ask_cultivation'
    affinityChange = 2
    reply = '修行先修心。每日吐纳不可间断，莫因一时进境而自满。'
  } else if (/拜见|长老好|师父|弟子/.test(text)) {
    intent = 'respectful_expression'
    affinityChange = 2
    reply = '礼数不必过多。既有这份心，便用在修炼上。'
  } else if (/不服|规矩不合理|凭什么|挑战你/.test(text)) {
    intent = 'provoke'
    affinityChange = -8
    reply = '锋芒不是坏事，但若连敬畏都不懂，你还没有资格谈大道。'
  } else if (/观察|四周|环境|看看/.test(text)) {
    intent = 'observe'
    state.player.attributes.perception += 1
    reply = '你放缓呼吸，注意到试炼场石阶上刻着聚灵纹，空气中的灵气正缓慢向测灵石汇聚。'
  }

  changeAffinity(state, 'master', affinityChange)
  state.free_input_history.push({
    turn: state.turn_count,
    input_text: text,
    interpreted_intent: intent,
    narrative_response: reply,
    timestamp: new Date().toISOString(),
  })
  state.free_input_history = state.free_input_history.slice(-10)
  master.dialogue_history.push(`玩家：${text}\n玄清真人：${reply}`)
  master.dialogue_history = master.dialogue_history.slice(-5)

  const segments: NarrativeSegment[] = [
    {
      type: 'narration',
      text: `你说道：“${text}”`,
    },
    {
      type: affinityChange === 0 && intent === 'observe' ? 'narration' : 'dialogue',
      speaker: affinityChange === 0 && intent === 'observe' ? undefined : '玄清真人',
      text: reply,
    },
  ]

  addRecentEvent(state, text, segments.map((item) => item.text).join(''), {
    interpreted_intent: intent,
    'npcs.master.affinity': affinityChange,
  })
  return createResponse(state, segments, currentChoices, {
    thought: `自由输入意图识别为 ${intent}，好感度变化 ${affinityChange}。`,
  })
}

export const mockApi = {
  async startSession(request: StartSessionRequest): Promise<StartSessionResponse> {
    await wait()
    currentState = buildInitialState(request)
    currentChoices = [
      { id: 'touch_stone', text: '深吸一口气，将手放在测灵石上' },
      { id: 'hesitate', text: '暂不上前，观察其他弟子的测试' },
    ]

    const openingSegments: NarrativeSegment[] = [
      {
        type: 'narration',
        text: '晨雾笼罩青云山门，悠远钟声穿过层层云海。你与数十名少年站在试炼场前，等待决定命运的一刻。',
      },
      {
        type: 'narration',
        text: '试炼场中央，一块三尺高的青白色测灵石静静矗立。石旁的玄清真人目光如炬，正在逐一审视众人。',
      },
      {
        type: 'dialogue',
        speaker: '玄清真人',
        text: `${currentState.player.name}，上前测试灵根。`,
      },
    ]

    return {
      session_id: currentState.session_id,
      initial_state: cloneState(currentState),
      opening_narrative: openingSegments.map((segment) => segment.text).join('\n'),
      narrative_segments: openingSegments,
      available_choices: structuredClone(currentChoices),
      free_input_enabled: true,
    }
  },

  async submitAction(sessionId: string, request: ActionRequest): Promise<ActionResponse> {
    await wait()

    if (!currentState || currentState.session_id !== sessionId) {
      throw new Error('游戏会话不存在，请重新开始游戏。')
    }

    const state = cloneState(currentState)
    state.turn_count += 1

    if (request.action_type === 'free_input') {
      return handleFreeInput(state, request.payload)
    }

    switch (state.current_scene_id) {
      case 'trial_grounds':
        return handleTrialGrounds(state, request.payload)
      case 'trial_hesitate':
        return handleTrialHesitate(state, request.payload)
      case 'trial_result':
        return handleTrialResult(state, request.payload)
      case 'master_qa':
        return handleMasterQa(state, request.payload)
      case 'master_selection':
        return handleMasterSelection(state, request.payload)
      case 'first_cultivation':
        return handleFirstCultivation(state, request.payload)
      case 'sect_tournament':
        return handleTournament(state, request.payload)
      default:
        return createResponse(
          state,
          [{ type: 'narration', text: '故事暂时告一段落。' }],
          [],
          { gameOver: true, freeInputEnabled: false },
        )
    }
  },

  reset(): void {
    currentState = null
    currentChoices = []
  },
}
