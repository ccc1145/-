import type { GameState, StatusField } from '../types/game'

interface StatusPanelProps {
  state: GameState
  changeIds?: Partial<Record<StatusField, number>>
}

function affinityText(value: number): string {
  if (value >= 30) return '亲近'
  if (value > 0) return '友善'
  if (value <= -30) return '厌恶'
  if (value < 0) return '冷淡'
  return '平常'
}

function sectText(flags: Record<string, boolean>): string {
  if (flags.sect_chosen_xuanqing) return '玄清宗 · 外门弟子'
  if (flags.sect_chosen_shenwu) return '神武门 · 外门弟子'
  if (flags.sect_chosen_fulong) return '扶龙宫 · 外门弟子'
  if (flags.sect_chosen_hongchen) return '红尘阁 · 外门弟子'
  return '中洲 · 待启灵者'
}

export function StatusPanel({ state, changeIds = {} }: StatusPanelProps) {
  const { player, world, npcs } = state
  const currentLevelStart = (player.realm.minor - 1) * 90
  const progress = Math.max(0, Math.min(100, ((player.cultivation - currentLevelStart) / 90) * 100))
  const latestChangeId = (...fields: StatusField[]) => Math.max(0, ...fields.map((field) => changeIds[field] ?? 0))
  const pulseClass = (changeId: number) => changeId > 0 ? 'status-field-pulse' : ''
  const cultivationChangeId = latestChangeId('cultivation', 'realm')
  const locationChangeId = latestChangeId('location')
  const relationChangeId = latestChangeId('relations')
  const inventoryChangeId = latestChangeId('inventory')

  return (
    <aside className="space-y-4">
      <section className="ink-panel rounded-2xl border border-amber-100/15 p-5">
        <div className="mb-5 flex items-center gap-3 border-b border-amber-100/10 pb-4">
          <div className="flex size-11 items-center justify-center rounded-full border border-amber-200/20 bg-amber-100/[0.06] font-serif text-xl text-amber-100">
            {player.name.slice(0, 1)}
          </div>
          <div>
            <h2 className="font-serif text-lg tracking-[0.15em] text-amber-50">{player.name}</h2>
            <p className="mt-1 text-xs text-stone-500">{sectText(world.flags)}</p>
          </div>
        </div>

        <div className="space-y-4 text-sm">
          <div key={`cultivation-${cultivationChangeId}`} className={pulseClass(cultivationChangeId)}>
            <div className="mb-2 flex items-center justify-between">
              <span className="text-stone-500">境界</span>
              <span className="text-amber-100">
                {player.realm.major} {player.realm.minor} 层
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-black/35">
              <div
                className="h-full rounded-full bg-gradient-to-r from-emerald-700 via-emerald-400 to-amber-200 transition-all duration-700"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="mt-1.5 text-right text-[10px] text-stone-600">修为 {player.cultivation}</p>
          </div>

          <dl className="grid grid-cols-2 gap-3">
            <div key={`spirit-root-${changeIds.spiritRoot ?? 0}`} className={`stat-card ${pulseClass(changeIds.spiritRoot ?? 0)}`}>
              <dt>灵根</dt>
              <dd>{player.spirit_root.type}</dd>
            </div>
            <div key={`spirit-quality-${changeIds.spiritRootQuality ?? 0}`} className={`stat-card ${pulseClass(changeIds.spiritRootQuality ?? 0)}`}>
              <dt>品质</dt>
              <dd>{player.spirit_root.quality} 等</dd>
            </div>
            <div key={`strength-${changeIds.strength ?? 0}`} className={`stat-card ${pulseClass(changeIds.strength ?? 0)}`}>
              <dt>力量</dt>
              <dd>{player.attributes.strength}</dd>
            </div>
            <div key={`agility-${changeIds.agility ?? 0}`} className={`stat-card ${pulseClass(changeIds.agility ?? 0)}`}>
              <dt>身法</dt>
              <dd>{player.attributes.agility}</dd>
            </div>
            <div key={`intelligence-${changeIds.intelligence ?? 0}`} className={`stat-card ${pulseClass(changeIds.intelligence ?? 0)}`}>
              <dt>神识</dt>
              <dd>{player.attributes.intelligence}</dd>
            </div>
            <div key={`perception-${changeIds.perception ?? 0}`} className={`stat-card ${pulseClass(changeIds.perception ?? 0)}`}>
              <dt>悟性</dt>
              <dd>{player.attributes.perception}</dd>
            </div>
          </dl>
        </div>
      </section>

      <section className="ink-panel rounded-2xl border border-amber-100/15 p-5">
        <h3 className="mb-4 text-xs tracking-[0.22em] text-amber-100/60">角色资源</h3>
        <dl className="grid grid-cols-2 gap-3">
          <div key={`hp-${changeIds.hp ?? 0}`} className={`stat-card ${pulseClass(changeIds.hp ?? 0)}`}>
            <dt>生命</dt>
            <dd>{player.hp ?? '—'} / {player.max_hp ?? '—'}</dd>
          </div>
          <div key={`mp-${changeIds.mp ?? 0}`} className={`stat-card ${pulseClass(changeIds.mp ?? 0)}`}>
            <dt>灵力</dt>
            <dd>{player.mp ?? '—'} / {player.max_mp ?? '—'}</dd>
          </div>
          <div key={`stones-${changeIds.spiritStones ?? 0}`} className={`stat-card ${pulseClass(changeIds.spiritStones ?? 0)}`}>
            <dt>灵石</dt>
            <dd>{player.spirit_stones}</dd>
          </div>
          <div key={`skills-${changeIds.skills ?? 0}`} className={`stat-card ${pulseClass(changeIds.skills ?? 0)}`}>
            <dt>功法</dt>
            <dd>{player.skills.length}</dd>
          </div>
        </dl>
      </section>

      <section key={`location-${locationChangeId}`} className={`ink-panel rounded-2xl border border-amber-100/15 p-5 ${pulseClass(locationChangeId)}`}>
        <h3 className="mb-4 text-xs tracking-[0.22em] text-amber-100/60">当前所在</h3>
        <p className="font-serif text-base text-stone-200">{world.current_location}</p>
        <p className="mt-2 text-xs text-stone-500">
          第 {world.time.day} 日 · {world.time.period} · 第 {state.turn_count} 回合
        </p>
      </section>

      <section key={`relations-${relationChangeId}`} className={`ink-panel rounded-2xl border border-amber-100/15 p-5 ${pulseClass(relationChangeId)}`}>
        <h3 className="mb-4 text-xs tracking-[0.22em] text-amber-100/60">人物关系</h3>
        <div className="space-y-3">
          {Object.values(npcs).map((npc) => (
            <div key={npc.id} className="flex items-center justify-between gap-3 text-sm">
              <span className="text-stone-300">{npc.name}</span>
              <span
                className={`text-xs ${
                  npc.affinity > 0
                    ? 'text-emerald-300/75'
                    : npc.affinity < 0
                      ? 'text-red-300/75'
                      : 'text-stone-500'
                }`}
              >
                {affinityText(npc.affinity)} {npc.affinity >= 0 ? '+' : ''}
                {npc.affinity}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section key={`inventory-${inventoryChangeId}`} className={`ink-panel rounded-2xl border border-amber-100/15 p-5 ${pulseClass(inventoryChangeId)}`}>
        <h3 className="mb-4 text-xs tracking-[0.22em] text-amber-100/60">储物袋</h3>
        {player.inventory.length > 0 ? (
          <div className="space-y-2">
            {player.inventory.map((item) => (
              <div
                key={item.item_id}
                className="flex items-center justify-between rounded-lg border border-stone-100/8 bg-black/10 px-3 py-2 text-sm"
              >
                <span className="text-stone-300">{item.name}</span>
                <span className="text-xs text-amber-100/60">× {item.quantity}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-stone-600">空空如也</p>
        )}
      </section>
    </aside>
  )
}
