function App() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-700 bg-slate-900 px-6 py-4">
        <h1 className="text-center text-2xl font-bold">
          修仙模拟器
        </h1>
      </header>

      <main className="mx-auto grid max-w-7xl grid-cols-1 gap-4 p-4 lg:grid-cols-[1fr_300px]">
        <section className="flex min-h-[700px] flex-col gap-4">
          <div className="flex-1 rounded-lg border border-slate-700 bg-slate-900 p-6">
            <h2 className="mb-4 text-lg font-semibold">剧情</h2>

            <p className="leading-8 text-slate-300">
              你从昏迷中醒来，发现自己身处一座云雾缭绕的山谷。
              远处传来悠扬的钟声，似乎有一座修仙宗门隐藏在群山之间。
            </p>
          </div>

          <div className="rounded-lg border border-slate-700 bg-slate-900 p-4">
            <h2 className="mb-3 font-semibold">请选择你的行动</h2>

            <div className="grid gap-2">
              <button className="rounded bg-slate-700 px-4 py-3 text-left hover:bg-slate-600">
                1. 顺着钟声寻找宗门
              </button>

              <button className="rounded bg-slate-700 px-4 py-3 text-left hover:bg-slate-600">
                2. 留在原地观察环境
              </button>
            </div>
          </div>

          <div className="flex gap-2 rounded-lg border border-slate-700 bg-slate-900 p-4">
            <input
              className="flex-1 rounded border border-slate-600 bg-slate-800 px-4 py-2 outline-none focus:border-slate-400"
              placeholder="输入你想做的事情……"
            />

            <button className="rounded bg-emerald-700 px-6 py-2 hover:bg-emerald-600">
              发送
            </button>
          </div>
        </section>

        <aside className="rounded-lg border border-slate-700 bg-slate-900 p-5">
          <h2 className="mb-5 text-lg font-semibold">角色状态</h2>

          <div className="space-y-4 text-sm">
            <p>
              <span className="text-slate-400">姓名：</span>
              无名
            </p>

            <p>
              <span className="text-slate-400">境界：</span>
              凡人
            </p>

            <p>
              <span className="text-slate-400">修为：</span>
              0 / 100
            </p>

            <p>
              <span className="text-slate-400">灵根：</span>
              尚未检测
            </p>

            <p>
              <span className="text-slate-400">生命：</span>
              100 / 100
            </p>
          </div>
        </aside>
      </main>
    </div>
  )
}

export default App