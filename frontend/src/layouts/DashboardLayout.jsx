import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  Activity, BarChart3, Layers, Calendar,
  Cpu, LogOut, Shield, User, Terminal
} from 'lucide-react';

const DashboardLayout = ({ children }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const navItems = [
    { to: '/', label: 'Overview', icon: BarChart3, end: true },
    { to: '/jobs', label: 'Jobs Explorer', icon: Layers },
    { to: '/schedules', label: 'Cron Schedules', icon: Calendar },
    { to: '/workers', label: 'Active Workers', icon: Cpu }
  ];

  return (
    <div className="flex min-h-screen" style={{ backgroundColor: '#0B0F19' }}>
      {/* Sidebar Panel */}
      <aside className="w-64 border-r border-[#1F2937] flex flex-col justify-between p-4" style={{ backgroundColor: '#111827' }}>
        <div className="space-y-6">
          {/* Logo */}
          <div className="flex items-center gap-2.5 px-2">
            <div className="bg-emerald-600/10 p-1.5 rounded-lg border border-emerald-500/20">
              <Terminal className="w-4 h-4 text-blue-500" />
            </div>
            <span className="font-bold text-sm tracking-tight text-white leading-none">Distributed Job Scheduler</span>
          </div>

          {/* Navigation Links */}
          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 px-3 py-2 rounded-md text-xs font-medium tracking-wide transition-all cursor-pointer ${isActive
                      ? 'bg-slate-800 text-white border-l-2 border-emerald-500'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
                    }`
                  }
                >
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </nav>
        </div>

        {/* User profile card & Logout */}
        <div className="space-y-3 pt-4 border-t border-[#1F2937]">
          <div className="flex items-center gap-2.5 bg-[#0B0F19]/60 p-2.5 rounded-md border border-[#1F2937]">
            <div className="bg-emerald-500/10 p-1.5 rounded-md text-blue-400">
              <User className="w-3.5 h-3.5" />
            </div>
            <div className="truncate">
              <p className="text-xs font-medium text-slate-200 truncate">{user?.email}</p>
              <span className="text-[9px] text-slate-500 block uppercase font-bold tracking-wider">Administrator</span>
            </div>
          </div>

          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-xs font-medium text-red-400 hover:text-red-300 hover:bg-red-500/5 transition-all cursor-pointer"
          >
            <LogOut className="w-4 h-4" />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Main Content viewport */}
      <main className="flex-1 overflow-y-auto max-h-screen">
        {/* Top Scope bar */}
        <header className="h-14 border-b border-[#1F2937] flex items-center justify-between px-6" style={{ backgroundColor: '#111827' }}>
          <div className="flex items-center gap-2">
            <Shield className="w-3.5 h-3.5 text-emerald-500" />
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Tenant Scope:</span>
            <span className="text-[10px] font-bold text-slate-300 uppercase px-2 py-0.5 rounded-full bg-[#1F2937] border border-slate-700/60">
              {user?.organization_id ? 'Authenticated' : 'Offline'}
            </span>
          </div>
          <div className="text-[10px] text-slate-500 font-medium">
            Service Active • UTC Time
          </div>
        </header>

        <div className="p-6">
          {children}
        </div>
      </main>
    </div>
  );
};

export default DashboardLayout;
