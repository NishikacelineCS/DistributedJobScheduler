import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Terminal, Shield, LogIn, UserPlus } from 'lucide-react';

const Login = () => {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [orgName, setOrgName] = useState('');
  const [localError, setLocalError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const { login, register } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLocalError('');
    setSubmitting(true);

    try {
      if (isRegister) {
        if (!orgName.trim()) {
          setLocalError('Organization name is required');
          setSubmitting(false);
          return;
        }
        await register(email, password, orgName);
      } else {
        await login(email, password);
      }
    } catch (err) {
      setLocalError(err.message || 'An error occurred during submission.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-4" style={{ backgroundColor: '#0F172A' }}>
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-cyan-950/10 via-[#0F172A] to-[#0F172A] -z-10" />

      <div className="w-full max-w-md p-8 rounded-2xl glass-card border border-slate-800/40 shadow-2xl">
        <div className="flex flex-col items-center mb-8">
          <div className="bg-cyan-500/10 p-3 rounded-2xl border border-cyan-500/20 mb-4">
            <Terminal className="w-8 h-8 text-cyan-500 animate-pulse" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Distributed Job Scheduler</h1>
          <p className="text-sm text-slate-400 mt-1">Industrial-Grade Background Processing</p>
        </div>

        {localError && (
          <div className="bg-red-500/10 border border-red-500/20 text-red-400 text-sm p-3 rounded-lg mb-6">
            {localError}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          {isRegister && (
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Organization Name</label>
              <input
                type="text"
                required
                className="w-full px-4 py-3 rounded-lg glass-input text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-cyan-500/20 text-sm transition-all"
                placeholder="e.g. Acme Corp"
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Email Address</label>
            <input
              type="email"
              required
              className="w-full px-4 py-3 rounded-lg glass-input text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-cyan-500/20 text-sm transition-all"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Password</label>
            <input
              type="password"
              required
              className="w-full px-4 py-3 rounded-lg glass-input text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-cyan-500/20 text-sm transition-all"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-3 px-4 rounded-lg bg-emerald-600 hover:bg-emerald-500 active:bg-blue-700 text-white font-medium flex items-center justify-center gap-2 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed text-sm shadow-lg shadow-blue-600/25 mt-2"
          >
            {submitting ? (
              <span className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : isRegister ? (
              <>
                <UserPlus className="w-4 h-4" /> Register Organization
              </>
            ) : (
              <>
                <LogIn className="w-4 h-4" /> Authenticate
              </>
            )}
          </button>
        </form>

        <div className="mt-8 pt-6 border-t border-slate-800/60 text-center">
          <button
            type="button"
            className="text-xs text-cyan-400 hover:text-cyan-300 font-medium transition-all"
            onClick={() => {
              setIsRegister(!isRegister);
              setLocalError('');
            }}
          >
            {isRegister ? 'Already have an organization? Login' : "Don't have an organization? Create one"}
          </button>
        </div>
      </div>
    </div>
  );

};

export default Login;
