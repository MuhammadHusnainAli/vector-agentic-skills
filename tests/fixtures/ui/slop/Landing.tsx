export default function Landing() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-purple-600 via-indigo-600 to-blue-500 text-center">
      <div className="absolute top-20 left-10 w-72 h-72 bg-purple-400 rounded-full blur-3xl opacity-30 animate-pulse" />
      <h1 className="text-6xl font-bold bg-gradient-to-r from-purple-400 to-pink-600 bg-clip-text text-transparent">
        🚀 Unlock the Power of AI ✨
      </h1>
      <p className="text-gray-300">Supercharge your workflow with our cutting-edge, all-in-one platform. Seamlessly transform your productivity.</p>
      <button className="bg-indigo-600 rounded-2xl shadow-2xl hover:scale-105 px-8 py-4">Get Started 🎉</button>
      <p>Trusted by 10,000+ teams · 99.9% uptime</p>
      <section className="grid md:grid-cols-3 gap-8">
        <div className="backdrop-blur-lg bg-white/10 rounded-2xl shadow-xl p-8 hover:-translate-y-2">
          <div className="w-12 h-12 bg-indigo-100 rounded-xl flex items-center">⚡</div>
          <h3>Lightning Fast</h3><p>Blazing fast performance that will elevate your team.</p>
        </div>
        <div className="backdrop-blur-lg bg-white/10 rounded-2xl shadow-xl p-8 hover:-translate-y-2">
          <div className="w-12 h-12 bg-purple-100 rounded-xl flex items-center">🔒</div>
          <h3>Secure by Design</h3><p>Enterprise-grade security, effortlessly.</p>
        </div>
        <div className="backdrop-blur-lg bg-white/10 rounded-2xl shadow-xl p-8 hover:-translate-y-2">
          <div className="w-12 h-12 bg-pink-100 rounded-xl flex items-center">🤖</div>
          <h3>AI Powered</h3><p>Lorem ipsum dolor sit amet.</p>
        </div>
      </section>
      <blockquote>"This changed everything!" ★★★★★ John Doe, CEO at Acme</blockquote>
      <a className="text-indigo-600 border-indigo-500">Learn more</a>
    </main>
  );
}
