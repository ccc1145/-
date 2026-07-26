import { useState } from 'react'

interface AuthPanelProps {
  isLoading: boolean
  error: string | null
  onLogin: (username: string, password: string) => Promise<void>
  onRegister: (username: string, password: string) => Promise<void>
}

export function AuthPanel({ isLoading, error, onLogin, onRegister }: AuthPanelProps) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [registering, setRegistering] = useState(false)

  return (
    <main className="relative z-10 mx-auto flex min-h-[calc(100vh-74px)] max-w-6xl items-center justify-center px-4 py-10">
      <section className="ink-panel w-full max-w-md rounded-[28px] border border-amber-200/20 p-8 shadow-2xl">
        <p className="text-center text-xs tracking-[0.4em] text-amber-200/60">洞天身份</p>
        <h2 className="mt-3 text-center font-serif text-3xl tracking-[0.2em] text-amber-50">
          {registering ? '创建账号' : '登录洞府'}
        </h2>
        <p className="mt-4 text-center text-sm leading-6 text-stone-400">登录后，所有角色存档都会保存在同一账号下。</p>
        <form
          className="mt-7 space-y-4"
          onSubmit={(event) => {
            event.preventDefault()
            void (registering ? onRegister(username, password) : onLogin(username, password))
          }}
        >
          <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="用户名（3-32 字符）" maxLength={32} disabled={isLoading} className="w-full rounded-xl border border-amber-100/15 bg-black/20 px-4 py-3 text-stone-100 outline-none focus:border-amber-200/50" />
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="密码（至少 6 字符）" disabled={isLoading} className="w-full rounded-xl border border-amber-100/15 bg-black/20 px-4 py-3 text-stone-100 outline-none focus:border-amber-200/50" />
          {error && <p className="text-sm text-red-200">{error}</p>}
          <button type="submit" disabled={isLoading || username.trim().length < 3 || password.length < 6} className="w-full rounded-xl border border-amber-200/30 bg-amber-100/10 px-5 py-3.5 text-amber-50 disabled:opacity-40">
            {isLoading ? '处理中……' : registering ? '注册并登录' : '登录'}
          </button>
        </form>
        <button type="button" onClick={() => setRegistering((value) => !value)} className="mt-5 w-full text-sm text-amber-100/65 hover:text-amber-50">
          {registering ? '已有账号？返回登录' : '没有账号？立即注册'}
        </button>
      </section>
    </main>
  )
}
